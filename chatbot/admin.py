from django.contrib import admin
from .models import LabelzKBEntry, ImportantLink

@admin.register(LabelzKBEntry)
class LabelzKBEntryAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_active", "is_pinned", "updated_at")
    list_filter = ("category", "is_active", "is_pinned")
    search_fields = ("title", "tags", "content")
    ordering = ("-is_pinned", "-updated_at")

@admin.register(ImportantLink)
class ImportantLinkAdmin(admin.ModelAdmin):
    list_display = ("title", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("title", "tags", "description", "url")
    ordering = ("-created_at",)