from django.db import models
from django.utils import timezone

class LabelzKBEntry(models.Model):
    CATEGORY_GENERAL = "GENERAL"
    CATEGORY_PRICING = "PRICING"
    CATEGORY_FEATURES = "FEATURES"
    CATEGORY_COMPLIANCE = "COMPLIANCE"
    CATEGORY_SUPPORT = "SUPPORT"

    CATEGORY_CHOICES = [
        (CATEGORY_GENERAL, "General"),
        (CATEGORY_PRICING, "Pricing"),
        (CATEGORY_FEATURES, "Features"),
        (CATEGORY_COMPLIANCE, "Compliance"),
        (CATEGORY_SUPPORT, "Support"),
    ]

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL)
    tags = models.CharField(max_length=300, blank=True, help_text="Comma-separated tags (optional)")
    content = models.TextField()
    is_active = models.BooleanField(default=True)

    # Optional: "pin" always-included snippets (keep short!)
    is_pinned = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.category})"


class ImportantLink(models.Model):
    title = models.CharField(max_length=200)
    url = models.URLField()
    description = models.TextField(blank=True)
    tags = models.CharField(max_length=300, blank=True, help_text="Comma-separated tags (optional)")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.title
