import csv
from io import TextIOWrapper
import os
from django.contrib import messages
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.text import slugify
from django.db.models import Q
from django.views.decorators.http import require_POST
from accounts.models import User
from .models import Workspace, WorkspaceField, WorkspaceMembership, OrgRoleChangeLog, LabelTemplate, LabelTemplateField, GlobalTemplate, GlobalTemplateField, LabelBatch
from .forms import WorkspaceCreateStep1Form, ManualFieldsForm, LabelTemplateForm, TemplateDuplicateForm, GlobalTemplateForm
import json
from .utils.label_codes import make_barcode_png, make_qr_png
from decimal import Decimal
from .utils.layout_engine import save_layout_to_template, load_layout_from_template, canvas_ui_size, compute_label_engine, ui_to_real, real_to_ui, get_ui_px_per_cm
from django.db import transaction
import math
from django.utils.safestring import mark_safe

WIZARD_SESSION_KEY = 'workspace_wizard'
UI_MAX_SIDE_PX = 700.0  # single source of truth

def input_fields_from_items(items):
    input_fields = []
    for it in items or []:
        ft = (it.get("field_type") or "").upper()
        key = (it.get("key") or "").strip()
        if not key:
            continue
        if ft in ("TEXT", "PRICE", "IMAGE_URL"):
            input_fields.append({
                "name": it.get("name") or key,
                "key": key,
                "field_type": ft,
            })
    return input_fields

def ui_sizes_for_template(template):
    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)
    max_side = max(width_cm, height_cm) or 1.0
    ui_px_per_cm = UI_MAX_SIDE_PX / max_side
    ui_w = int(round(width_cm * ui_px_per_cm))
    ui_h = int(round(height_cm * ui_px_per_cm))
    return width_cm, height_cm, ui_px_per_cm, ui_w, ui_h


def load_layout_ui(request, template):
    """
    Single source of truth:
    1) Use session layout saved from canvas
    2) fallback to DB only if session is absent
    """
    session_key = f"template_layout_{template.id}"
    raw = request.session.get(session_key)

    if raw:
        try:
            layout = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(layout, list):
                return layout
        except Exception:
            pass

    # fallback DB (will not include SHAPE/STATIC_TEXT unless you persist them in DB)
    fields = LabelTemplateField.objects.filter(template=template).order_by("order", "id")
    layout = []
    for f in fields:
        layout.append({
            "name": f.name,
            "key": f.key,
            "field_type": (f.field_type or "TEXT").upper(),
            "workspace_field_id": f.workspace_field_id,
            "x": int(f.x or 0),
            "y": int(f.y or 0),
            "width": int(f.width or 100),
            "height": int(f.height or 24),

            "z_index": getattr(f, "z_index", 0) or 0,
            "font_family": getattr(f, "font_family", "Inter") or "Inter",
            "font_size": int(getattr(f, "font_size", 14) or 14),
            "font_bold": bool(getattr(f, "font_bold", False)),
            "font_italic": bool(getattr(f, "font_italic", False)),
            "font_underline": bool(getattr(f, "font_underline", False)),
            "text_align": getattr(f, "text_align", "left") or "left",
            "text_color": getattr(f, "text_color", "#000000") or "#000000",
            "bg_color": getattr(f, "bg_color", "transparent") or "transparent",
            "show_label": bool(getattr(f, "show_label", True)),

            "shape_type": getattr(f, "shape_type", "RECT") or "RECT",
            "shape_color": getattr(f, "shape_color", "#000000") or "#000000",
            "static_value": getattr(f, "static_value", "") or "",
        })
    return layout


def prepare_ui_items(layout_ui, values_by_key, barcode_value, barcode_img, qr_value, qr_img):
    """
    Converts the raw layout into render-ready items (UI px),
    applying value + type handling consistently.
    """
    items = []
    for it in layout_ui:
        ft = (it.get("field_type") or "TEXT").upper()
        key = (it.get("key") or "").strip()

        item = dict(it)
        item["field_type"] = ft

        if ft == "BARCODE":
            item["value"] = barcode_value
            item["image_data_url"] = barcode_img
        elif ft == "QRCODE":
            item["value"] = qr_value
            item["image_data_url"] = qr_img
        elif ft == "IMAGE_URL":
            item["value"] = (values_by_key.get(key, "") or "").strip()
        elif ft == "STATIC_TEXT":
            item["value"] = (it.get("static_value") or it.get("name") or "")
        elif ft == "SHAPE":
            item["value"] = ""
        else:
            item["value"] = (values_by_key.get(key, "") or "").strip()

        items.append(item)

    # Layering: always by z_index, stable
    items.sort(key=lambda x: int(x.get("z_index", 0) or 0))
    return items


def ui_px_to_mm(px, ui_px_per_cm):
    return (float(px) / float(ui_px_per_cm or 1.0)) * 10.0


def prepare_print_items_from_ui(ui_items, ui_px_per_cm):
    """
    Convert UI px items to mm items for print, without changing look.
    """
    out = []
    for it in ui_items:
        item = dict(it)
        item["left_mm"] = ui_px_to_mm(int(it.get("x", 0) or 0), ui_px_per_cm)
        item["top_mm"] = ui_px_to_mm(int(it.get("y", 0) or 0), ui_px_per_cm)
        item["width_mm"] = ui_px_to_mm(int(it.get("width", 1) or 1), ui_px_per_cm)
        item["height_mm"] = ui_px_to_mm(int(it.get("height", 1) or 1), ui_px_per_cm)

        # font size must visually match UI -> convert px to mm
        fs_px = int(it.get("font_size", 14) or 14)
        item["font_mm"] = max(0.6, ui_px_to_mm(fs_px, ui_px_per_cm))

        out.append(item)

    out.sort(key=lambda x: int(x.get("z_index", 0) or 0))
    return out

def cm_to_px(cm: float, dpi: int) -> int:
    # 1 inch = 2.54 cm
    return int(round((float(cm) / 2.54) * int(dpi)))

def get_wizard(request):
    return request.session.get(WIZARD_SESSION_KEY, {})


def save_wizard(request, data):
    request.session[WIZARD_SESSION_KEY] = data
    request.session.modified = True


def clear_wizard(request):
    if WIZARD_SESSION_KEY in request.session:
        del request.session[WIZARD_SESSION_KEY]
        request.session.modified = True

def _compute_sizes(template: LabelTemplate):
    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)
    dpi = int(getattr(template, "dpi", 300) or 300)

    real_px_per_cm = dpi / 2.54
    export_w_px = int(round(width_cm * real_px_per_cm))
    export_h_px = int(round(height_cm * real_px_per_cm))

    max_side = max(width_cm, height_cm) or 1.0
    ui_px_per_cm = UI_MAX_SIDE_PX / max_side
    ui_w = int(round(width_cm * ui_px_per_cm))
    ui_h = int(round(height_cm * ui_px_per_cm))

    real_to_ui = ui_px_per_cm / real_px_per_cm
    ui_to_real = 1.0 / real_to_ui

    return {
        "width_cm": width_cm,
        "height_cm": height_cm,
        "dpi": dpi,
        "real_px_per_cm": real_px_per_cm,
        "export_w_px": export_w_px,
        "export_h_px": export_h_px,
        "ui_px_per_cm": ui_px_per_cm,
        "ui_w": ui_w,
        "ui_h": ui_h,
        "real_to_ui": real_to_ui,
        "ui_to_real": ui_to_real,
    }


def _load_layout_from_session_or_db(request, template: LabelTemplate):
    """
    Prefer session layout (latest WYSIWYG). Fallback to DB fields if session missing.
    Returns list of dict items (unknown unit: could be UI px or REAL px depending on your save pipeline).
    """
    session_key = f"template_layout_{template.id}"
    raw = request.session.get(session_key)
    if raw:
        try:
            layout = json.loads(raw)
            if isinstance(layout, list):
                return layout
        except Exception:
            pass

    # Fallback to DB
    fields = LabelTemplateField.objects.filter(template=template).order_by("order", "id")
    layout = []
    for f in fields:
        layout.append({
            "name": f.name,
            "key": f.key,
            "field_type": (f.field_type or "TEXT").upper(),
            "x": int(f.x or 0),
            "y": int(f.y or 0),
            "width": int(f.width or 1),
            "height": int(f.height or 1),

            # formatting (only if columns exist in your DB; safe getattr)
            "z_index": int(getattr(f, "z_index", 0) or 0),
            "font_family": getattr(f, "font_family", "Inter") or "Inter",
            "font_size": int(getattr(f, "font_size", 14) or 14),
            "font_bold": bool(getattr(f, "font_bold", False)),
            "font_italic": bool(getattr(f, "font_italic", False)),
            "font_underline": bool(getattr(f, "font_underline", False)),
            "text_align": getattr(f, "text_align", "left") or "left",
            "text_color": getattr(f, "text_color", "#000000") or "#000000",
            "bg_color": getattr(f, "bg_color", "transparent") or "transparent",
            "show_label": bool(getattr(f, "show_label", False)),

            "shape_type": getattr(f, "shape_type", "RECT") or "RECT",
            "shape_color": getattr(f, "shape_color", "#000000") or "#000000",
        })
    return layout


def _detect_units(layout, sizes):
    """
    Decide whether layout is UI px or REAL px (heuristic).
    """
    if not layout:
        return "UI"

    ui_w, ui_h = sizes["ui_w"], sizes["ui_h"]
    ew, eh = sizes["export_w_px"], sizes["export_h_px"]

    max_r = 0
    max_b = 0
    for it in layout:
        try:
            x = float(it.get("x", 0) or 0)
            y = float(it.get("y", 0) or 0)
            w = float(it.get("width", 0) or 0)
            h = float(it.get("height", 0) or 0)
            max_r = max(max_r, x + w)
            max_b = max(max_b, y + h)
        except Exception:
            continue

    if max_r <= ui_w * 1.25 and max_b <= ui_h * 1.25:
        return "UI"
    if max_r <= ew * 1.25 and max_b <= eh * 1.25:
        return "REAL"
    return "UI"


def _layout_to_ui_and_real(layout_any, sizes):
    """
    Convert unknown-units layout -> (layout_ui_px, layout_real_px).
    Also converts font_size in the same unit system.
    """
    units = _detect_units(layout_any, sizes)
    r2u = sizes["real_to_ui"]
    u2r = sizes["ui_to_real"]

    layout_ui = []
    layout_real = []

    for it in layout_any:
        ft = (it.get("field_type") or "TEXT").upper()

        x = float(it.get("x", 0) or 0)
        y = float(it.get("y", 0) or 0)
        w = float(it.get("width", 1) or 1)
        h = float(it.get("height", 1) or 1)
        fs = float(it.get("font_size", 14) or 14)

        base = dict(it)
        base["field_type"] = ft

        if units == "UI":
            ui_item = dict(base)
            ui_item.update({
                "x": int(round(x)),
                "y": int(round(y)),
                "width": max(1, int(round(w))),
                "height": max(1, int(round(h))),
                "font_size": max(1, int(round(fs))),
            })

            real_item = dict(base)
            real_item.update({
                "x": int(round(x * u2r)),
                "y": int(round(y * u2r)),
                "width": max(1, int(round(w * u2r))),
                "height": max(1, int(round(h * u2r))),
                "font_size": max(1, int(round(fs * u2r))),
            })
        else:
            ui_item = dict(base)
            ui_item.update({
                "x": int(round(x * r2u)),
                "y": int(round(y * r2u)),
                "width": max(1, int(round(w * r2u))),
                "height": max(1, int(round(h * r2u))),
                "font_size": max(1, int(round(fs * r2u))),
            })

            real_item = dict(base)
            real_item.update({
                "x": int(round(x)),
                "y": int(round(y)),
                "width": max(1, int(round(w))),
                "height": max(1, int(round(h))),
                "font_size": max(1, int(round(fs))),
            })

        layout_ui.append(ui_item)
        layout_real.append(real_item)

    return layout_ui, layout_real


def _input_fields_from_layout(layout_ui):
    """
    Return list of dicts: {key, name, field_type, html_type}
    Excludes: SHAPE, STATIC_TEXT, BARCODE, QRCODE
    """
    exclude = {"SHAPE", "STATIC_TEXT", "BARCODE", "QRCODE"}
    seen = set()
    out = []

    for it in layout_ui:
        ft = (it.get("field_type") or "TEXT").upper()
        key = (it.get("key") or "").strip()
        name = (it.get("name") or key or "Field").strip()

        if not key or ft in exclude:
            continue
        if key in seen:
            continue
        seen.add(key)

        html_type = "text"
        if ft == "PRICE":
            html_type = "number"
        elif ft == "IMAGE_URL":
            html_type = "url"

        out.append({"key": key, "name": name, "field_type": ft, "html_type": html_type})

    return out

def _ui_sizes(template: LabelTemplate):
    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)
    max_side = max(width_cm, height_cm) or 1.0
    ui_px_per_cm = UI_MAX_SIDE_PX / max_side
    ui_w = int(round(width_cm * ui_px_per_cm))
    ui_h = int(round(height_cm * ui_px_per_cm))
    return {
        "width_cm": width_cm,
        "height_cm": height_cm,
        "ui_px_per_cm": ui_px_per_cm,
        "ui_canvas_width": ui_w,
        "ui_canvas_height": ui_h,
    }


def _load_layout_ui(request, template: LabelTemplate):
    """
    Returns a list of dict items in UI units (px) if available.
    Priority: session layout (latest save) -> DB fallback.
    """
    session_key = f"template_layout_{template.id}"
    layout_json = request.session.get(session_key)

    if layout_json:
        try:
            data = json.loads(layout_json) if isinstance(layout_json, str) else layout_json
            if isinstance(data, list):
                return data
        except Exception:
            pass

    # DB fallback (older templates) — formatting defaults
    fields = LabelTemplateField.objects.filter(template=template).order_by("order", "id")
    layout = []
    for f in fields:
        layout.append({
            "name": f.name,
            "key": f.key,
            "field_type": (f.field_type or "TEXT").upper(),
            "workspace_field_id": f.workspace_field_id,
            "x": int(f.x or 0),
            "y": int(f.y or 0),
            "width": int(f.width or 100),
            "height": int(f.height or 24),

            # formatting defaults (if not stored in DB)
            "z_index": getattr(f, "z_index", 0) or 0,
            "font_family": getattr(f, "font_family", "Inter") or "Inter",
            "font_size": int(getattr(f, "font_size", 14) or 14),
            "font_bold": bool(getattr(f, "font_bold", False)),
            "font_italic": bool(getattr(f, "font_italic", False)),
            "font_underline": bool(getattr(f, "font_underline", False)),
            "text_align": getattr(f, "text_align", "left") or "left",
            "text_color": getattr(f, "text_color", "#000000") or "#000000",
            "bg_color": getattr(f, "bg_color", "transparent") or "transparent",
            "show_label": bool(getattr(f, "show_label", True)),

            "shape_type": getattr(f, "shape_type", "RECT") or "RECT",
            "shape_color": getattr(f, "shape_color", "#000000") or "#000000",
            "static_value": getattr(f, "static_value", "") or "",
        })
    return layout


def _input_fields_from_layout(layout_ui):
    """
    Fields the user should enter values for on Generate page.
    Excludes shapes/static/barcode/qr.
    """
    blocked = {"BARCODE", "QRCODE", "SHAPE", "STATIC_TEXT"}
    out = []
    seen = set()
    for it in layout_ui:
        ft = (it.get("field_type") or "TEXT").upper()
        key = (it.get("key") or "").strip()
        if not key or key in seen:
            continue
        if ft in blocked:
            continue
        out.append({
            "name": it.get("name") or key,
            "key": key,
            "field_type": ft,
        })
        seen.add(key)
    return out


def _cm_from_ui_px(px: int, ui_px_per_cm: float) -> float:
    return float(px) / float(ui_px_per_cm or 1.0)


def _mm_from_ui_px(px: int, ui_px_per_cm: float) -> float:
    # 1 cm = 10 mm
    return _cm_from_ui_px(px, ui_px_per_cm) * 10.0

@login_required
def workspace_list(request):
    user = request.user
    workspaces = []

    if user.org:
        workspaces = Workspace.objects.filter(org=user.org).order_by('-created_at')

    return render(request, 'workspaces/workspace_list.html', {
        "workspaces": workspaces,
    })

@login_required
def workspace_create_step1(request):
    user = request.user
    if not user.org or user.role != User.ROLE_ADMIN:
        messages.error(request, "Only admins can create workspaces.")
        return redirect('workspace_list')

    if request.method == "POST":
        form = WorkspaceCreateStep1Form(request.POST, request.FILES)
        if form.is_valid():
            name = form.cleaned_data['name']
            description = form.cleaned_data['description']
            template_file = form.cleaned_data['template_file']

            wizard = {
                "name": name,
                "description": description,
                "template_file_path": None,
                "fields": [],
                "from_file": False,
            }

            if template_file:
                _, ext = os.path.splitext(template_file.name.lower())
                if ext != '.csv':
                    messages.error(
                        request,
                        "Right now we only support CSV files. "
                        "Please export your Excel/Sheets file as CSV and upload that."
                    )
                    # Do NOT save file or mark from_file
                    # Re-render form with name/description preserved
                    return render(request, 'workspaces/workspace_create_step1.html', {
                        "form": form,
                    })

                filename = default_storage.save(
                    f"workspace_uploads/{template_file.name}",
                    template_file
                )
                wizard["template_file_path"] = filename
                wizard["from_file"] = True

            save_wizard(request, wizard)

            if wizard["from_file"]:
                return redirect('workspace_map_fields')
            else:
                return redirect('workspace_manual_fields')
    else:
        form = WorkspaceCreateStep1Form()

    return render(request, 'workspaces/workspace_create_step1.html', {
        "form": form,
    })

@login_required
def workspace_map_fields(request):
    user = request.user
    if not user.org or user.role != User.ROLE_ADMIN:
        messages.error(request, "Only admins can create workspaces.")
        return redirect('workspace_list')

    wizard = get_wizard(request)
    if not wizard or not wizard.get("from_file") or not wizard.get("template_file_path"):
        messages.error(request, "Workspace creation session not found or file not uploaded.")
        return redirect('workspace_create_step1')

    # Read headers from CSV
    file_path = wizard["template_file_path"]
    headers = []

    try:
        with default_storage.open(file_path, 'rb') as f:
            text_file = TextIOWrapper(f, encoding='utf-8', newline='')
            reader = csv.reader(text_file)
            try:
                headers = next(reader)
            except StopIteration:
                headers = []
    except (UnicodeDecodeError, csv.Error):
        # File is not a valid CSV text, or corrupt
        messages.error(
            request,
            "We couldn’t read that file as CSV. "
            "Please make sure you upload a valid CSV (exported from Excel/Sheets)."
        )
        clear_wizard(request)
        return redirect('workspace_create_step1')

    if request.method == "POST":
        # Allow going back
        if 'back' in request.POST:
            return redirect('workspace_create_step1')

        field_defs = []
        for idx, header in enumerate(headers):
            field_type = request.POST.get(f'field_type_{idx}')
            if field_type:
                field_defs.append({
                    "name": header.strip(),
                    "key": slugify(header) or f"field_{idx}",
                    "field_type": field_type,
                    "source_header": header.strip(),
                })

        wizard["fields"] = field_defs
        save_wizard(request, wizard)

        if not field_defs:
            # No fields selected; still allow to continue to manual fields
            messages.info(request, "No fields selected from file. You can define fields manually.")
            return redirect('workspace_manual_fields')

        return redirect('workspace_sample_canvas')

    return render(request, 'workspaces/workspace_map_fields.html', {
        "headers": headers,
    })

@login_required
def workspace_manual_fields(request):
    user = request.user
    if not user.org or user.role != User.ROLE_ADMIN:
        messages.error(request, "Only admins can create workspaces.")
        return redirect('workspace_list')

    wizard = get_wizard(request)
    if not wizard:
        messages.error(request, "Workspace creation session not found.")
        return redirect('workspace_create_step1')

    existing_fields = wizard.get("fields", []) or []

    if request.method == "POST":
        # Back navigation
        if 'back' in request.POST:
            if wizard.get("from_file"):
                return redirect('workspace_map_fields')
            return redirect('workspace_create_step1')

        action = request.POST.get('action', 'next')

        field_defs = []

        # Parse all field_name_* / field_type_* pairs from POST
        for key, value in request.POST.items():
            if not key.startswith('field_name_'):
                continue
            idx = key.split('_')[-1]
            name = (value or '').strip()
            field_type = (request.POST.get(f'field_type_{idx}', '') or '').strip()

            if name and field_type:
                field_defs.append({
                    "name": name,
                    "key": slugify(name) or f"field_{idx}",
                    "field_type": field_type,
                    "source_header": None,
                })

        wizard["fields"] = field_defs
        save_wizard(request, wizard)

        if action == 'skip':
            # Create workspace immediately, even if fields list is empty
            workspace = _create_workspace_from_wizard(user, wizard)
            clear_wizard(request)
            messages.success(request, f"Workspace '{workspace.name}' created.")
            return redirect('workspace_list')

        # Otherwise go to sample canvas
        return redirect('workspace_sample_canvas')

    # GET
    field_type_choices = WorkspaceField.FIELD_TYPE_CHOICES

    return render(request, 'workspaces/workspace_manual_fields.html', {
        "wizard": wizard,
        "existing_fields": existing_fields,
        "field_type_choices": field_type_choices,
    })

def _create_workspace_from_wizard(user, wizard):
    workspace = Workspace.objects.create(
        org=user.org,
        name=wizard["name"],
        description=wizard.get("description", ""),
        created_by=user,
        template_file=wizard.get("template_file_path") or None,
    )

    fields = wizard.get("fields", []) or []

    # Basic auto layout (stack vertically)
    x = 10
    y = 10
    spacing = 40

    for index, f in enumerate(fields):
        WorkspaceField.objects.create(
            workspace=workspace,
            name=f["name"],
            key=f["key"],
            field_type=f["field_type"],
            source_header=f.get("source_header"),
            x=x,
            y=y + index * spacing,
            width=200,
            height=32,
            order=index,
        )

    return workspace

@login_required
def workspace_sample_canvas(request):
    user = request.user
    if not user.org or user.role != User.ROLE_ADMIN:
        messages.error(request, "Only admins can create workspaces.")
        return redirect("workspace_list")

    wizard = get_wizard(request)
    if not wizard:
        messages.error(request, "Workspace creation session not found.")
        return redirect("workspace_create_step1")

    fields = wizard.get("fields", []) or []

    # Helper: does a list of items contain a barcode field?
    def has_barcode(items):
        return any(
            (item.get("key") == "barcode")
            or (str(item.get("field_type") or "").upper() == "BARCODE")
            for item in items
        )

    # Ensure there's at least one Barcode field in the wizard fields
    if not has_barcode(fields):
        fields.append(
            {
                "name": "Barcode",
                "key": "barcode",
                "field_type": "BARCODE",
                "source_header": None,
            }
        )
        wizard["fields"] = fields
        save_wizard(request, wizard)

    # If no fields, redirect to manual fields (very defensive)
    if not fields:
        messages.info(request, "Please define some fields first.")
        return redirect("workspace_manual_fields")

    base_x = 10
    spacing = 50

    # Initialise layout if not present
    if "layout" not in wizard:
        layout = []
        y_start = 10
        for idx, f in enumerate(fields):
            layout.append(
                {
                    "name": f["name"],
                    "key": f["key"],
                    "field_type": f["field_type"],
                    "source_header": f.get("source_header"),
                    "x": base_x,
                    "y": y_start + idx * spacing,
                    "width": 200,
                    "height": 40,
                }
            )
        wizard["layout"] = layout
        save_wizard(request, wizard)
    else:
        layout = wizard["layout"]

        # If layout somehow has no barcode (from older sessions), append one
        if not has_barcode(layout):
            max_y = max((item.get("y", 10) for item in layout), default=10)
            layout.append(
                {
                    "name": "Barcode",
                    "key": "barcode",
                    "field_type": "BARCODE",
                    "source_header": None,
                    "x": base_x,
                    "y": max_y + spacing,
                    "width": 250,
                    "height": 60,
                }
            )
            wizard["layout"] = layout
            save_wizard(request, wizard)

    if request.method == "POST":
        if "back" in request.POST:
            # Back button
            if wizard.get("from_file"):
                return redirect("workspace_map_fields")
            return redirect("workspace_manual_fields")

        # Save updated positions/sizes, then create workspace
        new_layout = []
        for idx, item in enumerate(layout):
            x = int(request.POST.get(f"x_{idx}", item["x"]))
            y = int(request.POST.get(f"y_{idx}", item["y"]))
            width = int(request.POST.get(f"width_{idx}", item["width"]))
            height = int(request.POST.get(f"height_{idx}", item["height"]))

            updated = item.copy()
            updated.update(
                {
                    "x": x,
                    "y": y,
                    "width": width,
                    "height": height,
                }
            )
            new_layout.append(updated)

        # Ensure barcode exists before saving workspace; if not, append one
        if not has_barcode(new_layout):
            max_y = max((item.get("y", 10) for item in new_layout), default=10)
            new_layout.append(
                {
                    "name": "Barcode",
                    "key": "barcode",
                    "field_type": "BARCODE",
                    "source_header": None,
                    "x": base_x,
                    "y": max_y + spacing,
                    "width": 250,
                    "height": 60,
                }
            )

        wizard["layout"] = new_layout
        save_wizard(request, wizard)

        # Create workspace with layout
        workspace = Workspace.objects.create(
            org=user.org,
            name=wizard["name"],
            description=wizard.get("description", ""),
            created_by=user,
            template_file=wizard.get("template_file_path") or None,
        )

        for idx, item in enumerate(new_layout):
            WorkspaceField.objects.create(
                workspace=workspace,
                name=item["name"],
                key=item["key"],
                field_type=item["field_type"],
                source_header=item.get("source_header"),
                x=item["x"],
                y=item["y"],
                width=item["width"],
                height=item["height"],
                order=idx,
            )

        clear_wizard(request)
        messages.success(
            request,
            f"Workspace '{workspace.name}' created with a base label template.",
        )
        return redirect("my_workspaces")

    return render(
        request,
        "workspaces/workspace_sample_canvas.html",
        {
            "layout": layout,
            "wizard": wizard,
        },
    )


@login_required
def manage_access(request):
    user = request.user
    if not user.org or user.role != User.ROLE_ADMIN:
        messages.error(request, "Only organisation admins can manage workspace access.")
        return redirect('dashboard')

    org = user.org

    # Org users & workspaces
    users = User.objects.filter(org=org).order_by('email')
    workspaces = Workspace.objects.filter(org=org).order_by('name')

    # Existing memberships map: (ws_id, user_id) -> membership
    memberships = WorkspaceMembership.objects.filter(workspace__org=org).select_related('workspace', 'user')
    membership_map = {(m.workspace_id, m.user_id): m for m in memberships}

    membership_role_choices = WorkspaceMembership.ROLE_CHOICES
    user_role_choices = User.ROLE_CHOICES  # from your User model

    if request.method == "POST":
        # 1) Process workspace memberships (checkboxes + workspace role)
        for ws in workspaces:
            for u in users:
                cb_name = f'ws_{ws.id}_user_{u.id}'
                role_name = f'ws_{ws.id}_role_{u.id}'
                has_access = cb_name in request.POST
                membership = membership_map.get((ws.id, u.id))

                if has_access:
                    ws_role = request.POST.get(role_name, WorkspaceMembership.ROLE_USER) or WorkspaceMembership.ROLE_USER
                    if membership:
                        if membership.role != ws_role:
                            membership.role = ws_role
                            membership.save()
                    else:
                        WorkspaceMembership.objects.create(
                            workspace=ws,
                            user=u,
                            role=ws_role,
                        )
                else:
                    if membership:
                        membership.delete()

        # 2) Process org-level role changes (this affects admin vs user ID)
        for u in users:
            new_role = request.POST.get(f'org_role_{u.id}', u.role)
            if new_role != u.role and new_role:
                previous_role = u.role
                u.role = new_role
                u.save()  # will regenerate user_code if role changed

                OrgRoleChangeLog.objects.create(
                    org=org,
                    user=u,
                    previous_role=previous_role,
                    new_role=new_role,
                    changed_by=user,
                )

        messages.success(request, "Access and roles updated successfully.")
        return redirect('workspace_manage_access')

    access_map = {}
    for m in memberships:
        ws_dict = access_map.setdefault(m.workspace_id, {})
        ws_dict[m.user_id] = m.role


    return render(request, 'workspaces/manage_access.html', {
        "org": org,
        "users": users,
        "workspaces": workspaces,
        "access_map": access_map,
        "membership_role_choices": membership_role_choices,
        "user_role_choices": user_role_choices,
    })


@login_required
def my_workspaces(request):
    user = request.user
    if not user.org:
        messages.error(request, "You are not linked to any organisation yet.")
        return redirect('dashboard')

    org = user.org

    if user.role == User.ROLE_ADMIN:
        # Admin sees all org workspaces
        workspaces = Workspace.objects.filter(org=org).order_by('name')
        membership_by_ws = {}  # not needed for admins
    else:
        # Non-admin: only workspaces they have membership in
        memberships = WorkspaceMembership.objects.filter(
            workspace__org=org,
            user=user,
        ).select_related('workspace')
        workspaces = [m.workspace for m in memberships]
        membership_by_ws = {m.workspace_id: m for m in memberships}

    return render(request, 'workspaces/my_workspaces.html', {
        "org": org,
        "workspaces": workspaces,
        "membership_by_ws": membership_by_ws,
        "is_admin": user.role == User.ROLE_ADMIN,
    })


@login_required
def my_workspace_detail(request, workspace_id):
    user = request.user
    if not user.org:
        messages.error(request, "You are not linked to any organisation yet.")
        return redirect('dashboard')

    org = user.org
    workspace = get_object_or_404(Workspace, id=workspace_id, org=org)

    # Access control: admins can see all; users only if they have membership
    if user.role != User.ROLE_ADMIN:
        has_access = WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=user,
        ).exists()
        if not has_access:
            messages.error(request, "You do not have access to this workspace.")
            return redirect('my_workspaces')

    return render(request, 'workspaces/my_workspace_detail.html', {
        "org": org,
        "workspace": workspace,
    })


def ensure_base_template_for_workspace(workspace: Workspace, user: User | None = None) -> LabelTemplate:
    """
    Ensure there is a base template for this workspace.
    If not, create one based on the existing WorkspaceField layout.
    """
    base = workspace.label_templates.filter(is_base=True).first()
    if base:
        return base

    # Fallback dimensions if you don't have them stored yet
    default_width_cm = 5.0
    default_height_cm = 3.0

    base = LabelTemplate.objects.create(
        workspace=workspace,
        name="Base Template",
        description="Base template created from initial workspace setup.",
        width_cm=default_width_cm,
        height_cm=default_height_cm,
        dpi=300,
        category=LabelTemplate.CATEGORY_OTHERS,
        is_base=True,
        created_by=user,
    )

    # Copy workspace fields as template fields
    ws_fields = WorkspaceField.objects.filter(workspace=workspace).order_by('id')
    for idx, f in enumerate(ws_fields):
        LabelTemplateField.objects.create(
            template=base,
            name=f.name,
            key=f.key,
            field_type=f.field_type,
            x=f.x,
            y=f.y,
            width=f.width,
            height=f.height,
            workspace_field=f,
            order=idx,
        )

    return base

@login_required
def label_template_list(request, workspace_id):
    user = request.user
    if not user.org:
        messages.error(request, "You are not linked to any organisation yet.")
        return redirect('dashboard')

    org = user.org
    workspace = get_object_or_404(Workspace, id=workspace_id, org=org)

    # Access control: admin sees all; users only if they have membership
    if user.role != User.ROLE_ADMIN:
        has_access = WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=user,
        ).exists()
        if not has_access:
            messages.error(request, "You do not have access to this workspace.")
            return redirect('my_workspaces')

    # Lazily create base template if missing
    ensure_base_template_for_workspace(workspace, user)

    templates = LabelTemplate.objects.filter(workspace=workspace).order_by("-created_at")

    base_template = (
        LabelTemplate.objects.filter(workspace=workspace)
        .order_by("id")  # or "created_at"
        .first()
    )
    base_template_id = base_template.id if base_template else None
    global_templates = GlobalTemplate.objects.filter(is_active=True).order_by("-created_at")

    # Filters
    category = request.GET.get('category') or ''
    search_q = request.GET.get('q') or ''

    if category:
        templates = templates.filter(category=category)

    if search_q:
        templates = templates.filter(
            Q(name__icontains=search_q) | Q(description__icontains=search_q)
        )

    categories = LabelTemplate.CATEGORY_CHOICES

    return render(request, 'workspaces/label_template_list.html', {
        "org": org,
        "workspace": workspace,
        "templates": templates,
        "categories": categories,
        "selected_category": category,
        "search_q": search_q,
        "is_admin": user.role == User.ROLE_ADMIN,
        "global_templates": global_templates,
    })

@login_required
def label_template_create(request, workspace_id):
    user = request.user
    if not user.org:
        messages.error(request, "You are not linked to any organisation yet.")
        return redirect("dashboard")

    org = user.org
    workspace = get_object_or_404(Workspace, id=workspace_id, org=org)

    # Access control: admin can always; users only if they have membership
    if user.role != User.ROLE_ADMIN:
        has_access = WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=user,
        ).exists()
        if not has_access:
            messages.error(request, "You do not have access to this workspace.")
            return redirect("my_workspaces")

    if request.method == "POST":
        form = LabelTemplateForm(request.POST)
        if form.is_valid():
            tpl = form.save(commit=False)
            tpl.workspace = workspace
            tpl.created_by = user
            tpl.is_base = False
            tpl.save()
            messages.success(request, "Template details saved. Now design your label.")
            return redirect("label_template_canvas", template_id=tpl.id)
    else:
        form = LabelTemplateForm(initial={"dpi": 300})

    return render(
        request,
        "workspaces/label_template_create.html",
        {
            "org": org,
            "workspace": workspace,
            "form": form,
        },
    )

@login_required
def label_template_canvas(request, template_id):
    user = request.user
    template = get_object_or_404(LabelTemplate, id=template_id)
    workspace = template.workspace
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    if user.role != User.ROLE_ADMIN:
        messages.error(request, "Only admins can edit templates.")
        return redirect("label_template_list", workspace_id=workspace.id)

    engine = compute_label_engine(
        width_cm=float(template.width_cm or 10),
        height_cm=float(template.height_cm or 10),
        dpi=int(template.dpi or 300),
        ui_max_side_px=700,
    )

    ui_scale = engine["ui_scale"]

    # ---------------------------
    # POST: Save to DB (canonical REAL px)
    # ---------------------------
    if request.method == "POST":
        canvas_bg_color = (request.POST.get("canvas_bg_color") or "").strip() or "#ffffff"
        template.canvas_bg_color = canvas_bg_color
        template.save(update_fields=["canvas_bg_color"])

        raw = (request.POST.get("layout_data") or "").strip()
        if not raw:
            messages.error(request, "No layout data submitted.")
            return redirect("label_template_canvas", template_id=template.id)

        try:
            incoming_ui = json.loads(raw)
            if not isinstance(incoming_ui, list):
                incoming_ui = []
        except Exception:
            messages.error(request, "Invalid layout data.")
            return redirect("label_template_canvas", template_id=template.id)

        # Barcode mandatory
        has_barcode = any(
            (str(it.get("key") or "").strip().lower() == "barcode")
            or ((str(it.get("field_type") or "")).upper() == "BARCODE")
            for it in incoming_ui
        )
        if not has_barcode:
            messages.error(request, "Barcode field is mandatory. Please add Barcode to the canvas.")
            return redirect("label_template_canvas", template_id=template.id)

        existing = {f.id: f for f in LabelTemplateField.objects.filter(template=template)}
        seen_ids = set()

        # Workspace fields mapping (avoid N queries)
        ws_field_ids = set()
        for it in incoming_ui:
            wf = it.get("workspace_field_id")
            if wf:
                try:
                    ws_field_ids.add(int(wf))
                except Exception:
                    pass
        ws_fields = {
            wf.id: wf
            for wf in WorkspaceField.objects.filter(workspace=workspace, id__in=list(ws_field_ids))
        }

        def norm_align(v: str) -> str:
            v = (v or "left").lower()
            return v if v in ("left", "center", "right") else "left"

        def norm_color(v: str, default: str) -> str:
            v = (v or "").strip()
            return v or default

        with transaction.atomic():
            order_counter = 0
            for it in incoming_ui:
                ft = (it.get("field_type") or "TEXT").upper()
                name = (it.get("name") or "").strip() or "Field"
                key = (it.get("key") or "").strip()

                # If key missing, generate stable-ish key
                if not key:
                    key = slugify(name)[:60] or f"field_{order_counter+1}"

                # Position in REAL px
                x_ui = int(it.get("x", 0) or 0)
                y_ui = int(it.get("y", 0) or 0)
                w_ui = int(it.get("width", 1) or 1)
                h_ui = int(it.get("height", 1) or 1)

                x = ui_to_real(x_ui, ui_scale)
                y = ui_to_real(y_ui, ui_scale)
                w = max(1, ui_to_real(w_ui, ui_scale))
                h = max(1, ui_to_real(h_ui, ui_scale))

                # Styling
                z_index = int(it.get("z_index", 0) or 0)
                font_family = (it.get("font_family") or "Inter").strip() or "Inter"
                font_size = int(it.get("font_size", 14) or 14)
                font_bold = bool(it.get("font_bold"))
                font_italic = bool(it.get("font_italic"))
                font_underline = bool(it.get("font_underline"))
                text_align = norm_align(it.get("text_align"))
                text_color = norm_color(it.get("text_color"), "#000000")
                bg_color = (it.get("bg_color") or "transparent").strip() or "transparent"
                show_label = bool(it.get("show_label", True))

                shape_type = (it.get("shape_type") or "RECT").upper()
                shape_color = norm_color(it.get("shape_color"), "#000000")

                wf_id = it.get("workspace_field_id") or None
                wf_obj = None
                if wf_id:
                    try:
                        wf_obj = ws_fields.get(int(wf_id))
                    except Exception:
                        wf_obj = None

                payload = {
                    "name": name,
                    "key": key,
                    "field_type": ft,
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "order": order_counter,
                    "z_index": z_index,
                    "font_family": font_family,
                    "font_size": max(6, min(font_size, 200)),
                    "font_bold": font_bold,
                    "font_italic": font_italic,
                    "font_underline": font_underline,
                    "text_align": text_align,
                    "text_color": text_color,
                    "bg_color": bg_color,
                    "show_label": show_label,
                    "shape_type": shape_type,
                    "shape_color": shape_color,
                    "workspace_field": wf_obj,
                }
                order_counter += 1

                db_id = it.get("db_id")
                if db_id:
                    try:
                        db_id = int(db_id)
                    except Exception:
                        db_id = None

                if db_id and db_id in existing:
                    f = existing[db_id]
                    for k, v in payload.items():
                        setattr(f, k, v)
                    f.save()
                    seen_ids.add(f.id)
                else:
                    f = LabelTemplateField.objects.create(template=template, **payload)
                    seen_ids.add(f.id)

            # Delete removed
            for fid, f in existing.items():
                if fid not in seen_ids:
                    f.delete()

        save_layout_to_template(template, incoming_ui)
        messages.success(request, "Template saved.")
        return redirect("label_template_preview", template_id=template.id)

    # ---------------------------
    # GET: Load from DB -> UI layout
    # ---------------------------
    fields = LabelTemplateField.objects.filter(template=template).order_by("z_index", "order", "id")

    layout_ui = []
    for f in fields:
        layout_ui.append({
            "db_id": f.id,
            "name": f.name,
            "key": f.key,
            "field_type": (f.field_type or "TEXT").upper(),
            "workspace_field_id": f.workspace_field_id or None,

            # UI coords
            "x": real_to_ui(int(f.x or 0), ui_scale),
            "y": real_to_ui(int(f.y or 0), ui_scale),
            "width": max(1, real_to_ui(int(f.width or 1), ui_scale)),
            "height": max(1, real_to_ui(int(f.height or 1), ui_scale)),

            # styling
            "z_index": int(getattr(f, "z_index", 0) or 0),
            "font_family": getattr(f, "font_family", "Inter") or "Inter",
            "font_size": int(getattr(f, "font_size", 14) or 14),
            "font_bold": bool(getattr(f, "font_bold", False)),
            "font_italic": bool(getattr(f, "font_italic", False)),
            "font_underline": bool(getattr(f, "font_underline", False)),
            "text_align": getattr(f, "text_align", "left") or "left",
            "text_color": getattr(f, "text_color", "#000000") or "#000000",
            "bg_color": getattr(f, "bg_color", "transparent") or "transparent",
            "show_label": bool(getattr(f, "show_label", True)),

            "shape_type": getattr(f, "shape_type", "RECT") or "RECT",
            "shape_color": getattr(f, "shape_color", "#000000") or "#000000",
        })

    workspace_fields = WorkspaceField.objects.filter(workspace=workspace).order_by("order", "id")
    canvas_bg = (getattr(template, "canvas_bg_color", None) or "#ffffff").strip() or "#ffffff"

    return render(
        request,
        "workspaces/label_template_canvas.html",
        {
            "org": org,
            "workspace": workspace,
            "template": template,
            "workspace_fields": workspace_fields,

            # Engine numbers
            "width_cm": engine["width_cm"],
            "height_cm": engine["height_cm"],
            "dpi": engine["dpi"],
            "real_canvas_width": engine["real_w_px"],
            "real_canvas_height": engine["real_h_px"],

            "ui_scale": engine["ui_scale"],
            "ui_px_per_cm": engine["ui_px_per_cm"],
            "canvas_width": engine["ui_w_px"],
            "canvas_height": engine["ui_h_px"],

            "canvas_bg_color": canvas_bg,
            "existing_layout": json.dumps(layout_ui),
        },
    )

import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from workspaces.utils.layout_engine import load_layout_from_template, canvas_ui_size
from workspaces.utils.label_codes import make_barcode_png, make_qr_png
from .models import LabelTemplate

@login_required
def label_template_preview(request, template_id):
    user = request.user
    template = get_object_or_404(LabelTemplate, id=template_id)
    workspace = template.workspace
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    stored = load_layout_from_template(template)
    meta = stored.get("_meta") or {}
    items = stored.get("items") or []

    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)

    # UI scale used during design (single source of truth)
    ui_px_per_cm = float(
        meta.get("ui_px_per_cm") or (700.0 / (max(width_cm, height_cm) or 1.0))
    )

    ui_w, ui_h = canvas_ui_size(width_cm, height_cm, ui_px_per_cm)
    canvas_bg = (template.canvas_bg_color or "#ffffff").strip() or "#ffffff"

    dpi = int(template.dpi or 300)
    export_w_px = int(round((width_cm / 2.54) * dpi))
    export_h_px = int(round((height_cm / 2.54) * dpi))

    # ---- sample values persisted in session ----
    sess_key = f"tpl_sample_{template.id}"
    sample_values = request.session.get(sess_key, {}) or {}

    if request.method == "POST":
        # reset
        if request.POST.get("reset") == "1":
            request.session[sess_key] = {}
            return redirect("label_template_preview", template_id=template.id)

        new_values = {}
        for it in items:
            ft = (it.get("field_type") or "").upper()
            key = (it.get("key") or "").strip()
            if not key:
                continue
            if ft in ("TEXT", "PRICE", "IMAGE_URL"):
                new_values[key] = (request.POST.get(f"field_{key}") or "").strip()

        request.session[sess_key] = new_values
        return redirect("label_template_preview", template_id=template.id)

    # Build sample fields panel (with values)
    sample_fields = []
    for it in items:
        ft = (it.get("field_type") or "").upper()
        key = (it.get("key") or "").strip()
        if key and ft in ("TEXT", "PRICE", "IMAGE_URL"):
            sample_fields.append(
                {
                    "name": it.get("name") or key,
                    "key": key,
                    "field_type": ft,
                    "value": sample_values.get(key, ""),
                }
            )

    # barcode/qr sample images for preview renderer
    barcode_base = "SAMPLE123456"
    serial = "001"
    barcode_value = f"{barcode_base}{serial}"
    qr_value = barcode_value

    barcode_img = make_barcode_png(barcode_value)
    qr_img = make_qr_png(qr_value)

    return render(
        request,
        "workspaces/label_template_preview.html",
        {
            "org": org,
            "workspace": workspace,
            "template": template,

            "width_cm": width_cm,
            "height_cm": height_cm,
            "dpi": dpi,

            "export_w_px": export_w_px,
            "export_h_px": export_h_px,

            "ui_px_per_cm": ui_px_per_cm,
            "ui_w": ui_w,
            "ui_h": ui_h,

            "canvas_bg_color": canvas_bg,

            # canonical items in UI pixels (already)
            "layout_ui": json.dumps(items),

            # sample panel
            "sample_fields": sample_fields,
            "sample_values_json": json.dumps(sample_values),

            # barcode/qr preview
            "barcode_img_data_url": barcode_img,
            "qr_img_data_url": qr_img,
            "barcode_value": barcode_value,
            "qr_value": qr_value,
        },
    )


@login_required
def label_template_edit(request, template_id):
    user = request.user
    template = get_object_or_404(LabelTemplate, id=template_id)
    workspace = template.workspace
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    if user.role != User.ROLE_ADMIN:
        messages.error(request, "Only admins can edit templates.")
        return redirect("label_template_list", workspace_id=workspace.id)

    return redirect("label_template_canvas", template_id=template.id)


@login_required
def label_template_duplicate(request, template_id):
    user = request.user
    template = get_object_or_404(LabelTemplate, id=template_id)
    workspace = template.workspace
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    if user.role != User.ROLE_ADMIN:
        messages.error(request, "Only admins can duplicate templates.")
        return redirect("label_template_list", workspace_id=workspace.id)

    if request.method == "POST":
        form = TemplateDuplicateForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            description = form.cleaned_data["description"]

            # Create new template, copying meta from original
            new_template = LabelTemplate.objects.create(
                workspace=workspace,
                name=name,
                description=description or template.description,
                width_cm=template.width_cm,
                height_cm=template.height_cm,
                dpi=template.dpi,
                category=template.category,
                custom_category=template.custom_category,
            )

            # Copy all fields / layout
            fields = LabelTemplateField.objects.filter(template=template).order_by(
                "order", "id"
            )
            for f in fields:
                LabelTemplateField.objects.create(
                    template=new_template,
                    name=f.name,
                    key=f.key,
                    field_type=f.field_type,
                    x=f.x,
                    y=f.y,
                    width=f.width,
                    height=f.height,
                    workspace_field=f.workspace_field,
                    order=f.order,
                )

            messages.success(request, f"Template duplicated as “{new_template.name}”.")
            # Go straight to canvas so they can tweak if needed
            return redirect("label_template_canvas", template_id=new_template.id)
    else:
        initial_name = f"{template.name} Copy"
        form = TemplateDuplicateForm(
            initial={
                "name": initial_name,
                "description": template.description,
            }
        )

    return render(
        request,
        "workspaces/label_template_duplicate.html",
        {
            "org": org,
            "workspace": workspace,
            "template": template,
            "form": form,
        },
    )

@require_POST
@login_required
def label_template_delete(request, template_id):
    user = request.user
    template = get_object_or_404(LabelTemplate, id=template_id)
    workspace = template.workspace
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    if user.role != User.ROLE_ADMIN:
        messages.error(request, "Only admins can delete templates.")
        return redirect("label_template_list", workspace_id=workspace.id)

    # Determine base template = first created in this workspace
    base_template = (
        LabelTemplate.objects.filter(workspace=workspace)
        .order_by("id")  # or "created_at" if you have that
        .first()
    )

    if base_template and template.id == base_template.id:
        messages.error(request, "Base template cannot be deleted.")
        return redirect("label_template_list", workspace_id=workspace.id)

    template.delete()
    messages.success(request, "Template deleted.")
    return redirect("label_template_list", workspace_id=workspace.id)

@login_required
def global_template_list(request):
    if not request.user.is_superuser:
        messages.error(request, "Only superadmins can access super templates.")
        return redirect("dashboard")

    templates = GlobalTemplate.objects.filter(is_active=True).order_by("-created_at")
    return render(
        request,
        "super_templates/global_template_list.html",
        {"templates": templates},
    )

@login_required
def global_template_create_meta(request):
    if not request.user.is_superuser:
        messages.error(request, "Only superadmins can create super templates.")
        return redirect("dashboard")

    if request.method == "POST":
        form = GlobalTemplateForm(request.POST)
        if form.is_valid():
            tmpl = form.save(commit=False)
            tmpl.created_by = request.user
            tmpl.save()
            # start with empty layout; canvas view will handle it
            return redirect("global_template_canvas", template_id=tmpl.id)
    else:
        form = GlobalTemplateForm(initial={"dpi": 300})

    return render(
        request,
        "super_templates/global_template_meta.html",
        {"form": form},
    )

@login_required
def global_template_canvas(request, template_id):
    user = request.user
    if not user.is_superuser:
        messages.error(request, "Only superadmins can edit super templates.")
        return redirect("dashboard")

    template = get_object_or_404(GlobalTemplate, id=template_id)
    session_key = f"global_template_layout_{template.id}"

    # ---------- POST: save layout then go to preview ----------
    if request.method == "POST":
        layout_json = (request.POST.get("layout_data") or "").strip()
        if not layout_json:
            messages.error(request, "No layout data submitted.")
            return redirect("global_template_canvas", template_id=template.id)

        try:
            layout = json.loads(layout_json)
        except json.JSONDecodeError:
            messages.error(request, "Invalid layout data.")
            return redirect("global_template_canvas", template_id=template.id)

        # Barcode mandatory here too
        has_barcode = any(
            (item.get("key") == "barcode")
            or (str(item.get("field_type") or "").upper() == "BARCODE")
            for item in layout
        )
        if not has_barcode:
            # keep what user did so far
            request.session[session_key] = json.dumps(layout)
            messages.error(
                request,
                "Barcode field is mandatory. Please add a Barcode field to the canvas.",
            )
            return redirect("global_template_canvas", template_id=template.id)

        # Store layout and go to preview
        request.session[session_key] = json.dumps(layout)
        return redirect("global_template_preview", template_id=template.id)

    # ---------- GET: build Python list `layout` ----------
    layout: list[dict] = []

    # 1) Try session
    layout_json = request.session.get(session_key)
    if layout_json:
        try:
            layout = json.loads(layout_json)
        except json.JSONDecodeError:
            layout = []

    # 2) If still empty, try DB
    if not layout:
        fields = (
            GlobalTemplateField.objects.filter(template=template)
            .order_by("order", "id")
        )
        for f in fields:
            layout.append(
                {
                    "name": f.name,
                    "key": f.key,
                    "field_type": f.field_type,
                    "x": f.x,
                    "y": f.y,
                    "width": f.width,
                    "height": f.height,
                }
            )

    # 3) If brand new super template – seed with a default barcode box
    if not layout:
        layout.append(
            {
                "name": "Barcode",
                "key": "barcode",
                "field_type": "BARCODE",
                "x": 50,
                "y": 50,
                "width": 250,
                "height": 60,
            }
        )

    # This is what the template will see – a JSON **array literal**
    existing_layout = json.dumps(layout)

    # Canvas size based on label dimensions (same logic as your workspace canvas)
    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)
    max_side = max(width_cm, height_cm) or 1.0
    scale = 700.0 / max_side
    canvas_width = int(width_cm * scale)
    canvas_height = int(height_cm * scale)

    return render(
        request,
        "super_templates/global_template_canvas.html",
        {
            "template": template,
            "existing_layout": existing_layout,
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
            "field_type_choices": WorkspaceField.FIELD_TYPE_CHOICES,
        },
    )


@login_required
def global_template_preview(request, template_id):
    user = request.user
    if not user.is_superuser:
        messages.error(request, "Only superadmins can edit super templates.")
        return redirect("dashboard")

    template = get_object_or_404(GlobalTemplate, id=template_id)
    session_key = f"global_template_layout_{template.id}"
    layout_json = request.session.get(session_key)

    if not layout_json:
        messages.error(request, "No layout data found for this template.")
        return redirect("global_template_canvas", template_id=template.id)

    try:
        layout = json.loads(layout_json)
    except json.JSONDecodeError:
        messages.error(request, "Invalid layout data; please re-design the template.")
        return redirect("global_template_canvas", template_id=template.id)

    # build sample form fields (same pattern as label preview)
    if request.method == "POST":
        if "save_template" in request.POST:
            # persist fields in DB
            GlobalTemplateField.objects.filter(template=template).delete()
            for idx, item in enumerate(layout):
                GlobalTemplateField.objects.create(
                    template=template,
                    name=item.get("name") or item.get("key"),
                    key=item.get("key"),
                    field_type=item.get("field_type"),
                    x=int(item.get("x", 0)),
                    y=int(item.get("y", 0)),
                    width=int(item.get("width", 140)),
                    height=int(item.get("height", 32)),
                    order=idx,
                )
            messages.success(request, "Super template saved.")
            return redirect("global_template_list")

        # "update_preview" – rebuild sample values dict
        sample_values = {}
        for item in layout:
            key = item.get("key")
            if not key:
                continue
            sample_values[key] = request.POST.get(f"sample_{key}", "")

    else:
        # GET – no sample values yet
        sample_values = {}

    # 🔹 Attach a 'sample_value' field onto each layout item
    for item in layout:
        key = item.get("key")
        item["sample_value"] = sample_values.get(key, "")

    return render(
        request,
        "super_templates/global_template_preview.html",
        {
            "template": template,
            "layout": layout,
            "sample_values": sample_values,  # can keep this if you want, but template won't index it
        },
    )

@login_required
def use_global_template(request, workspace_id, global_id):
    user = request.user
    workspace = get_object_or_404(Workspace, id=workspace_id)
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    # both admins and operators should be able to use recommended templates
    # (if you want only admins, add role check)
    global_tmpl = get_object_or_404(GlobalTemplate, id=global_id, is_active=True)

    # create a new LabelTemplate under this workspace
    new_template = LabelTemplate.objects.create(
        workspace=workspace,
        name=global_tmpl.name,
        description=global_tmpl.description,
        width_cm=global_tmpl.width_cm,
        height_cm=global_tmpl.height_cm,
        dpi=global_tmpl.dpi,
        category=global_tmpl.category,
        custom_category=global_tmpl.custom_category,
    )

    # copy global fields
    g_fields = GlobalTemplateField.objects.filter(template=global_tmpl).order_by(
        "order", "id"
    )
    for f in g_fields:
        LabelTemplateField.objects.create(
            template=new_template,
            name=f.name,
            key=f.key,
            field_type=f.field_type,
            x=f.x,
            y=f.y,
            width=f.width,
            height=f.height,
            workspace_field=None,  # generic fields
            order=f.order,
        )

    messages.success(
        request,
        f"Template “{global_tmpl.name}” duplicated into this workspace.",
    )
    # Let them further tweak it in the canvas
    return redirect("label_template_canvas", template_id=new_template.id)

@login_required
def label_generate_start(request, workspace_id):
    user = request.user
    workspace = get_object_or_404(Workspace, id=workspace_id)
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    templates = LabelTemplate.objects.filter(workspace=workspace).order_by("name")

    if request.method == "POST":
        template_id = request.POST.get("template_id")
        mode = request.POST.get("mode") or LabelBatch.MODE_SINGLE

        if not template_id:
            messages.error(request, "Please select a template.")
        else:
            if mode == LabelBatch.MODE_SINGLE:
                return redirect(
                    "label_generate_single",
                    workspace_id=workspace.id,
                    template_id=template_id,
                )
            else:
                messages.info(request, "Multi-SKU label generation is coming soon.")

    return render(
        request,
        "workspaces/label_generate_start.html",
        {
            "workspace": workspace,
            "templates": templates,
        },
    )

@login_required
def label_generate_single(request, workspace_id, template_id):
    user = request.user
    workspace = get_object_or_404(Workspace, id=workspace_id)
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    template = get_object_or_404(LabelTemplate, id=template_id, workspace=workspace)

    # membership check for non-admins
    if user.role != user.ROLE_ADMIN:
        if not WorkspaceMembership.objects.filter(workspace=workspace, user=user).exists():
            messages.error(request, "You do not have access to this workspace.")
            return redirect("my_workspaces")

    # ✅ SINGLE SOURCE OF TRUTH
    stored = load_layout_from_template(template)
    meta = stored.get("_meta") or {}
    items = stored.get("items") or []

    if not items:
        messages.error(request, "No template layout found. Please open Canvas and Save once.")
        return redirect("label_template_canvas", template_id=template.id)

    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)

    ui_px_per_cm = float(meta.get("ui_px_per_cm") or get_ui_px_per_cm(width_cm, height_cm))
    canvas_width, canvas_height = canvas_ui_size(width_cm, height_cm, ui_px_per_cm)

    canvas_bg = (template.canvas_bg_color or "#ffffff").strip() or "#ffffff"

    input_fields = input_fields_from_items(items)

    # defaults
    quantity = 1
    ean_code = ""
    has_gs1 = False
    gs1_code = ""
    field_values = {}

    if request.method == "POST":
        ean_code = (request.POST.get("ean_code") or "").strip()
        has_gs1 = request.POST.get("has_gs1") == "on"
        gs1_code = (request.POST.get("gs1_code") or "").strip() if has_gs1 else ""

        try:
            quantity = int(request.POST.get("quantity") or "0")
        except ValueError:
            quantity = 0

        errors = []
        if not ean_code:
            errors.append("EAN code is mandatory.")
        if quantity < 1 or quantity > 500:
            errors.append("Quantity must be between 1 and 500.")

        field_values = {}
        for f in input_fields:
            key = f["key"]
            field_values[key] = (request.POST.get(f"field_{key}") or "").strip()

        if errors:
            for msg in errors:
                messages.error(request, msg)
            return render(
                request,
                "workspaces/label_generate_single.html",
                {
                    "workspace": workspace,
                    "template": template,
                    "input_fields": input_fields,
                    "quantity": quantity or 1,
                    "ean_code": ean_code,
                    "has_gs1": has_gs1,
                    "gs1_code": gs1_code,
                    "field_values": field_values,

                    # for consistent UI sizing / preview widget if you show it
                    "canvas_width": canvas_width,
                    "canvas_height": canvas_height,
                    "canvas_bg_color": canvas_bg,
                },
            )

        batch = LabelBatch.objects.create(
            workspace=workspace,
            template=template,
            created_by=user,
            mode=LabelBatch.MODE_SINGLE,
            ean_code=ean_code,
            gs1_code=gs1_code,
            quantity=quantity,
            field_values=field_values,
        )

        messages.success(request, "Label batch created.")
        return redirect("label_generate_single_preview", workspace_id=workspace.id, batch_id=batch.id)

    return render(
        request,
        "workspaces/label_generate_single.html",
        {
            "workspace": workspace,
            "template": template,
            "input_fields": input_fields,
            "quantity": quantity,
            "ean_code": ean_code,
            "has_gs1": has_gs1,
            "gs1_code": gs1_code,
            "field_values": field_values,

            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
            "canvas_bg_color": canvas_bg,
        },
    )


@login_required
def label_generate_single_preview(request, workspace_id, batch_id):
    user = request.user
    workspace = get_object_or_404(Workspace, id=workspace_id)
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    batch = get_object_or_404(LabelBatch, id=batch_id, workspace=workspace)
    template = batch.template

    stored = load_layout_from_template(template)
    meta = stored.get("_meta") or {}
    items = stored.get("items") or []

    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)

    ui_px_per_cm = float(meta.get("ui_px_per_cm") or get_ui_px_per_cm(width_cm, height_cm))
    canvas_width, canvas_height = canvas_ui_size(width_cm, height_cm, ui_px_per_cm)

    canvas_bg = (template.canvas_bg_color or "#ffffff").strip() or "#ffffff"
    user_values = batch.field_values or {}

    serial = "001"
    base = ((batch.ean_code or "").strip()) + ((batch.gs1_code or "").strip())
    barcode_value = f"{base}{serial}" if base else ""
    qr_value = barcode_value

    barcode_img = make_barcode_png(barcode_value) if barcode_value else None
    qr_img = make_qr_png(qr_value) if qr_value else None

    def norm_align(v):
        v = (v or "left").lower()
        return v if v in ("left", "center", "right") else "left"

    render_items = []
    for it in items:
        ft = (it.get("field_type") or "TEXT").upper()
        key = (it.get("key") or "").strip()

        out = dict(it)

        # ✅ normalize for renderer stability
        out["field_type"] = ft
        out["text_align"] = norm_align(out.get("text_align"))
        out["show_label"] = bool(out.get("show_label", True))
        out["bg_color"] = (out.get("bg_color") or "transparent").strip() or "transparent"
        out["text_color"] = (out.get("text_color") or "#000000").strip() or "#000000"
        out["font_family"] = (out.get("font_family") or "Inter").strip() or "Inter"
        out["font_size"] = int(out.get("font_size") or 14)

        if ft == "BARCODE":
            out["value"] = barcode_value
            out["image_data_url"] = barcode_img
        elif ft == "QRCODE":
            out["value"] = qr_value
            out["image_data_url"] = qr_img
        elif ft == "STATIC_TEXT":
            out["value"] = out.get("static_value") or out.get("name") or ""
        else:
            out["value"] = user_values.get(key, "") if key else ""

        render_items.append(out)

    return render(
        request,
        "workspaces/label_generate_single_preview.html",
        {
            "workspace": workspace,
            "template": template,
            "batch": batch,
            "render_items": render_items,
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
            "canvas_bg_color": canvas_bg,
        },
    )

@login_required
def label_batch_history(request, workspace_id):
    user = request.user
    workspace = get_object_or_404(Workspace, id=workspace_id)
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    batches = (
        LabelBatch.objects.filter(workspace=workspace)
        .select_related("template", "created_by")
    )

    return render(
        request,
        "workspaces/label_batch_history.html",
        {
            "workspace": workspace,
            "batches": batches,
        },
    )

@login_required
def label_batch_print(request, workspace_id, batch_id):
    user = request.user
    workspace = get_object_or_404(Workspace, id=workspace_id)
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    batch = get_object_or_404(LabelBatch, id=batch_id, workspace=workspace)
    template = batch.template

    stored = load_layout_from_template(template)
    meta = stored.get("_meta") or {}
    items_ui = stored.get("items") or []

    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)

    ui_px_per_cm = float(meta.get("ui_px_per_cm") or get_ui_px_per_cm(width_cm, height_cm))
    mm_per_px = 10.0 / float(ui_px_per_cm or 1.0)  # 1cm = 10mm

    label_w_mm = width_cm * 10.0
    label_h_mm = height_cm * 10.0

    canvas_bg = (template.canvas_bg_color or "#ffffff").strip() or "#ffffff"
    user_values = batch.field_values or {}

    base = ((batch.ean_code or "").strip()) + ((batch.gs1_code or "").strip())
    qty = int(batch.quantity or 1)

    # serial padding: at least 3 digits
    serial_digits = max(3, len(str(qty)))

    def norm_align(v):
        v = (v or "left").lower()
        return v if v in ("left", "center", "right") else "left"

    # Convert one template item to mm-based coords + mm-based font sizing
    def item_to_mm(it):
        ft = (it.get("field_type") or "TEXT").upper()
        out = dict(it)
        out["field_type"] = ft

        # coords in mm
        out["x_mm"] = (float(out.get("x") or 0) * mm_per_px)
        out["y_mm"] = (float(out.get("y") or 0) * mm_per_px)
        out["w_mm"] = max(0.1, float(out.get("width") or 1) * mm_per_px)
        out["h_mm"] = max(0.1, float(out.get("height") or 1) * mm_per_px)

        # styles
        out["z_index"] = int(out.get("z_index") or 0)
        out["font_family"] = (out.get("font_family") or "Inter").strip() or "Inter"
        fs_px = float(out.get("font_size") or 14)
        out["font_size_mm"] = max(0.5, fs_px * mm_per_px)  # mm font size
        out["font_bold"] = bool(out.get("font_bold"))
        out["font_italic"] = bool(out.get("font_italic"))
        out["font_underline"] = bool(out.get("font_underline"))
        out["text_align"] = norm_align(out.get("text_align"))
        out["text_color"] = (out.get("text_color") or "#000000").strip() or "#000000"
        out["bg_color"] = (out.get("bg_color") or "transparent").strip() or "transparent"
        out["show_label"] = bool(out.get("show_label", True))

        out["shape_type"] = (out.get("shape_type") or "RECT").upper()
        out["shape_color"] = (out.get("shape_color") or "#000000").strip() or "#000000"

        return out

    base_items_mm = [item_to_mm(it) for it in items_ui]

    # Build labels list (each label has its own barcode/qr images)
    labels = []
    for i in range(1, qty + 1):
        serial = str(i).zfill(serial_digits)
        barcode_value = f"{base}{serial}" if base else serial
        qr_value = barcode_value

        barcode_img = make_barcode_png(barcode_value) if barcode_value else None
        qr_img = make_qr_png(qr_value) if qr_value else None

        label_items = []
        for it in base_items_mm:
            out = dict(it)
            ft = out["field_type"]
            key = (out.get("key") or "").strip()

            if ft == "BARCODE":
                out["value"] = barcode_value
                out["image_data_url"] = barcode_img
            elif ft == "QRCODE":
                out["value"] = qr_value
                out["image_data_url"] = qr_img
            elif ft == "STATIC_TEXT":
                out["value"] = out.get("static_value") or out.get("name") or ""
            else:
                out["value"] = user_values.get(key, "") if key else ""

            label_items.append(out)

        labels.append({"index": i, "serial": serial, "items": label_items})

    # Print defaults (optional)
    d = template.print_defaults or {}
    defaults = {
        "stock_type": d.get("stock_type", "SHEET"),  # SHEET or ROLL
        "page_size": d.get("page_size", "A4"),       # A4, LETTER, CUSTOM
        "orientation": d.get("orientation", "PORTRAIT"),
        "custom_w_mm": float(d.get("custom_w_mm", 210)),
        "custom_h_mm": float(d.get("custom_h_mm", 297)),
        "labels_per_row": int(d.get("labels_per_row", 2)),
        "gap_x_mm": float(d.get("gap_x_mm", 3)),
        "gap_y_mm": float(d.get("gap_y_mm", 3)),
        "margin_left_mm": float(d.get("margin_left_mm", 5)),
        "margin_top_mm": float(d.get("margin_top_mm", 5)),
        "margin_right_mm": float(d.get("margin_right_mm", 5)),
        "margin_bottom_mm": float(d.get("margin_bottom_mm", 5)),
        "offset_x_mm": float(d.get("offset_x_mm", 0)),
        "offset_y_mm": float(d.get("offset_y_mm", 0)),
    }

    page_sizes = {
        "A4": {"w": 210.0, "h": 297.0},
        "LETTER": {"w": 215.9, "h": 279.4},
    }

    return render(
        request,
        "workspaces/label_batch_print.html",
        {
            "workspace": workspace,
            "template": template,
            "batch": batch,

            "canvas_bg_color": canvas_bg,

            "label_w_mm": label_w_mm,
            "label_h_mm": label_h_mm,
            "mm_per_px": mm_per_px,

            "labels": labels,
            "defaults": defaults,
            "page_sizes_json": mark_safe(json.dumps(page_sizes)),
        },
    )



@login_required
def label_batch_export_csv(request, workspace_id, batch_id):
    user = request.user
    workspace = get_object_or_404(Workspace, id=workspace_id)
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    batch = get_object_or_404(LabelBatch, id=batch_id, workspace=workspace)
    template = batch.template

    # Get template fields in order
    t_fields = LabelTemplateField.objects.filter(
        template=template
    ).order_by("order", "id")

    # Figure out which special fields exist
    has_barcode = any((f.field_type or "").upper() == "BARCODE" for f in t_fields)
    has_qr = any((f.field_type or "").upper() == "QRCODE" for f in t_fields)

    base_ean = batch.ean_code or ""
    gs1 = batch.gs1_code or ""
    barcode_value = f"{base_ean}{gs1}".strip()

    user_values = batch.field_values or {}

    # Build rows: one row per label in the batch
    rows = []
    for i in range(1, batch.quantity + 1):
        serial_str = f"{i:03d}"
        qr_value = f"{barcode_value}{serial_str}" if has_qr and barcode_value else ""

        row = {
            "Label Index": i,
            "EAN Code": base_ean,
            "GS1 Code": gs1,
            "Barcode Encoded": barcode_value if has_barcode else "",
            "QR Encoded": qr_value if has_qr else "",
        }

        # Add all non-barcode/QR fields used in the template
        for f in t_fields:
            ft = (f.field_type or "").upper()
            key = f.key
            if ft in ("BARCODE", "QRCODE"):
                continue  # handled in the special columns above
            col_name = f.name or key
            row[col_name] = user_values.get(key, "")

        rows.append(row)

    # Even if quantity is somehow 0, return a CSV with just headers
    if rows:
        fieldnames = list(rows[0].keys())
    else:
        fieldnames = ["Label Index", "EAN Code", "GS1 Code", "Barcode Encoded", "QR Encoded"]

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="label_batch_{batch.id}.csv"'

    writer = csv.DictWriter(response, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    return response
