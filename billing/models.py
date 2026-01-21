# billing/models.py
from __future__ import annotations

from datetime import timedelta
from django.conf import settings
from django.db import models
from django.utils import timezone

from accounts.models import Org
from django.db import transaction


class Plan(models.Model):
    code = models.CharField(max_length=32, unique=True)  # STARTER, PRO, SUPER
    name = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class PlanVersion(models.Model):
    """
    Versioned pricing + entitlements.
    When pricing/limits change later, create a NEW PlanVersion row.
    Existing orgs remain on their plan_version until changed.
    """
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="versions")
    version = models.PositiveIntegerField(default=1)

    currency = models.CharField(max_length=8, default="USD")
    amount_cents = models.PositiveIntegerField(default=0)

    # Entitlements: None = unlimited
    workspace_limit = models.PositiveIntegerField(null=True, blank=True)
    template_limit = models.PositiveIntegerField(null=True, blank=True)
    labels_per_period = models.PositiveIntegerField(null=True, blank=True)

    # future mapping
    razorpay_plan_id = models.CharField(max_length=128, blank=True, default="")

    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("plan", "version")]
        ordering = ["plan__code", "-version"]

    def __str__(self) -> str:
        return f"{self.plan.code} v{self.version} ({self.currency} {self.amount_cents/100:.2f})"


class OrgSubscription(models.Model):
    STATUS_TRIAL = "TRIAL"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_NONE = "NONE"
    STATUS_CANCELED = "CANCELED"

    STATUS_CHOICES = [
        (STATUS_TRIAL, "Free Trial"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_NONE, "None"),
        (STATUS_CANCELED, "Canceled"),
    ]

    org = models.OneToOneField(Org, on_delete=models.CASCADE, related_name="subscription")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_TRIAL)

    # For ACTIVE subscriptions
    plan_version = models.ForeignKey(
        PlanVersion, null=True, blank=True, on_delete=models.SET_NULL, related_name="org_subscriptions"
    )
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)

    cancel_at_period_end = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def ensure_paid_period(self, now=None):
        """
        ACTIVE plans are 30 days from payment success.
        If no period exists, set it.
        If period is expired, the plan should later become NONE (handled in usage.refresh).
        """
        now = now or timezone.now()
        if self.status != self.STATUS_ACTIVE:
            return

        if not self.current_period_start or not self.current_period_end:
            self.current_period_start = now
            self.current_period_end = now + timedelta(days=30)

    def __str__(self) -> str:
        return f"{self.org_id} - {self.status}"


class OrgUsageLifetime(models.Model):
    """
    Lifetime usage for TRIAL (no time window).
    """
    org = models.OneToOneField(Org, on_delete=models.CASCADE, related_name="usage_lifetime")
    labels_generated_total = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.org_id} lifetime labels={self.labels_generated_total}"


class OrgUsagePeriod(models.Model):
    """
    Period usage for paid plans (STARTER/PRO/SUPER): current 30-day window.
    """
    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="usage_periods")
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()

    labels_generated = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("org", "period_start")]
        ordering = ["-period_start"]

    def __str__(self) -> str:
        return f"{self.org_id} {self.period_start.date()} labels={self.labels_generated}"


class PaymentEvent(models.Model):
    """
    Placeholder ledger for Phase 1 (real Razorpay fields later).
    """
    STATUS_CREATED = "CREATED"
    STATUS_SUCCESS = "SUCCESS"
    STATUS_FAILED = "FAILED"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Created"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="payment_events")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)

    plan_version = models.ForeignKey(PlanVersion, null=True, blank=True, on_delete=models.SET_NULL)
    currency = models.CharField(max_length=8, default="USD")
    amount_cents = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_CREATED)
    provider = models.CharField(max_length=32, default="RAZORPAY")

    provider_order_id = models.CharField(max_length=128, default="", blank=True)   # NEW
    provider_payment_id = models.CharField(max_length=128, default="", blank=True)
    provider_signature = models.CharField(max_length=256, default="", blank=True) # NEW (optional)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.org_id} {self.status} {self.amount_cents/100:.2f}"

class SuperPlanRequest(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    org = models.ForeignKey(Org, on_delete=models.CASCADE, related_name="super_requests")
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    requested_labels = models.PositiveIntegerField(default=0)

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="approved_super_requests"
    )
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def _get_or_create_super_pv(self):
        from .models import Plan, PlanVersion  # avoid circular imports

        plan, _ = Plan.objects.get_or_create(
            code="SUPER",
            defaults={"name": "Super", "is_active": True},
        )

        pv = PlanVersion.objects.filter(plan=plan, is_active=True).order_by("-version").first()
        if pv:
            return pv

        # Super plan has no fixed labels cap; we store per-org in override
        return PlanVersion.objects.create(
            plan=plan,
            version=1,
            currency="USD",
            amount_cents=0,
            workspace_limit=None,
            template_limit=None,
            labels_per_period=None,
            is_default=False,
            is_active=True,
        )

    @transaction.atomic()
    def grant_super(self, approved_by_user=None):
        """
        Grants SUPER for 30 days from now and sets per-org label limit = requested_labels.
        """
        if self.status != self.STATUS_PENDING:
            return  # already handled

        if self.requested_labels <= 0:
            raise ValueError("Requested labels must be > 0")

        from .models import OrgSubscription, OrgLimitOverride  # local import

        now = timezone.now()
        super_pv = self._get_or_create_super_pv()

        sub, _ = OrgSubscription.objects.select_for_update().get_or_create(org=self.org)
        sub.status = OrgSubscription.STATUS_ACTIVE
        sub.plan_version = super_pv
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)
        sub.cancel_at_period_end = False
        sub.save()

        ov, _ = OrgLimitOverride.objects.select_for_update().get_or_create(org=self.org)

        # make SUPER unlimited ws/templates
        ov.workspace_limit_override = None
        ov.template_limit_override = None

        # set SUPER label cap for 30 days
        if hasattr(ov, "labels_limit_override"):
            ov.labels_limit_override = int(self.requested_labels)
        else:
            ov.labels_per_period_override = int(self.requested_labels)

        ov.save()

        self.status = self.STATUS_APPROVED
        self.approved_by = approved_by_user
        self.approved_at = now
        self.save(update_fields=["status", "approved_by", "approved_at"])

class OrgLimitOverride(models.Model):
    """
    Superadmin override: if set (non-null), overrides plan entitlements.
    """
    org = models.OneToOneField(Org, on_delete=models.CASCADE, related_name="limit_override")

    workspace_limit_override = models.PositiveIntegerField(null=True, blank=True)
    template_limit_override = models.PositiveIntegerField(null=True, blank=True)
    labels_per_period_override = models.PositiveIntegerField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Overrides for {self.org_id}"