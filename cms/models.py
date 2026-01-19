from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from .sanitize import sanitize_blog_html, sanitize_youtube_embed_html

class CMSPost(models.Model):
    TYPE_BLOG = "BLOG"
    TYPE_VIDEO = "VIDEO"
    TYPE_CHOICES = [
        (TYPE_BLOG, "Blog"),
        (TYPE_VIDEO, "Video"),
    ]

    STATUS_DRAFT = "DRAFT"
    STATUS_PUBLISHED = "PUBLISHED"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
    ]

    # Common
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_BLOG)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)

    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True, default="")
    slug = models.SlugField(max_length=240, unique=True, blank=True)

    meta_title = models.CharField(max_length=60, blank=True, default="")
    meta_description = models.CharField(max_length=160, blank=True, default="")

    preview_image = models.ImageField(upload_to="cms/previews/", blank=True, null=True)
    og_image = models.ImageField(upload_to="cms/og/", blank=True, null=True)

    # Blog fields
    blog_html = models.TextField(blank=True, default="")

    # Video fields
    video_description = models.TextField(blank=True, default="")
    youtube_embed_html = models.TextField(blank=True, default="")

    # Dates
    published_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return f"{self.get_type_display()}: {self.title}"

    def save(self, *args, **kwargs):
        # auto-slug
        if not self.slug:
            base = slugify(self.title)[:220] or "post"
            slug = base
            i = 2
            while CMSPost.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{i}"
                i += 1
            self.slug = slug

        # sanitize BEFORE saving
        if self.type == self.TYPE_BLOG:
            self.blog_html = sanitize_blog_html(self.blog_html)
        elif self.type == self.TYPE_VIDEO:
            self.youtube_embed_html = sanitize_youtube_embed_html(self.youtube_embed_html)

        # published timestamp
        if self.status == self.STATUS_PUBLISHED and not self.published_at:
            self.published_at = timezone.now()
        if self.status == self.STATUS_DRAFT:
            # keep published_at if you want "unpublish but preserve date" remove this line
            self.published_at = None

        super().save(*args, **kwargs)

    def clean(self):
        errors = {}

        if self.type == self.TYPE_BLOG:
            # required for blog
            if not (self.meta_title or "").strip():
                errors["meta_title"] = "Meta Title is required for a Blog."
            if not (self.meta_description or "").strip():
                errors["meta_description"] = "Meta Description is required for a Blog."
            if not self.preview_image:
                errors["preview_image"] = "Blog Preview Image is required for a Blog."
            if not self.og_image:
                errors["og_image"] = "Open Graph Image is required for a Blog."
            if not (self.blog_html or "").strip():
                errors["blog_html"] = "Blog Content (HTML) is required for a Blog."

        if self.type == self.TYPE_VIDEO:
            if not (self.video_description or "").strip():
                errors["video_description"] = "Video description is required."
            emb = (self.youtube_embed_html or "").strip()
            if not emb:
                errors["youtube_embed_html"] = "YouTube embed HTML is required."
            else:
                # minimal safety check: must contain youtube embed iframe
                low = emb.lower()
                if "<iframe" not in low or "youtube.com/embed" not in low:
                    errors["youtube_embed_html"] = "Please paste a valid YouTube iframe embed (youtube.com/embed...)."

        if errors:
            raise ValidationError(errors)
