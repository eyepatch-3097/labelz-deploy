from django.contrib.sitemaps import Sitemap
from .models import CMSPost

class CMSPostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return (
            CMSPost.objects
            .filter(status=CMSPost.STATUS_PUBLISHED)
            .order_by("-published_at", "-updated_at", "-id")
        )

    def lastmod(self, obj: CMSPost):
        # Google likes last modified; updated_at is safest
        return obj.updated_at or obj.published_at

from django.urls import reverse

class StaticViewSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        # Add public pages only
        return ["landing", "affiliate", "cms_content_list"]

    def location(self, item):
        return reverse(item)
