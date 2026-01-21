# billing/guards.py
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import redirect

from accounts.models import Org
from billing.models import OrgSubscription
from billing.usage import get_or_create_subscription, refresh_subscription_state


def get_plan_code(org: Org) -> str:
    """
    Returns: TRIAL / STARTER / PRO / SUPER / NONE
    """
    sub = get_or_create_subscription(org)
    sub = refresh_subscription_state(sub)

    if sub.status == OrgSubscription.STATUS_TRIAL:
        return "TRIAL"

    if sub.status == OrgSubscription.STATUS_ACTIVE and sub.plan_version and sub.plan_version.plan:
        return (sub.plan_version.plan.code or "").upper() or "NONE"

    return "NONE"


def limit_redirect(request, org: Org, msg: str = ""):
    """
    Routing rules:
    - TRIAL/STARTER/NONE => Upgrade page
    - PRO/SUPER => Super Plan page
    """
    code = get_plan_code(org)

    if msg:
        messages.error(request, msg)

    if code in ("PRO", "SUPER"):
        return redirect("billing_super_plan")
    return redirect("billing_select_plan")
