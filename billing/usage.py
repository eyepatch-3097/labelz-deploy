# billing/usage.py
from __future__ import annotations

from datetime import timedelta, datetime
from typing import Optional, Dict, Any

from django.db import transaction
from django.utils import timezone

from accounts.models import Org
from billing.constants import (
    TRIAL_WORKSPACE_LIMIT, TRIAL_TEMPLATE_LIMIT, TRIAL_LABELS_TOTAL,
)
from .models import OrgSubscription, OrgUsageLifetime, OrgUsagePeriod, OrgLimitOverride


def get_or_create_subscription(org: Org) -> OrgSubscription:
    sub, created = OrgSubscription.objects.get_or_create(
        org=org,
        defaults={"status": OrgSubscription.STATUS_TRIAL},
    )
    # If some legacy org had status empty, normalize to TRIAL
    if created:
        return sub
    if not sub.status:
        sub.status = OrgSubscription.STATUS_TRIAL
        sub.save(update_fields=["status", "updated_at"])
    return sub


def refresh_subscription_state(sub: OrgSubscription, *, now=None) -> OrgSubscription:
    """
    Makes subscription state consistent.
    Defensive: if 'now' is passed incorrectly, we recover safely.
    """

    if not sub:
        return sub

    # --- hard safety: ensure 'now' is a datetime ---
    if now is None or isinstance(now, OrgSubscription) or not isinstance(now, datetime):
        now = timezone.now()

    # If ACTIVE and expired -> NONE
    if sub.status == OrgSubscription.STATUS_ACTIVE:
        if sub.current_period_end and now >= sub.current_period_end:
            sub.status = OrgSubscription.STATUS_NONE
            sub.plan_version = None
            sub.current_period_start = None
            sub.current_period_end = None
            sub.cancel_at_period_end = False
            sub.save(update_fields=[
                "status",
                "plan_version",
                "current_period_start",
                "current_period_end",
                "cancel_at_period_end",
                "updated_at",
            ])

    return sub

def get_effective_entitlements(org: Org) -> Dict[str, Optional[int]]:
    """
    Returns effective entitlements (None = unlimited):
      - workspace_limit
      - template_limit
      - labels_limit
    NOTE: labels_limit is the unified key used everywhere in views/templates/pill.
    """
    sub: Optional[OrgSubscription] = getattr(org, "subscription", None)

    # defaults
    ent: Dict[str, Optional[int]] = {
        "workspace_limit": 0,
        "template_limit": 0,
        "labels_limit": 0,
    }

    # TRIAL = lifetime entitlements (no expiry)
    if sub and sub.status == OrgSubscription.STATUS_TRIAL:
        ent["workspace_limit"] = TRIAL_WORKSPACE_LIMIT
        ent["template_limit"] = TRIAL_TEMPLATE_LIMIT
        ent["labels_limit"] = TRIAL_LABELS_TOTAL

    # ACTIVE = plan-based entitlements
    elif sub and sub.status == OrgSubscription.STATUS_ACTIVE and sub.plan_version:
        pv = sub.plan_version
        ent["workspace_limit"] = pv.workspace_limit   # None => unlimited
        ent["template_limit"] = pv.template_limit     # None => unlimited
        ent["labels_limit"] = pv.labels_per_period    # None => unlimited

    # NONE/CANCELED = no entitlements
    else:
        ent["workspace_limit"] = 0
        ent["template_limit"] = 0
        ent["labels_limit"] = 0

    # Apply overrides ONLY when TRIAL or ACTIVE (so NONE stays blocked)
    ov: Optional[OrgLimitOverride] = getattr(org, "limit_override", None)
    if ov and sub and sub.status in (OrgSubscription.STATUS_TRIAL, OrgSubscription.STATUS_ACTIVE):
        if ov.workspace_limit_override is not None:
            ent["workspace_limit"] = ov.workspace_limit_override
        if ov.template_limit_override is not None:
            ent["template_limit"] = ov.template_limit_override
        # support either field name (in case your model used the older name)
        if hasattr(ov, "labels_limit_override") and ov.labels_limit_override is not None:
            ent["labels_limit"] = ov.labels_limit_override
        elif hasattr(ov, "labels_per_period_override") and ov.labels_per_period_override is not None:
            ent["labels_limit"] = ov.labels_per_period_override

    return ent

@transaction.atomic()
def get_labels_used(org: Org, now=None) -> int:
    now = now or timezone.now()
    sub = get_or_create_subscription(org)
    sub = refresh_subscription_state(sub, now=now)

    # TRIAL => lifetime usage
    if sub.status == OrgSubscription.STATUS_TRIAL:
        usage, _ = OrgUsageLifetime.objects.select_for_update().get_or_create(org=org)
        return int(usage.labels_generated_total or 0)

    # ACTIVE => period usage
    if sub.status == OrgSubscription.STATUS_ACTIVE and sub.current_period_start and sub.current_period_end:
        usage, _ = OrgUsagePeriod.objects.select_for_update().get_or_create(
            org=org,
            period_start=sub.current_period_start,
            defaults={"period_end": sub.current_period_end, "labels_generated": 0},
        )
        if usage.period_end != sub.current_period_end:
            usage.period_end = sub.current_period_end
            usage.save(update_fields=["period_end", "updated_at"])
        return int(usage.labels_generated or 0)

    return 0

@transaction.atomic()
def record_label_generation(org: Org, qty: int) -> None:
    qty = int(qty or 0)
    if qty <= 0:
        return

    now = timezone.now()
    sub = get_or_create_subscription(org)
    sub = refresh_subscription_state(sub, now=now)

    # TRIAL => lifetime usage
    if sub.status == OrgSubscription.STATUS_TRIAL:
        usage, _ = OrgUsageLifetime.objects.select_for_update().get_or_create(org=org)
        usage.labels_generated_total = int(usage.labels_generated_total or 0) + qty
        usage.save(update_fields=["labels_generated_total", "updated_at"])
        return

    # ACTIVE => period usage
    if sub.status == OrgSubscription.STATUS_ACTIVE and sub.current_period_start and sub.current_period_end:
        usage, _ = OrgUsagePeriod.objects.select_for_update().get_or_create(
            org=org,
            period_start=sub.current_period_start,
            defaults={"period_end": sub.current_period_end, "labels_generated": 0},
        )
        usage.labels_generated = int(usage.labels_generated or 0) + qty
        usage.save(update_fields=["labels_generated", "updated_at"])
        return

    return


def get_labels_remaining(org: Org) -> Optional[int]:
    ent = get_effective_entitlements(org)
    limit = ent.get("labels_limit")  # None => unlimited

    if limit is None:
        return None

    used = get_labels_used(org)
    return max(0, int(limit) - int(used))
