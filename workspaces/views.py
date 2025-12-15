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
<<<<<<< HEAD


WIZARD_SESSION_KEY = 'workspace_wizard'
=======
import re


WIZARD_SESSION_KEY = 'workspace_wizard'
HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
>>>>>>> ff5e724 (new additions to formatting)

def get_wizard(request):
    return request.session.get(WIZARD_SESSION_KEY, {})


def save_wizard(request, data):
    request.session[WIZARD_SESSION_KEY] = data
    request.session.modified = True


def clear_wizard(request):
    if WIZARD_SESSION_KEY in request.session:
        del request.session[WIZARD_SESSION_KEY]
        request.session.modified = True

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
        return redirect("workspace_list")

    return render(
        request,
        "workspaces/workspace_sample_canvas.html",
        {
            "layout": layout,
            "wizard": wizard,
        },
    )


    return render(request, 'workspaces/workspace_sample_canvas.html', {
        "layout": layout,
        "wizard": wizard,
    })

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

<<<<<<< HEAD
    # only admins can edit templates
=======
>>>>>>> ff5e724 (new additions to formatting)
    if user.role != User.ROLE_ADMIN:
        messages.error(request, "Only admins can edit templates.")
        return redirect("label_template_list", workspace_id=workspace.id)

    session_key = f"template_layout_{template.id}"
<<<<<<< HEAD

    if request.method == "POST":
        layout_json = request.POST.get("layout_data", "").strip()
=======
    session_bg_key = f"{session_key}_canvas_bg"

    # ---------- POST ----------
    if request.method == "POST":
        layout_json = (request.POST.get("layout_data") or "").strip()
>>>>>>> ff5e724 (new additions to formatting)
        if not layout_json:
            messages.error(request, "No layout data submitted.")
            return redirect("label_template_canvas", template_id=template.id)

<<<<<<< HEAD
        try:
            layout = json.loads(layout_json)
        except json.JSONDecodeError:
            messages.error(request, "Invalid layout data.")
            return redirect("label_template_canvas", template_id=template.id)

        # 🔴 Barcode is mandatory
=======
        # Canvas background (persist on template + session)
        posted_bg = (request.POST.get("canvas_bg_color") or "").strip()
        if posted_bg and HEX_COLOR_RE.match(posted_bg):
            template.canvas_bg_color = posted_bg
            template.save(update_fields=["canvas_bg_color"])
            request.session[session_bg_key] = posted_bg
        else:
            request.session[session_bg_key] = template.canvas_bg_color or "#ffffff"

        try:
            layout = json.loads(layout_json)
            if not isinstance(layout, list):
                raise ValueError("layout_data must be a JSON array")
        except Exception:
            messages.error(request, "Invalid layout data.")
            return redirect("label_template_canvas", template_id=template.id)

        # Barcode mandatory
>>>>>>> ff5e724 (new additions to formatting)
        has_barcode = any(
            (item.get("key") == "barcode")
            or (str(item.get("field_type") or "").upper() == "BARCODE")
            for item in layout
        )
<<<<<<< HEAD

        if not has_barcode:
            # keep their layout so nothing is lost
=======
        if not has_barcode:
>>>>>>> ff5e724 (new additions to formatting)
            request.session[session_key] = layout_json
            messages.error(
                request,
                "Barcode field is mandatory. Please add a Barcode field to the canvas before saving.",
            )
            return redirect("label_template_canvas", template_id=template.id)

<<<<<<< HEAD
        # ✅ Valid layout, with barcode → proceed to preview
        request.session[session_key] = layout_json
        return redirect("label_template_preview", template_id=template.id)


    # ---------- GET: load existing layout ----------

    layout_json = request.session.get(session_key)

    if not layout_json:
        # No session layout: fall back to DB fields
        fields = (
            LabelTemplateField.objects.filter(template=template)
            .order_by("order", "id")
        )
=======
        # Normalize defaults so preview/save always has all keys
        normalized = []
        for item in layout:
            item = item or {}
            normalized.append(
                {
                    "name": item.get("name", ""),
                    "key": item.get("key", ""),
                    "field_type": (item.get("field_type") or "").upper(),
                    "workspace_field_id": item.get("workspace_field_id", None),
                    "x": int(item.get("x", 0) or 0),
                    "y": int(item.get("y", 0) or 0),
                    "width": int(item.get("width", 140) or 140),
                    "height": int(item.get("height", 32) or 32),

                    # style
                    "font_bold": bool(item.get("font_bold", False)),
                    "font_italic": bool(item.get("font_italic", False)),
                    "font_underline": bool(item.get("font_underline", False)),
                    "font_size": int(item.get("font_size", 12) or 12),
                    "text_color": item.get("text_color") or "#000000",
                    "bg_color": item.get("bg_color") or "",

                    # static/shapes
                    "is_static": bool(item.get("is_static", False)),
                    "static_text": item.get("static_text") or "",
                    "shape_type": item.get("shape_type") or "",
                    "shape_color": item.get("shape_color") or "#000000",
                }
            )

        request.session[session_key] = json.dumps(normalized)
        return redirect("label_template_preview", template_id=template.id)

    # ---------- GET ----------
    layout_json = request.session.get(session_key)

    canvas_bg_color = (
        request.session.get(session_bg_key)
        or template.canvas_bg_color
        or "#ffffff"
    )

    if not layout_json:
        fields = LabelTemplateField.objects.filter(template=template).order_by("order", "id")
>>>>>>> ff5e724 (new additions to formatting)
        layout = []
        for f in fields:
            layout.append(
                {
                    "name": f.name,
                    "key": f.key,
<<<<<<< HEAD
                    "field_type": f.field_type,
                    "workspace_field_id": f.workspace_field.id
                    if f.workspace_field
                    else None,
=======
                    "field_type": (f.field_type or "").upper(),
                    "workspace_field_id": f.workspace_field.id if f.workspace_field else None,
>>>>>>> ff5e724 (new additions to formatting)
                    "x": f.x,
                    "y": f.y,
                    "width": f.width,
                    "height": f.height,
<<<<<<< HEAD
=======

                    # style
                    "font_bold": getattr(f, "font_bold", False),
                    "font_italic": getattr(f, "font_italic", False),
                    "font_underline": getattr(f, "font_underline", False),
                    "font_size": getattr(f, "font_size", 12) or 12,
                    "text_color": getattr(f, "text_color", "#000000") or "#000000",
                    "bg_color": getattr(f, "bg_color", "") or "",

                    # static/shapes
                    "is_static": getattr(f, "is_static", False),
                    "static_text": getattr(f, "static_text", "") or "",
                    "shape_type": getattr(f, "shape_type", "") or "",
                    "shape_color": getattr(f, "shape_color", "#000000") or "#000000",
>>>>>>> ff5e724 (new additions to formatting)
                }
            )
        layout_json = json.dumps(layout)

    existing_layout = layout_json or "[]"

<<<<<<< HEAD
    # canvas sizing based on cm ratio (keep your existing logic)
=======
>>>>>>> ff5e724 (new additions to formatting)
    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)
    max_side = max(width_cm, height_cm) or 1.0
    scale = 700.0 / max_side
<<<<<<< HEAD

=======
>>>>>>> ff5e724 (new additions to formatting)
    canvas_width = int(width_cm * scale)
    canvas_height = int(height_cm * scale)

    workspace_fields = WorkspaceField.objects.filter(workspace=workspace)

    return render(
        request,
        "workspaces/label_template_canvas.html",
        {
            "org": org,
            "workspace": workspace,
            "template": template,
            "workspace_fields": workspace_fields,
            "existing_layout": existing_layout,
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
<<<<<<< HEAD
=======
            "canvas_bg_color": canvas_bg_color,
>>>>>>> ff5e724 (new additions to formatting)
        },
    )

@login_required
def label_template_preview(request, template_id):
    user = request.user
    template = get_object_or_404(LabelTemplate, id=template_id)
    workspace = template.workspace
    org = workspace.org

    if not user.org or user.org != org:
        messages.error(request, "You are not linked to this organisation.")
        return redirect("dashboard")

    if user.role != User.ROLE_ADMIN:
<<<<<<< HEAD
        has_access = WorkspaceMembership.objects.filter(
            workspace=workspace,
            user=user,
        ).exists()
=======
        has_access = WorkspaceMembership.objects.filter(workspace=workspace, user=user).exists()
>>>>>>> ff5e724 (new additions to formatting)
        if not has_access:
            messages.error(request, "You do not have access to this workspace.")
            return redirect("my_workspaces")

    session_key = f"template_layout_{template.id}"
<<<<<<< HEAD
=======
    session_bg_key = f"{session_key}_canvas_bg"

>>>>>>> ff5e724 (new additions to formatting)
    layout_data = request.session.get(session_key)
    if not layout_data:
        messages.error(request, "No layout data found, please design your template first.")
        return redirect("label_template_canvas", template_id=template.id)

    try:
        layout = json.loads(layout_data)
    except json.JSONDecodeError:
        messages.error(request, "Layout data is corrupted, please design again.")
        return redirect("label_template_canvas", template_id=template.id)

<<<<<<< HEAD
    field_keys = [item.get("key") for item in layout]
=======
    # Canvas BG: from session (set on canvas), else from template model
    canvas_bg_color = request.session.get(session_bg_key) or (template.canvas_bg_color or "#ffffff")

    def is_shape(item: dict) -> bool:
        return bool((item.get("shape_type") or "").strip())

    def is_static(item: dict) -> bool:
        return bool(item.get("is_static")) or (str(item.get("field_type") or "").upper() == "STATIC_TEXT")

    def ft(item: dict) -> str:
        return str(item.get("field_type") or "").upper()

    # Only ask sample values for real variable fields (not barcode/qr, not shapes, not static)
    sample_keys = []
    for item in layout:
        key = item.get("key")
        if not key:
            continue
        if ft(item) in ("BARCODE", "QRCODE"):
            continue
        if is_shape(item):
            continue
        if is_static(item):
            continue
        sample_keys.append(key)

>>>>>>> ff5e724 (new additions to formatting)
    sample_values = {}
    errors = {}

    if request.method == "POST":
<<<<<<< HEAD
        action = request.POST.get("action")
        # Collect sample values
        for key in field_keys:
            sample_values[key] = (request.POST.get(f"sample_{key}") or "").strip()

        # Validate image URLs
        for item in layout:
            if item.get("field_type") == WorkspaceField.FIELD_IMAGE_URL:
                key = item.get("key")
                val = sample_values.get(key, "")
                if val and not (val.startswith("http://") or val.startswith("https://")):
                    errors[key] = "Please enter a valid URL starting with http:// or https://"

        if not errors and action == "save":
            # Persist fields
            LabelTemplateField.objects.filter(template=template).delete()
=======
        action = request.POST.get("action")  # preview/save

        # keep canvas bg if passed (optional), else session value remains
        post_bg = (request.POST.get("canvas_bg_color") or "").strip()
        if post_bg:
            canvas_bg_color = post_bg
            request.session[session_bg_key] = post_bg

        # Collect sample values
        for key in sample_keys:
            sample_values[key] = (request.POST.get(f"sample_{key}") or "").strip()

        # Validate image URLs for IMAGE_URL fields
        for item in layout:
            if ft(item) == "IMAGE_URL":
                key = item.get("key")
                if key in sample_keys:
                    val = sample_values.get(key, "")
                    if val and not (val.startswith("http://") or val.startswith("https://")):
                        errors[key] = "Please enter a valid URL starting with http:// or https://"

        if not errors and action == "save":
            # Save template canvas bg color
            template.canvas_bg_color = canvas_bg_color
            template.save(update_fields=["canvas_bg_color", "updated_at"])

            # Persist fields exactly as designed (INCLUDING styles, static text, shapes)
            LabelTemplateField.objects.filter(template=template).delete()

>>>>>>> ff5e724 (new additions to formatting)
            for order_idx, item in enumerate(layout):
                LabelTemplateField.objects.create(
                    template=template,
                    name=item.get("name") or item.get("key"),
<<<<<<< HEAD
                    key=item.get("key"),
                    field_type=item.get("field_type", WorkspaceField.FIELD_TEXT),
                    x=item.get("x", 0),
                    y=item.get("y", 0),
                    width=item.get("width", 100),
                    height=item.get("height", 24),
                    workspace_field_id=item.get("workspace_field_id") or None,
                    order=order_idx,
                )

            # Clear layout from session
            request.session.pop(session_key, None)
            messages.success(request, "Template saved successfully.")
            return redirect("label_template_list", workspace_id=workspace.id)

        # If action == "preview" or there are errors, fall through to re-render
    else:
        # Initial GET: empty values
        sample_values = {k: "" for k in field_keys}

    # Enrich layout items with value + error for template
    layout_enriched = []
    for item in layout:
        key = item.get("key")
        enriched = dict(item)  # shallow copy
        enriched["value"] = sample_values.get(key, "")
        enriched["error"] = errors.get(key, "")
        layout_enriched.append(enriched)

    # --- NEW: same canvas sizing logic as designer ---
=======
                    key=item.get("key") or "",
                    field_type=item.get("field_type", WorkspaceField.FIELD_TEXT),
                    x=int(item.get("x", 0)),
                    y=int(item.get("y", 0)),
                    width=int(item.get("width", 100)),
                    height=int(item.get("height", 24)),
                    workspace_field_id=item.get("workspace_field_id") or None,
                    order=order_idx,

                    # ✅ text styling
                    font_bold=bool(item.get("font_bold", False)),
                    font_italic=bool(item.get("font_italic", False)),
                    font_underline=bool(item.get("font_underline", False)),
                    font_size=int(item.get("font_size") or 12),
                    text_color=item.get("text_color") or "#000000",
                    bg_color=item.get("bg_color") or "",

                    # ✅ static text
                    is_static=bool(item.get("is_static", False)),
                    static_text=item.get("static_text") or "",

                    # ✅ shape
                    shape_type=item.get("shape_type") or "",
                    shape_color=item.get("shape_color") or "#000000",
                )

            # Clear session data
            request.session.pop(session_key, None)
            request.session.pop(session_bg_key, None)

            messages.success(request, "Template saved successfully.")
            return redirect("label_template_list", workspace_id=workspace.id)

        # else: show preview with values/errors
    else:
        sample_values = {k: "" for k in sample_keys}

    # Enrich layout for template rendering
    layout_enriched = []
    for item in layout:
        key = item.get("key")

        enriched = dict(item)
        enriched["field_type"] = ft(item)
        enriched["canvas_bg_color"] = canvas_bg_color

        # If static text, preview uses static_text (not sample input)
        if is_static(enriched):
            enriched["value"] = enriched.get("static_text") or ""
        elif key and key in sample_values:
            enriched["value"] = sample_values.get(key, "")
        else:
            enriched["value"] = ""

        enriched["error"] = errors.get(key, "")
        layout_enriched.append(enriched)

    # Canvas sizing
>>>>>>> ff5e724 (new additions to formatting)
    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)
    max_side = max(width_cm, height_cm) or 1.0
    scale = 700.0 / max_side
<<<<<<< HEAD

    canvas_width = int(width_cm * scale)
    canvas_height = int(height_cm * scale)
    # --- END NEW ---
=======
    canvas_width = int(width_cm * scale)
    canvas_height = int(height_cm * scale)
>>>>>>> ff5e724 (new additions to formatting)

    return render(
        request,
        "workspaces/label_template_preview.html",
        {
            "org": org,
            "workspace": workspace,
            "template": template,
            "layout": layout_enriched,
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
<<<<<<< HEAD
=======
            "canvas_bg_color": canvas_bg_color,
>>>>>>> ff5e724 (new additions to formatting)
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

    # Fields to ask user for (everything except BARCODE / QRCODE)
    t_fields = LabelTemplateField.objects.filter(template=template).order_by("order", "id")
<<<<<<< HEAD
    input_fields = [
        f for f in t_fields
        if (str(f.field_type) or "").upper() not in ("BARCODE", "QRCODE")
    ]
=======
    input_fields = []
    for f in t_fields:
        ft = (str(f.field_type) or "").upper()

        # Always exclude codes (system-derived)
        if ft in ("BARCODE", "QRCODE"):
            continue

        # Exclude static text blocks
        if getattr(f, "is_static", False):
            continue

        # Exclude shapes (shape_type drives rendering)
        if (getattr(f, "shape_type", "") or "").strip():
            continue

        # Extra safety if you ever store these in field_type
        if ft in ("SHAPE", "STATIC_TEXT"):
            continue

        input_fields.append(f)
>>>>>>> ff5e724 (new additions to formatting)

    initial = {
        "quantity": 1,
        "ean_code": "",
        "gs1_code": "",
        "has_gs1": False,
        "field_values": {},
    }

    if request.method == "POST":
        ean = (request.POST.get("ean_code") or "").strip()
        has_gs1 = request.POST.get("has_gs1") == "on"
        gs1 = (request.POST.get("gs1_code") or "").strip() if has_gs1 else ""

        try:
            qty = int(request.POST.get("quantity") or "0")
        except ValueError:
            qty = 0

        errors = []
        if not ean:
            errors.append("EAN code is mandatory.")
        if qty < 1 or qty > 500:
            errors.append("Quantity must be between 1 and 500.")

        field_values = {}
        for f in input_fields:
            key = f.key
            value = (request.POST.get(f"field_{key}") or "").strip()
            field_values[key] = value

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
                    "quantity": qty or 1,
                    "ean_code": ean,
                    "has_gs1": has_gs1,
                    "gs1_code": gs1,
                    "field_values": field_values,
                },
            )

        batch = LabelBatch.objects.create(
            workspace=workspace,
            template=template,
            created_by=user,
            mode=LabelBatch.MODE_SINGLE,
            ean_code=ean,
            gs1_code=gs1,
            quantity=qty,
            field_values=field_values,
        )

        messages.success(request, "Label batch created.")
        return redirect(
            "label_generate_single_preview",
            workspace_id=workspace.id,
            batch_id=batch.id,
        )

    # GET – show blank form
    return render(
        request,
        "workspaces/label_generate_single.html",
        {
            "workspace": workspace,
            "template": template,
            "input_fields": input_fields,
            "quantity": 1,
            "ean_code": "",
            "has_gs1": False,
            "gs1_code": "",
            "field_values": {},
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

<<<<<<< HEAD
    # Layout from template fields
    t_fields = LabelTemplateField.objects.filter(template=template).order_by("order", "id")

    layout = []
    has_qr = False
    for f in t_fields:
        ft = (f.field_type or "").upper()
        if ft == "QRCODE":
            has_qr = True
=======
    t_fields = LabelTemplateField.objects.filter(template=template).order_by("order", "id")

    # Build layout with styling + shape/static metadata
    layout = []
    has_qr = False
    for f in t_fields:
        ft = (str(f.field_type) or "").upper()
        if ft == "QRCODE":
            has_qr = True

>>>>>>> ff5e724 (new additions to formatting)
        layout.append(
            {
                "name": f.name,
                "key": f.key,
                "field_type": ft,
                "x": f.x,
                "y": f.y,
                "width": f.width,
                "height": f.height,
<<<<<<< HEAD
=======

                # styling
                "font_bold": getattr(f, "font_bold", False),
                "font_italic": getattr(f, "font_italic", False),
                "font_underline": getattr(f, "font_underline", False),
                "font_size": getattr(f, "font_size", 12) or 12,
                "text_color": getattr(f, "text_color", "#000000") or "#000000",
                "bg_color": getattr(f, "bg_color", "") or "",

                # static + shapes
                "is_static": getattr(f, "is_static", False),
                "static_text": getattr(f, "static_text", "") or "",
                "shape_type": (getattr(f, "shape_type", "") or "").strip(),
                "shape_color": getattr(f, "shape_color", "#000000") or "#000000",
>>>>>>> ff5e724 (new additions to formatting)
            }
        )

    base_ean = batch.ean_code or ""
    gs1 = batch.gs1_code or ""
    barcode_value = f"{base_ean}{gs1}".strip()

<<<<<<< HEAD
    serial_str = f"{1:03d}"  # preview = first label
=======
    serial_str = f"{1:03d}"
>>>>>>> ff5e724 (new additions to formatting)
    qr_value = f"{barcode_value}{serial_str}" if has_qr and barcode_value else ""

    user_values = batch.field_values or {}

<<<<<<< HEAD
    # Generate images once for preview
=======
>>>>>>> ff5e724 (new additions to formatting)
    barcode_img_data = make_barcode_png(barcode_value) if barcode_value else None
    qr_img_data = make_qr_png(qr_value) if qr_value else None

    for item in layout:
<<<<<<< HEAD
        key = item["key"]
        ft = item["field_type"]
        if ft == "BARCODE":
            item["value"] = barcode_value
            item["image_data_url"] = barcode_img_data
        elif ft == "QRCODE":
            item["value"] = qr_value
            item["image_data_url"] = qr_img_data
        else:
            item["value"] = user_values.get(key, "")

    # canvas size same as template canvas
=======
        ft = item["field_type"]

        # barcode/qr render as images
        if ft == "BARCODE":
            item["value"] = barcode_value
            item["image_data_url"] = barcode_img_data
            continue
        if ft == "QRCODE":
            item["value"] = qr_value
            item["image_data_url"] = qr_img_data
            continue

        # shapes: no value, no label shown in HTML
        if item.get("shape_type"):
            item["value"] = ""
            continue

        # static text: use saved static_text
        if item.get("is_static"):
            item["value"] = item.get("static_text") or ""
            continue

        # regular variable field
        item["value"] = user_values.get(item["key"], "")

    # Canvas size
>>>>>>> ff5e724 (new additions to formatting)
    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)
    max_side = max(width_cm, height_cm) or 1.0
    scale = 700.0 / max_side
    canvas_width = int(width_cm * scale)
    canvas_height = int(height_cm * scale)

    return render(
        request,
        "workspaces/label_generate_single_preview.html",
        {
            "workspace": workspace,
            "template": template,
            "batch": batch,
            "layout": layout,
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
<<<<<<< HEAD
=======
            "canvas_bg_color": template.canvas_bg_color or "#ffffff",
>>>>>>> ff5e724 (new additions to formatting)
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

<<<<<<< HEAD
=======
    # ✅ canvas bg (important for print + preview consistency)
    canvas_bg_color = (template.canvas_bg_color or "#ffffff").strip() or "#ffffff"

>>>>>>> ff5e724 (new additions to formatting)
    t_fields = LabelTemplateField.objects.filter(template=template).order_by("order", "id")

    base_layout = []
    has_qr = False
<<<<<<< HEAD
=======

>>>>>>> ff5e724 (new additions to formatting)
    for f in t_fields:
        ft = (f.field_type or "").upper()
        if ft == "QRCODE":
            has_qr = True
<<<<<<< HEAD
=======

>>>>>>> ff5e724 (new additions to formatting)
        base_layout.append(
            {
                "name": f.name,
                "key": f.key,
                "field_type": ft,
                "x": f.x,
                "y": f.y,
                "width": f.width,
                "height": f.height,
<<<<<<< HEAD
            }
        )

    base_ean = batch.ean_code or ""
    gs1 = batch.gs1_code or ""
=======

                # styles
                "font_bold": bool(getattr(f, "font_bold", False)),
                "font_italic": bool(getattr(f, "font_italic", False)),
                "font_underline": bool(getattr(f, "font_underline", False)),
                "font_size": int(getattr(f, "font_size", 12) or 12),
                "text_color": getattr(f, "text_color", "#000000") or "#000000",
                "bg_color": getattr(f, "bg_color", "") or "",

                # static/shapes
                "is_static": bool(getattr(f, "is_static", False)),
                "static_text": getattr(f, "static_text", "") or "",
                "shape_type": getattr(f, "shape_type", "") or "",
                "shape_color": getattr(f, "shape_color", "#000000") or "#000000",
            }
        )

    base_ean = (batch.ean_code or "").strip()
    gs1 = (batch.gs1_code or "").strip()
>>>>>>> ff5e724 (new additions to formatting)
    barcode_value = f"{base_ean}{gs1}".strip()
    user_values = batch.field_values or {}

    # Generate barcode image once (same for all labels in batch)
    barcode_img_data = make_barcode_png(barcode_value) if barcode_value else None

    labels = []
<<<<<<< HEAD
    for i in range(1, batch.quantity + 1):
=======
    for i in range(1, (batch.quantity or 0) + 1):
>>>>>>> ff5e724 (new additions to formatting)
        serial_str = f"{i:03d}"
        qr_value = f"{barcode_value}{serial_str}" if has_qr and barcode_value else ""
        qr_img_data = make_qr_png(qr_value) if qr_value else None

        label_layout = []
        for item in base_layout:
            itm = item.copy()
<<<<<<< HEAD
            ft = itm["field_type"]
            key = itm["key"]

            if ft == "BARCODE":
                itm["value"] = barcode_value
                itm["image_data_url"] = barcode_img_data
            elif ft == "QRCODE":
                itm["value"] = qr_value
                itm["image_data_url"] = qr_img_data
            else:
                itm["value"] = user_values.get(key, "")

            label_layout.append(itm)

        labels.append(
            {
                "index": i,
                "layout": label_layout,
            }
        )

=======
            ft = (itm.get("field_type") or "").upper()
            key = itm.get("key") or ""

    # ✅     SHAPES: ignore values completely
            if (itm.get("shape_type") or "").strip():
                itm["value"] = ""
                itm["image_data_url"] = None

    # ✅ STATIC TEXT: always comes from static_text
            elif itm.get("is_static"):
                itm["value"] = itm.get("static_text") or ""
                itm["image_data_url"] = None

    # ✅ BARCODE / QR
            elif ft == "BARCODE":
                itm["value"] = barcode_value
                itm["image_data_url"] = barcode_img_data

            elif ft == "QRCODE":
                itm["value"] = qr_value
                itm["image_data_url"] = qr_img_data

    # ✅ NORMAL FIELDS (including IMAGE_URL)
            else:
                itm["value"] = user_values.get(key, "")
                itm["image_data_url"] = None

            label_layout.append(itm)


        labels.append({"index": i, "layout": label_layout})

    # canvas size (same scaling you already use)
>>>>>>> ff5e724 (new additions to formatting)
    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)
    max_side = max(width_cm, height_cm) or 1.0
    scale = 700.0 / max_side
    canvas_width = int(width_cm * scale)
    canvas_height = int(height_cm * scale)

    return render(
        request,
        "workspaces/label_batch_print.html",
        {
            "workspace": workspace,
            "template": template,
            "batch": batch,
            "labels": labels,
            "canvas_width": canvas_width,
            "canvas_height": canvas_height,
<<<<<<< HEAD
=======
            "canvas_bg_color": template.canvas_bg_color,   # ✅ ADD THIS
>>>>>>> ff5e724 (new additions to formatting)
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
