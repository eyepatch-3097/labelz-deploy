from django.db import migrations

def seed_plans(apps, schema_editor):
    Plan = apps.get_model("billing", "Plan")
    PlanVersion = apps.get_model("billing", "PlanVersion")

    starter, _ = Plan.objects.get_or_create(code="STARTER", defaults={"name": "Starter"})
    pro, _ = Plan.objects.get_or_create(code="PRO", defaults={"name": "Pro"})

    # Starter v1
    PlanVersion.objects.get_or_create(
        plan=starter, version=1,
        defaults=dict(
            currency="USD",
            amount_cents=1900,
            workspace_limit=1,
            template_limit=3,
            labels_per_period=3000,
            is_default=True,
            is_active=True,
        )
    )

    # Pro v1
    PlanVersion.objects.get_or_create(
        plan=pro, version=1,
        defaults=dict(
            currency="USD",
            amount_cents=6900,
            workspace_limit=None,
            template_limit=None,
            labels_per_period=30000,
            is_default=True,
            is_active=True,
        )
    )

class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(seed_plans, migrations.RunPython.noop),
    ]
