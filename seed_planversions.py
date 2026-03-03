from billing.models import Plan, PlanVersion
from django.db.models import Max

def upsert_planversion(plan_code, currency, amount_minor, ws, tpl, labels):
    plan = Plan.objects.get(code=plan_code)

    # Update latest PV for this currency if it exists
    pv = PlanVersion.objects.filter(plan=plan, currency__iexact=currency).order_by("-version").first()
    if pv:
        pv.amount_cents = amount_minor
        pv.workspace_limit = ws
        pv.template_limit = tpl
        pv.labels_per_period = labels
        pv.is_active = True
        pv.save()
        return pv

    # Otherwise create a new PV with next plan version (works with your current unique_together(plan, version))
    next_v = (PlanVersion.objects.filter(plan=plan).aggregate(Max("version"))["version__max"] or 0) + 1
    pv = PlanVersion.objects.create(
        plan=plan,
        version=next_v,
        currency=currency.upper(),
        amount_cents=amount_minor,
        workspace_limit=ws,
        template_limit=tpl,
        labels_per_period=labels,
        is_active=True,
        is_default=False,
    )
    return pv

# International (PayPal) USD
upsert_planversion("STARTER", "USD", 2900, 1, 3, 3000)        # $29
upsert_planversion("PRO", "USD", 6900, None, None, 30000)     # $69

# India (Razorpay) INR — store in paise
upsert_planversion("STARTER", "INR", 290000, 1, 3, 3000)      # ₹2900
upsert_planversion("PRO", "INR", 690000, None, None, 30000)   # ₹6900

print("Seeded/updated PlanVersions successfully.")
