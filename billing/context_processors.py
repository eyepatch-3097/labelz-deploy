# billing/context_processors.py
from datetime import timedelta
from django.utils import timezone

from accounts.models import User
from billing.models import OrgSubscription
from billing.usage import (
    get_or_create_subscription,
    refresh_subscription_state,
    get_effective_entitlements,
    get_labels_used,
)

def billing_summary(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not getattr(user, "org_id", None):
        return {}

    org = user.org
    sub = get_or_create_subscription(org)
    sub = refresh_subscription_state(sub)

    ent = get_effective_entitlements(org)
    labels_limit = ent.get("labels_limit")  # ✅ now always 5/3000/30000/0

    used = int(get_labels_used(org) or 0)
    remaining = None if labels_limit is None else max(0, int(labels_limit) - used)

    # Plan code/label
    plan_code = "NONE"
    plan_label = "NONE"

    if sub.status == OrgSubscription.STATUS_TRIAL:
        plan_code = "TRIAL"
        plan_label = "Free Trial"
    elif sub.status == OrgSubscription.STATUS_ACTIVE and sub.plan_version and sub.plan_version.plan:
        plan_code = (sub.plan_version.plan.code or "NONE").upper()
        plan_label = sub.plan_version.plan.name or plan_code
    else:
        plan_code = "NONE"
        plan_label = "NONE"

    

    is_admin = (user.role == User.ROLE_ADMIN)

    billing_can_upgrade = is_admin and plan_code in ("TRIAL", "STARTER", "NONE")
    billing_can_go_super = is_admin and plan_code == "PRO"

    return {
        "billing_plan_code": plan_code,
        "billing_plan_label": plan_label,
        "billing_labels_limit": labels_limit,
        "billing_labels_used": used,
        "billing_labels_remaining": remaining,
        "billing_can_upgrade": billing_can_upgrade,
        "billing_can_go_super": billing_can_go_super,
    }
