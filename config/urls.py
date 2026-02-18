from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import re_path
from django.views.static import serve as django_serve
from django.conf.urls.static import static
from django.db.models import Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
import json
import os
from cms.models import CMSPost
from workspaces.models import Workspace, LabelTemplate, LabelBatch


def landingpage(request):
    recent_blogs = (
        CMSPost.objects
        .filter(status=CMSPost.STATUS_PUBLISHED, type=CMSPost.TYPE_BLOG)
        .order_by("-published_at", "-created_at", "-id")[:3]
    )

    recent_videos = (
        CMSPost.objects
        .filter(status=CMSPost.STATUS_PUBLISHED, type=CMSPost.TYPE_VIDEO)
        .order_by("-published_at", "-created_at", "-id")[:3]
    )

    return render(request, "landingpage.html", {
        "recent_blogs": recent_blogs,
        "recent_videos": recent_videos,
    })


def _parse_date(s: str):
    """
    Accepts 'YYYY-MM-DD'. Returns aware datetime at start of day in current TZ.
    """
    if not s:
        return None
    try:
        d = datetime.strptime(s, "%Y-%m-%d").date()
        tz = timezone.get_current_timezone()
        return timezone.make_aware(datetime(d.year, d.month, d.day, 0, 0, 0), tz)
    except Exception:
        return None


@login_required
def dashboard_view(request):
    user = request.user

    ctx = {
        "is_admin": (user.role == user.ROLE_ADMIN),
        "workspace_count": 0,
        "template_count": 0,
        "labels_total": 0,
        "chart_labels": "[]",
        "chart_values": "[]",
        "top_categories": [],
        "workspace_options": [],
        "selected_workspace": "all",
        "range_mode": "30",       # '7'/'30'/'90'/'custom'
        "start_date": "",
        "end_date": "",
    }

    if not user.org:
        return render(request, "dashboard.html", ctx)

    org = user.org

    # ---- Accessible workspaces (admin: all org workspaces, user: memberships) ----
    if user.role == user.ROLE_ADMIN:
        accessible_qs = Workspace.objects.filter(org=org).order_by("name")
    else:
        accessible_qs = Workspace.objects.filter(
            org=org,
            memberships__user=user
        ).distinct().order_by("name")

    accessible_ids = list(accessible_qs.values_list("id", flat=True))

    # Workspace dropdown options
    ctx["workspace_options"] = list(accessible_qs.values("id", "name"))

    # Workspace filter (GET)
    selected_ws = (request.GET.get("workspace") or "all").strip()
    if selected_ws != "all":
        try:
            selected_ws_id = int(selected_ws)
        except ValueError:
            selected_ws_id = None

        # Non-admin must not query other workspaces
        if selected_ws_id and selected_ws_id in accessible_ids:
            scoped_ids = [selected_ws_id]
            ctx["selected_workspace"] = str(selected_ws_id)
        else:
            scoped_ids = accessible_ids
            ctx["selected_workspace"] = "all"
    else:
        scoped_ids = accessible_ids
        ctx["selected_workspace"] = "all"

    # If user has no accessible workspaces
    if not scoped_ids:
        return render(request, "dashboard.html", ctx)

    # ---- Date filter (GET) ----
    range_mode = (request.GET.get("range") or "30").strip()  # 7/30/90/custom
    ctx["range_mode"] = range_mode if range_mode in ("7", "30", "90", "custom") else "30"

    start_dt = None
    end_dt = None

    if ctx["range_mode"] == "custom":
        start_dt = _parse_date(request.GET.get("start") or "")
        end_dt = _parse_date(request.GET.get("end") or "")

        # End date should include the full day -> add 1 day and use __lt
        if end_dt:
            end_dt = end_dt + timedelta(days=1)

        ctx["start_date"] = (request.GET.get("start") or "").strip()
        ctx["end_date"] = (request.GET.get("end") or "").strip()
    else:
        days = int(ctx["range_mode"])
        start_dt = timezone.now() - timedelta(days=days - 1)
        end_dt = None
        ctx["start_date"] = ""
        ctx["end_date"] = ""

    # Base queryset filtered by workspace scope (+ date range)
    batches_qs = LabelBatch.objects.filter(workspace_id__in=scoped_ids)

    if start_dt:
        batches_qs = batches_qs.filter(created_at__gte=start_dt)
    if end_dt:
        batches_qs = batches_qs.filter(created_at__lt=end_dt)

    # ---- KPI metrics ----
    ctx["workspace_count"] = len(scoped_ids)

    ctx["template_count"] = LabelTemplate.objects.filter(
        workspace_id__in=scoped_ids
    ).count()

    labels_total = batches_qs.aggregate(total=Sum("quantity")).get("total") or 0
    ctx["labels_total"] = int(labels_total)

    # ---- Chart: date-wise labels generated ----
    daily = (
        batches_qs
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("quantity"))
        .order_by("day")
    )

    chart_labels = [d["day"].strftime("%d %b") for d in daily]
    chart_values = [int(d["total"] or 0) for d in daily]

    ctx["chart_labels"] = json.dumps(chart_labels)
    ctx["chart_values"] = json.dumps(chart_values)

    # ---- Top categories by labels generated ----
    top_categories = (
        batches_qs
        .values("template__category")
        .annotate(total=Sum("quantity"))
        .order_by("-total")[:8]
    )

    cat_map = dict(LabelTemplate.CATEGORY_CHOICES)
    ctx["top_categories"] = [
        {
            "key": row["template__category"],
            "label": cat_map.get(row["template__category"], row["template__category"]),
            "total": int(row["total"] or 0),
        }
        for row in top_categories
    ]

    return render(request, "dashboard.html", ctx)

urlpatterns = [
    path("admin/", admin.site.urls),

    # ✅ Public landing
    path("", landingpage, name="landing"),

    # ✅ Logged-in dashboard
    path("dashboard/", dashboard_view, name="dashboard"),

    path("accounts/", include("accounts.urls")),
    path("workspaces/", include("workspaces.urls")),
    path("cms/", include("cms.urls")),
    path("billing/", include("billing.urls")),
    path("chatbot/", include("chatbot.urls")),
]

if settings.DEBUG or os.getenv("SERVE_MEDIA", "0") == "1":
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", django_serve, {"document_root": settings.MEDIA_ROOT}),
    ]


