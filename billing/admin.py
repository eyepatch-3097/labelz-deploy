from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
from django.contrib import messages
from .models import SuperPlanRequest, OrgSubscription, OrgLimitOverride, Plan, PlanVersion


@admin.register(SuperPlanRequest)
class SuperPlanRequestAdmin(admin.ModelAdmin):
    list_display = ("org", "requested_labels", "status", "created_at", "approved_at")
    list_filter = ("status",)
    actions = ["approve_selected"]

    def approve_selected(self, request, queryset):
        count = 0
        for r in queryset:
            if r.status != SuperPlanRequest.STATUS_PENDING:
                continue
            r.grant_super(approved_by_user=request.user)
            count += 1
        self.message_user(request, f"Approved {count} request(s).", level=messages.SUCCESS)

    approve_selected.short_description = "Approve selected Super requests (grant Super)"

    def save_model(self, request, obj, form, change):
        # detect transition PENDING -> APPROVED via manual edit
        if change:
            old = SuperPlanRequest.objects.filter(pk=obj.pk).first()
            if old and old.status == SuperPlanRequest.STATUS_PENDING and obj.status == SuperPlanRequest.STATUS_APPROVED:
                # Save first so admin doesn't error on validation; then grant
                super().save_model(request, obj, form, change)
                obj.grant_super(approved_by_user=request.user)
                return

        super().save_model(request, obj, form, change)