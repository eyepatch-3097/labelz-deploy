# billing/views.py
from __future__ import annotations

from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from accounts.models import User
from billing.models import (
    OrgSubscription,
    Plan,
    PlanVersion,
    SuperPlanRequest,
    OrgLimitOverride,
)
from billing.usage import get_effective_entitlements, get_or_create_subscription, refresh_subscription_state, get_labels_used

from workspaces.models import Workspace, LabelTemplate  # adjust if your import path differs


def _plan_code_from_sub(sub: OrgSubscription) -> str:
    if sub.status == OrgSubscription.STATUS_TRIAL:
        return "TRIAL"
    if sub.status == OrgSubscription.STATUS_ACTIVE and sub.plan_version and sub.plan_version.plan:
        return (sub.plan_version.plan.code or "").upper() or "NONE"
    return "NONE"


def _org_counts(org):
    ws_created = Workspace.objects.filter(org=org).count()
    tpl_created = LabelTemplate.objects.filter(workspace__org=org).count()
    return ws_created, tpl_created


def _labels_used_for_display(org, sub: OrgSubscription) -> int:
    
    return int(get_labels_used(org) or 0)


def _latest_pv(code: str):
    p = Plan.objects.filter(code=code, is_active=True).first()
    if not p:
        return None
    return PlanVersion.objects.filter(plan=p, is_active=True).order_by("-version").first()


@login_required
def billing_select_plan(request):
    user = request.user
    if not user.org:
        messages.error(request, "You are not linked to any organisation.")
        return redirect("dashboard")

    org = user.org
    sub = get_or_create_subscription(org)
    sub = refresh_subscription_state(sub)

    plan_code = _plan_code_from_sub(sub)
    ent = get_effective_entitlements(org)

    ws_created, tpl_created = _org_counts(org)

    ws_limit = ent.get("workspace_limit")          # None => unlimited
    tpl_limit = ent.get("template_limit")          # None => unlimited
    lbl_limit = ent.get("labels_limit")       # TRIAL=5 total, STARTER=3000, PRO=30000, SUPER=override

    labels_used = _labels_used_for_display(org, sub)
    lbl_remaining = None if lbl_limit is None else max(0, int(lbl_limit) - int(labels_used))

    # Show plan options (even if user can’t buy)
    starter_pv = _latest_pv("STARTER")
    pro_pv = _latest_pv("PRO")

    # POST = fake “buy” (Phase 3, no Razorpay)
    if request.method == "POST":
        if user.role != User.ROLE_ADMIN:
            messages.error(request, "Only admins can upgrade plans.")
            return redirect("billing_select_plan")

        target = (request.POST.get("plan_code") or "").strip().upper()
        if target not in ("STARTER", "PRO"):
            messages.error(request, "Invalid plan selection.")
            return redirect("billing_select_plan")

        target_pv = _latest_pv(target)
        if not target_pv:
            messages.error(request, "Plan not configured. Please contact support.")
            return redirect("billing_select_plan")

        now = timezone.now()
        sub.status = OrgSubscription.STATUS_ACTIVE
        sub.plan_version = target_pv
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)
        sub.cancel_at_period_end = False
        sub.save()

        messages.success(request, f"Activated {target} (fake purchase).")
        return redirect("dashboard")

    # admins should NOT see plan purchase options if already PRO/SUPER
    can_upgrade = (user.role == User.ROLE_ADMIN and plan_code not in ("PRO", "SUPER"))

    return render(request, "billing/select_plan.html", {
        "org": org,
        "sub": sub,
        "plan_code": plan_code,
        "can_upgrade": can_upgrade,

        "ws_limit": ws_limit,
        "ws_created": ws_created,
        "tpl_limit": tpl_limit,
        "tpl_created": tpl_created,
        "lbl_limit": lbl_limit,
        "lbl_used": labels_used,
        "lbl_remaining": lbl_remaining,

        "starter_pv": starter_pv,
        "pro_pv": pro_pv,
    })


@login_required
def billing_super_plan(request):
    user = request.user
    if not user.org:
        messages.error(request, "You are not linked to any organisation.")
        return redirect("dashboard")

    org = user.org
    sub = get_or_create_subscription(org)
    sub = refresh_subscription_state(sub)
    plan_code = _plan_code_from_sub(sub)

    ent = get_effective_entitlements(org)

    workspaces_created = Workspace.objects.filter(org=org).count()
    templates_created = LabelTemplate.objects.filter(workspace__org=org).count()

    labels_used = int(get_labels_used(org) or 0)
    labels_limit = ent.get("labels_limit")
    labels_remaining = None if labels_limit is None else max(0, int(labels_limit) - labels_used)

    pending = SuperPlanRequest.objects.filter(
        org=org, status=SuperPlanRequest.STATUS_PENDING
    ).order_by("-approved_at").first()

    if request.method == "POST":
        if user.role != User.ROLE_ADMIN:
            messages.error(request, "Only admins can request Super plan.")
            return redirect("billing_super_plan")

        if pending:
            messages.info(request, "You already have a pending Super request.")
            return redirect("billing_super_plan")

        raw = (request.POST.get("requested_labels") or "").strip()
        try:
            qty = int(raw)
        except ValueError:
            qty = 0

        if qty <= 0:
            messages.error(request, "Enter a valid label count.")
            return redirect("billing_super_plan")

        SuperPlanRequest.objects.create(
            org=org,
            requested_by=user,
            requested_labels=qty,
            status=SuperPlanRequest.STATUS_PENDING,
        )
        messages.success(request, "Super plan request submitted. Awaiting approval.")
        return redirect("billing_super_plan")

    return render(request, "billing/super_plan.html", {
        "org": org,
        "sub": sub,
        "ent": ent,
        "plan_code": plan_code,
        "pending": pending,
        "is_admin": (user.role == User.ROLE_ADMIN),
        "workspaces_created": workspaces_created,
        "templates_created": templates_created,
        "labels_used": labels_used,
        "labels_limit": labels_limit,
        "labels_remaining": labels_remaining,
    })