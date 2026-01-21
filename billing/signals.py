# billing/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import Org
from .models import OrgSubscription


@receiver(post_save, sender=Org)
def ensure_org_subscription(sender, instance: Org, created: bool, **kwargs):
    # For new orgs, always start in TRIAL
    if created:
        OrgSubscription.objects.get_or_create(org=instance, defaults={"status": OrgSubscription.STATUS_TRIAL})
