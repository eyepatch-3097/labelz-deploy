# billing/views.py
from __future__ import annotations

from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
import razorpay, hmac, hashlib, json
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest
from accounts.models import User
from billing.models import (
    OrgSubscription,
    Plan,
    PlanVersion,
    SuperPlanRequest,
    OrgLimitOverride,
)
from billing.usage import get_effective_entitlements, get_or_create_subscription, refresh_subscription_state, get_labels_used
from django.db import transaction
from billing.models import PaymentEvent
from workspaces.models import Workspace, LabelTemplate  # adjust if your import path differs
from django.http import StreamingHttpResponse
from reportlab.pdfgen import canvas
from io import BytesIO
import csv

def _rupees(paise: int) -> int:
    return int(int(paise or 0) / 100)

@login_required
def billing_invoices_csv(request):
    user = request.user
    if not user.org or user.role != User.ROLE_ADMIN:
        return redirect("dashboard")

    org = user.org
    qs = PaymentEvent.objects.filter(org=org).order_by("-created_at")

    def rows():
        yield ["id","status","plan","amount_rupees","provider_order_id","provider_payment_id","created_at"]
        for p in qs:
            plan = p.plan_version.plan.code if p.plan_version and p.plan_version.plan else ""
            yield [
                str(p.id), p.status, plan,
                str(int((p.amount_cents or 0)/100)),
                p.provider_order_id, p.provider_payment_id,
                p.created_at.isoformat()
            ]

    def stream():
        out = BytesIO()
        w = csv.writer(out)
        for r in rows():
            out.seek(0); out.truncate(0)
            w.writerow(r)
            yield out.getvalue().decode("utf-8")

    resp = StreamingHttpResponse(stream(), content_type="text/csv")
    resp["Content-Disposition"] = f'attachment; filename="invoices_org_{org.id}.csv"'
    return resp

@login_required
def billing_invoice_pdf(request, payment_id: int):
    user = request.user
    if not user.org or user.role != User.ROLE_ADMIN:
        return redirect("dashboard")

    org = user.org
    p = PaymentEvent.objects.filter(org=org, id=payment_id).first()
    if not p:
        messages.error(request, "Invoice not found.")
        return redirect("billing_invoices")

    plan = p.plan_version.plan.code if p.plan_version and p.plan_version.plan else "—"
    amount_rupees = int((p.amount_cents or 0) / 100)

    buf = BytesIO()
    c = canvas.Canvas(buf)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 800, "Invoice")

    c.setFont("Helvetica", 11)
    c.drawString(50, 770, f"Org: {org.name} (ID {org.id})")
    c.drawString(50, 750, f"Invoice ID: INV-{org.id}-{p.id}")
    c.drawString(50, 730, f"Date: {p.created_at.strftime('%Y-%m-%d %H:%M')}")
    c.drawString(50, 710, f"Plan: {plan}")
    c.drawString(50, 690, f"Status: {p.status}")
    c.drawString(50, 670, f"Amount: ₹{amount_rupees}")

    if p.provider_order_id:
        c.drawString(50, 650, f"Razorpay Order: {p.provider_order_id}")
    if p.provider_payment_id:
        c.drawString(50, 630, f"Razorpay Payment: {p.provider_payment_id}")

    c.showPage()
    c.save()

    pdf = buf.getvalue()
    buf.close()

    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="INV-{org.id}-{p.id}.pdf"'
    return resp

@login_required
@transaction.atomic
def billing_cancel_plan(request):
    user = request.user
    if not user.org or user.role != User.ROLE_ADMIN:
        return redirect("dashboard")

    if request.method != "POST":
        return redirect("billing_invoices")

    org = user.org
    sub = OrgSubscription.objects.select_for_update().get(org=org)

    sub.status = OrgSubscription.STATUS_NONE
    sub.plan_version = None
    sub.current_period_start = None
    sub.current_period_end = None
    sub.cancel_at_period_end = False
    sub.save()

    # keep overrides cleared on cancel (so NONE stays blocked)
    ov = OrgLimitOverride.objects.filter(org=org).first()
    if ov:
        ov.workspace_limit_override = None
        ov.template_limit_override = None
        ov.labels_per_period_override = None
        ov.save()

    messages.success(request, "Plan canceled. You are now on NONE.")
    return redirect("billing_select_plan")

@login_required
def billing_invoices(request):
    user = request.user
    if not user.org:
        return redirect("dashboard")

    if user.role != User.ROLE_ADMIN:
        messages.error(request, "Only admins can access billing history.")
        return redirect("dashboard")

    org = user.org
    sub = refresh_subscription_state(get_or_create_subscription(org))
    plan_code = _plan_code_from_sub(sub)
    ent = get_effective_entitlements(org)

    ws_created, tpl_created = _org_counts(org)
    lbl_limit = ent.get("labels_limit")
    lbl_used = int(get_labels_used(org) or 0)
    lbl_remaining = None if lbl_limit is None else max(0, int(lbl_limit) - lbl_used)

    

    payments = PaymentEvent.objects.filter(org=org).order_by("-created_at")

    return render(request, "billing/invoices.html", {
        "org": org,
        "plan_code": plan_code,
        "ws_limit": ent.get("workspace_limit"),
        "tpl_limit": ent.get("template_limit"),
        "lbl_limit": lbl_limit,
        "lbl_used": lbl_used,
        "lbl_remaining": lbl_remaining,
        "ws_created": ws_created,
        "tpl_created": tpl_created,
        "payments": payments,
    })

@login_required
def billing_checkout_start(request):
    user = request.user
    if request.method != "POST":
        return redirect("billing_select_plan")

    if not user.org or user.role != User.ROLE_ADMIN:
        messages.error(request, "Only org admins can purchase plans.")
        return redirect("billing_select_plan")

    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        messages.error(request, "Razorpay keys are not configured.")
        return redirect("billing_select_plan")

    org = user.org
    sub = refresh_subscription_state(get_or_create_subscription(org))
    current_code = _plan_code_from_sub(sub)

    plan_code = (request.POST.get("plan_code") or "").strip().upper()
    if plan_code not in ("STARTER", "PRO"):
        messages.error(request, "Invalid plan.")
        return redirect("billing_select_plan")

    # If already PRO/SUPER -> route to super page
    if current_code in ("PRO", "SUPER"):
        return redirect("billing_super_plan")

    pv = _latest_pv(plan_code)
    if not pv or not pv.is_active:
        messages.error(request, "Plan not configured.")
        return redirect("billing_select_plan")

    if (pv.currency or "").upper() != "INR":
        messages.error(request, "Plan currency must be INR.")
        return redirect("billing_select_plan")

    amount_paise = int(pv.amount_cents or 0)
    if amount_paise <= 0:
        messages.error(request, "Plan price not set.")
        return redirect("billing_select_plan")

    client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))

    receipt = f"org_{org.id}_pv_{pv.id}_{int(timezone.now().timestamp())}"
    order = client.order.create({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "notes": {"org_id": str(org.id), "plan_code": plan_code, "plan_version_id": str(pv.id)},
    })

    pe = PaymentEvent.objects.create(
        org=org,
        created_by=user,
        plan_version=pv,
        currency="INR",
        amount_cents=amount_paise,
        status=PaymentEvent.STATUS_CREATED,
        provider="RAZORPAY",
        provider_order_id=order["id"],
    )

    return render(request, "billing/checkout.html", {
        "org": org,
        "plan_code": plan_code,
        "pv": pv,
        "payment_event": pe,
        "razorpay_key_id": settings.RAZORPAY_KEY_ID,
        "razorpay_order_id": order["id"],
        "amount_paise": amount_paise,
        "amount_rupees": int(amount_paise / 100),
        "currency": "INR",
    })

@login_required
@transaction.atomic
def billing_verify_payment(request):
    user = request.user
    if request.method != "POST" or not user.org:
        return redirect("billing_select_plan")

    org = user.org

    order_id = (request.POST.get("razorpay_order_id") or "").strip()
    payment_id = (request.POST.get("razorpay_payment_id") or "").strip()
    signature = (request.POST.get("razorpay_signature") or "").strip()

    if not (order_id and payment_id and signature):
        messages.error(request, "Payment verification failed.")
        return redirect("billing_select_plan")

    pe = PaymentEvent.objects.select_for_update().filter(org=org, provider_order_id=order_id).first()
    if not pe:
        messages.error(request, "Payment record not found.")
        return redirect("billing_select_plan")

    msg = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), msg, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(expected, signature):
        pe.status = PaymentEvent.STATUS_FAILED
        pe.provider_payment_id = payment_id
        pe.provider_signature = signature
        pe.save(update_fields=["status", "provider_payment_id", "provider_signature"])
        messages.error(request, "Payment signature mismatch.")
        return redirect("billing_select_plan")

    # Idempotent success
    if pe.status != PaymentEvent.STATUS_SUCCESS:
        pe.status = PaymentEvent.STATUS_SUCCESS
        pe.provider_payment_id = payment_id
        pe.provider_signature = signature
        pe.save(update_fields=["status", "provider_payment_id", "provider_signature"])

        sub = OrgSubscription.objects.select_for_update().get(org=org)
        now = timezone.now()
        sub.status = OrgSubscription.STATUS_ACTIVE
        sub.plan_version = pe.plan_version
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)
        sub.cancel_at_period_end = False
        sub.save()

        # Clear overrides when buying fixed plans
        ov = OrgLimitOverride.objects.filter(org=org).first()
        if ov:
            ov.workspace_limit_override = None
            ov.template_limit_override = None
            ov.labels_per_period_override = None
            ov.save()

    messages.success(request, "Payment successful. Plan activated.")
    return redirect("dashboard")

@csrf_exempt
def razorpay_webhook(request):
    if request.method != "POST":
        return HttpResponse(status=405)

    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        return HttpResponseBadRequest("Webhook secret not set")

    body = request.body
    received = request.headers.get("X-Razorpay-Signature", "")

    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        return HttpResponse(status=400)

    payload = json.loads(body.decode("utf-8"))
    event = payload.get("event", "")

    if event == "payment.captured":
        ent = payload["payload"]["payment"]["entity"]
        order_id = ent.get("order_id", "")
        payment_id = ent.get("id", "")

        pe = PaymentEvent.objects.filter(provider_order_id=order_id).first()
        if pe and pe.status != PaymentEvent.STATUS_SUCCESS:
            with transaction.atomic():
                pe = PaymentEvent.objects.select_for_update().get(id=pe.id)
                if pe.status != PaymentEvent.STATUS_SUCCESS:
                    pe.status = PaymentEvent.STATUS_SUCCESS
                    pe.provider_payment_id = payment_id
                    pe.save(update_fields=["status", "provider_payment_id"])

                    org = pe.org
                    sub = OrgSubscription.objects.select_for_update().get(org=org)
                    now = timezone.now()
                    sub.status = OrgSubscription.STATUS_ACTIVE
                    sub.plan_version = pe.plan_version
                    sub.current_period_start = now
                    sub.current_period_end = now + timedelta(days=30)
                    sub.cancel_at_period_end = False
                    sub.save()

                    ov = OrgLimitOverride.objects.filter(org=org).first()
                    if ov:
                        ov.workspace_limit_override = None
                        ov.template_limit_override = None
                        ov.labels_per_period_override = None
                        ov.save()

    return HttpResponse(status=200)

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

    starter_price = _rupees(starter_pv.amount_cents) if starter_pv else 0
    pro_price = _rupees(pro_pv.amount_cents) if pro_pv else 0

    # POST = fake “buy” (Phase 3, no Razorpay)
    
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
        "starter_price": starter_price,
        "pro_price": pro_price,
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