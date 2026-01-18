import uuid
import random
import string
import csv
import hashlib
from django.conf import settings
from django.db import models
from django.utils.text import slugify
from accounts.models import Org, User
from django.utils import timezone
from django.utils.text import slugify


def generate_workspace_code(org: Org) -> str:
    base = org.name or org.domain or "WSP"
    letters = ''.join(ch for ch in base if ch.isalnum())
    prefix = (letters[:3] or "WSP").upper()

    rand_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    hash_part = uuid.uuid4().hex[:6].upper()

    return f"{prefix}{rand_part}{hash_part}"


class Workspace(models.Model):
    org = models.ForeignKey(Org, related_name='workspaces', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    workspace_code = models.CharField(max_length=64, unique=True, blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='created_workspaces',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # whether this workspace had an initial template file
    template_file = models.FileField(upload_to='workspace_templates/', blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.org.name})"

    def save(self, *args, **kwargs):
        if not self.workspace_code and self.org_id:
            self.workspace_code = generate_workspace_code(self.org)
        super().save(*args, **kwargs)


class WorkspaceField(models.Model):
    FIELD_TEXT = 'TEXT'
    FIELD_IMAGE_URL = 'IMAGE_URL'
    FIELD_PRICE = 'PRICE'
    FIELD_SERIAL = 'SERIAL'
    FIELD_BARCODE = 'BARCODE'
    FIELD_QR = 'QRCODE'
    FIELD_STATIC_TEXT = 'STATIC_TEXT'
    FIELD_SHAPE = 'SHAPE'

    FIELD_TYPE_CHOICES = [
        (FIELD_TEXT, 'Text'),
        (FIELD_IMAGE_URL, 'Image URL'),
        (FIELD_PRICE, 'Price'),
        (FIELD_SERIAL, 'Serial Number'),
        (FIELD_BARCODE, 'Barcode'),
        (FIELD_QR, 'QR Code'),
        (FIELD_STATIC_TEXT, 'Static Text'),
        (FIELD_SHAPE, 'Shape'),
    ]

    workspace = models.ForeignKey(Workspace, related_name='fields', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    key = models.CharField(max_length=255)  # internal key (slugged)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)

    # If originated from uploaded file, keep original column header
    source_header = models.CharField(max_length=255, blank=True, null=True)

    # Simple positioning on canvas
    x = models.IntegerField(default=10)
    y = models.IntegerField(default=10)
    width = models.IntegerField(default=160)
    height = models.IntegerField(default=32)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('workspace', 'key')
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.name} [{self.field_type}]"

class WorkspaceMembership(models.Model):
    ROLE_ADMIN = 'ADMIN'
    ROLE_USER = 'USER'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_USER, 'User'),
    ]

    workspace = models.ForeignKey(
        Workspace,
        related_name='memberships',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        related_name='workspace_memberships',
        on_delete=models.CASCADE,
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default=ROLE_USER,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('workspace', 'user')
        ordering = ['workspace', 'user']

    def __str__(self):
        return f"{self.user.email} @ {self.workspace.name} ({self.get_role_display()})"


class OrgRoleChangeLog(models.Model):
    org = models.ForeignKey(
        Org,
        related_name='role_change_logs',
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        User,
        related_name='role_change_logs',
        on_delete=models.CASCADE,
    )
    previous_role = models.CharField(max_length=20)
    new_role = models.CharField(max_length=20)
    changed_by = models.ForeignKey(
        User,
        related_name='role_changes_made',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']

    def __str__(self):
        return f"{self.user.email}: {self.previous_role} → {self.new_role} at {self.changed_at}"

def generate_template_code(workspace, name: str) -> str:
    """
    Generate a template code like ORGWRKLAB12AB.
    """
    if workspace.org and workspace.org.name:
        org_prefix = workspace.org.name[:3].upper()
    else:
        org_prefix = "ORG"

    ws_prefix = workspace.name[:3].upper() or "WS"

    base = f"{org_prefix}{ws_prefix}{name[:3].upper() or 'TPL'}"
    rand_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    hash_suffix = hashlib.sha1(f"{base}{rand_part}".encode("utf-8")).hexdigest()[:3].upper()
    return base + rand_part + hash_suffix


class LabelTemplate(models.Model):
    CATEGORY_APPAREL = 'APPAREL'
    CATEGORY_FOOTWEAR = 'FOOTWEAR'
    CATEGORY_CANDLES = 'CANDLES'
    CATEGORY_IDOLS = 'IDOLS'
    CATEGORY_HOME_DECOR = 'HOME_DECOR'
    CATEGORY_HOME_FURNISHING = 'HOME_FURNISHING'
    CATEGORY_FMCG = 'FMCG'
    CATEGORY_ELECTRONICS = 'ELECTRONICS'
    CATEGORY_JEWELLERY = 'JEWELLERY'
    CATEGORY_BEAUTY = 'BEAUTY'
    CATEGORY_EQUIPMENTS = 'EQUIPMENTS'
    CATEGORY_SUPPLIES = 'SUPPLIES'
    CATEGORY_OTHERS = 'OTHERS'

    CATEGORY_CHOICES = [
        (CATEGORY_APPAREL, 'Apparel'),
        (CATEGORY_FOOTWEAR, 'Footwear'),
        (CATEGORY_CANDLES, 'Candles'),
        (CATEGORY_IDOLS, 'Idols'),
        (CATEGORY_HOME_DECOR, 'Home Decor'),
        (CATEGORY_HOME_FURNISHING, 'Home Furnishing'),
        (CATEGORY_FMCG, 'FMCG'),
        (CATEGORY_ELECTRONICS, 'Electronics'),
        (CATEGORY_JEWELLERY, 'Jewellery'),
        (CATEGORY_BEAUTY, 'Beauty & Cosmetics'),
        (CATEGORY_EQUIPMENTS, 'Equipments'),
        (CATEGORY_SUPPLIES, 'Supplies'),
        (CATEGORY_OTHERS, 'Others'),
    ]

    workspace = models.ForeignKey(
        Workspace,
        related_name='label_templates',
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    width_cm = models.DecimalField(max_digits=5, decimal_places=2)
    height_cm = models.DecimalField(max_digits=5, decimal_places=2)
    dpi = models.PositiveIntegerField(default=300)
    canvas_bg_color = models.CharField(max_length=20, default="#ffffff", blank=True)
    layout_json = models.JSONField(default=dict, blank=True)
    print_defaults = models.JSONField(default=dict, blank=True)  # optional but recommended
    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_OTHERS,
    )
    custom_category = models.CharField(max_length=50, blank=True)

    is_base = models.BooleanField(default=False)
    template_code = models.CharField(max_length=30, unique=True, blank=True)

    created_by = models.ForeignKey(
        User,
        related_name='created_label_templates',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_base', 'name']

    def __str__(self):
        base = f"{self.workspace.name}: {self.name}"
        if self.is_base:
            return f"{base} (Base)"
        return base

    def save(self, *args, **kwargs):
        if not self.template_code and self.workspace_id and self.name:
            self.template_code = generate_template_code(self.workspace, self.name)
        super().save(*args, **kwargs)


class LabelTemplateField(models.Model):
    template = models.ForeignKey(
        LabelTemplate,
        related_name='fields',
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=100)
    key = models.CharField(max_length=100)
    field_type = models.CharField(
        max_length=20,
        choices=WorkspaceField.FIELD_TYPE_CHOICES,
        default=WorkspaceField.FIELD_TEXT,
    )
    

    # Canvas layout in pixels (we’ll map from cm+dpi on the front-end)
    x = models.IntegerField(default=0)
    y = models.IntegerField(default=0)
    width = models.IntegerField(default=100)
    height = models.IntegerField(default=24)
    # Optional reference back to workspace field (for variables defined at workspace level)
    # Layering
    z_index = models.IntegerField(default=0)
    # Formatting
    font_family = models.CharField(max_length=50, default="Inter", blank=True)
    font_size = models.PositiveIntegerField(default=14)
    font_bold = models.BooleanField(default=False)
    font_italic = models.BooleanField(default=False)
    font_underline = models.BooleanField(default=False)
    ALIGN_LEFT = "left"
    ALIGN_CENTER = "center"
    ALIGN_RIGHT = "right"
    TEXT_ALIGN_CHOICES = [
        (ALIGN_LEFT, "Left"),
        (ALIGN_CENTER, "Center"),
        (ALIGN_RIGHT, "Right"),
    ]
    text_align = models.CharField(max_length=10, choices=TEXT_ALIGN_CHOICES, default=ALIGN_LEFT)

    text_color = models.CharField(max_length=20, default="#000000", blank=True)
    bg_color = models.CharField(max_length=20, default="transparent", blank=True)

    show_label = models.BooleanField(default=True)

    # Shape props (used when field_type == SHAPE)
    SHAPE_RECT = "RECT"
    SHAPE_CIRCLE = "CIRCLE"
    SHAPE_TRIANGLE = "TRIANGLE"
    SHAPE_STAR = "STAR"
    SHAPE_TYPE_CHOICES = [
        (SHAPE_RECT, "Rectangle"),
        (SHAPE_CIRCLE, "Circle"),
        (SHAPE_TRIANGLE, "Triangle"),
        (SHAPE_STAR, "Star"),
    ]
    shape_type = models.CharField(max_length=20, choices=SHAPE_TYPE_CHOICES, default=SHAPE_RECT, blank=True)
    shape_color = models.CharField(max_length=20, default="#000000", blank=True)


    workspace_field = models.ForeignKey(
        WorkspaceField,
        related_name='template_fields',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    order = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('template','key')
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.template.name}: {self.name}"

class GlobalTemplate(models.Model):
    """
    A super template defined by superadmin, visible to all orgs as a
    recommended template. Not tied to any workspace.
    """
    CATEGORY_CHOICES = LabelTemplate.CATEGORY_CHOICES  # reuse

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    width_cm = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    height_cm = models.DecimalField(max_digits=5, decimal_places=2, default=5)
    dpi = models.PositiveIntegerField(default=300)

    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default="other",
    )
    custom_category = models.CharField(max_length=100, blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="global_templates_created",
    )
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class GlobalTemplateField(models.Model):
    """
    Fields / layout for a GlobalTemplate.
    """
    template = models.ForeignKey(
        GlobalTemplate,
        on_delete=models.CASCADE,
        related_name="fields",
    )

    name = models.CharField(max_length=100)
    key = models.SlugField(max_length=100)
    field_type = models.CharField(
        max_length=20,
        choices=WorkspaceField.FIELD_TYPE_CHOICES,
    )

    x = models.IntegerField(default=0)
    y = models.IntegerField(default=0)
    width = models.IntegerField(default=140)
    height = models.IntegerField(default=32)
    order = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.template.name} – {self.name}"

class LabelBatch(models.Model):
    MODE_SINGLE = "SINGLE"
    MODE_MULTI = "MULTI"

    MODE_CHOICES = [
        (MODE_SINGLE, "Single SKU"),
        (MODE_MULTI, "Multiple SKUs"),
    ]

    workspace = models.ForeignKey(
        "Workspace",
        on_delete=models.CASCADE,
        related_name="label_batches",
    )
    template = models.ForeignKey(
        "LabelTemplate",
        on_delete=models.CASCADE,
        related_name="label_batches",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_label_batches",
    )

    mode = models.CharField(
        max_length=16,
        choices=MODE_CHOICES,
        default=MODE_SINGLE,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # Product codes
    ean_code = models.CharField(max_length=64, blank=True, default="")
    gs1_code = models.CharField(max_length=64, blank=True, default="")
    quantity = models.PositiveIntegerField(default=1)

    # User-supplied values for non-barcode/QR fields (by field.key)
    field_values = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Batch #{self.id} – {self.template.name} ({self.quantity} labels)"

class LabelBatchItem(models.Model):
    batch = models.ForeignKey(
        "LabelBatch",
        on_delete=models.CASCADE,
        related_name="items",
    )

    row_index = models.PositiveIntegerField(default=1)  # 1..N
    ean_code = models.CharField(max_length=64)
    gs1_code = models.CharField(max_length=64, blank=True, default="")
    quantity = models.PositiveIntegerField(default=1)

    # variable values for this row (by template field key)
    field_values = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["row_index", "id"]

    def __str__(self):
        return f"Batch #{self.batch_id} Row {self.row_index}"
