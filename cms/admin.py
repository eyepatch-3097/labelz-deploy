from django.contrib import admin
from django import forms
from .models import CMSPost


class CMSPostAdminForm(forms.ModelForm):
    class Meta:
        model = CMSPost
        fields = "__all__"
        widgets = {
            "blog_html": forms.Textarea(attrs={"rows": 18, "style": "font-family: ui-monospace;"}),
            "youtube_embed_html": forms.Textarea(attrs={"rows": 6, "style": "font-family: ui-monospace;"}),
            "video_description": forms.Textarea(attrs={"rows": 4}),
            "subtitle": forms.Textarea(attrs={"rows": 2}),
            "meta_description": forms.Textarea(attrs={"rows": 3}),
        }


@admin.register(CMSPost)
class CMSPostAdmin(admin.ModelAdmin):
    form = CMSPostAdminForm

    list_display = ("title", "type", "status", "published_at", "updated_at")
    list_filter = ("type", "status")
    search_fields = ("title", "subtitle", "slug", "meta_title")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at", "published_at")

    fieldsets = (
        ("Common", {
            "fields": ("type", "status", "title", "subtitle", "slug")
        }),
        ("SEO", {
            "fields": ("meta_title", "meta_description", "preview_image", "og_image")
        }),
        ("Blog Content (HTML)", {
            "fields": ("blog_html",),
            "classes": ("collapse",),
        }),
        ("Video", {
            "fields": ("video_description", "youtube_embed_html"),
            "classes": ("collapse",),
        }),
        ("Timestamps", {
            "fields": ("published_at", "created_at", "updated_at"),
        }),
    )
