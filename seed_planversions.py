from django.core.management.base import BaseCommand
from django.db.models import Max

from billing.models import Plan, PlanVersion


class Command(BaseCommand):
    help = "Seed/Update billing PlanVersions for USD/INR monthly+annual."

    def handle(self, *args, **options):
        def ensure_plan(code, name):
            p, _ = Plan.objects.get_or_create(code=code, defaults={"name": name, "is_active": True})
            if p.name != name:
                p.name = name
                p.save(update_fields=["name"])
            if not p.is_active:
                p.is_active = True
                p.save(update_fields=["is_active"])
            return p

        def upsert_pv(plan_code, currency, billing_cycle, amount_minor, period_days, ws, tpl, labels):
            plan = Plan.objects.get(code=plan_code)
            currency = currency.upper().strip()
            billing_cycle = billing_cycle.upper().strip()

            pv = (
                PlanVersion.objects
                .filter(plan=plan, currency__iexact=currency, billing_cycle=billing_cycle)
                .order_by("-version")
                .first()
            )

            if pv:
                pv.amount_cents = int(amount_minor)
                pv.period_days = int(period_days)
                pv.workspace_limit = ws
                pv.template_limit = tpl
                pv.labels_per_period = labels
                pv.is_active = True
                pv.is_default = False
                pv.save()
                return pv, "updated"

            next_v = (
                PlanVersion.objects
                .filter(plan=plan, currency__iexact=currency, billing_cycle=billing_cycle)
                .aggregate(Max("version"))["version__max"] or 0
            ) + 1

            pv = PlanVersion.objects.create(
                plan=plan,
                version=next_v,
                currency=currency,
                billing_cycle=billing_cycle,
                period_days=int(period_days),
                amount_cents=int(amount_minor),
                workspace_limit=ws,
                template_limit=tpl,
                labels_per_period=labels,
                is_active=True,
                is_default=False,
            )
            return pv, "created"

        ensure_plan("STARTER", "Starter")
        ensure_plan("PRO", "Pro")

        targets = [
            # USD
            ("STARTER", "USD", "MONTHLY", 2900,    30,  1,    3,      3000),
            ("STARTER", "USD", "ANNUAL",  14900,   365, 1,    3,      36000),
            ("PRO",     "USD", "MONTHLY", 6900,    30,  None, None,   30000),
            ("PRO",     "USD", "ANNUAL",  44900,   365, None, None,   360000),

            # INR (paise)
            ("STARTER", "INR", "MONTHLY", 290000,  30,  1,    3,      3000),
            ("STARTER", "INR", "ANNUAL",  1490000, 365, 1,    3,      36000),
            ("PRO",     "INR", "MONTHLY", 690000,  30,  None, None,   30000),
            ("PRO",     "INR", "ANNUAL",  4490000, 365, None, None,   360000),
        ]

        for t in targets:
            pv, action = upsert_pv(*t)
            self.stdout.write(
                f"{action} {pv.plan.code} {pv.currency} {pv.billing_cycle} v{pv.version} "
                f"amount_minor={pv.amount_cents} days={pv.period_days} labels={pv.labels_per_period}"
            )

        self.stdout.write(self.style.SUCCESS("✅ PlanVersions seeded/updated."))