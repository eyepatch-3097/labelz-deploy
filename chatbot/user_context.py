# chatbot/user_context.py

from datetime import timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Max

from workspaces.models import Workspace, LabelTemplate, LabelBatch


def get_accessible_workspaces(user):
    if not getattr(user, "org", None):
        return Workspace.objects.none()

    if user.role == user.ROLE_ADMIN:
        return Workspace.objects.filter(org=user.org)

    return Workspace.objects.filter(
        org=user.org,
        memberships__user=user
    ).distinct()


def build_user_context(user, query=""):
    """
    Returns:
      context_text (string)
      action_cards (list)
    """

    workspaces = get_accessible_workspaces(user)
    ws_ids = list(workspaces.values_list("id", flat=True))

    if not ws_ids:
        return "User has no workspaces yet.", []

    last_30_days = timezone.now() - timedelta(days=30)

    batches = LabelBatch.objects.filter(
        workspace_id__in=ws_ids,
        created_at__gte=last_30_days
    )

    total_labels_30d = batches.aggregate(total=Sum("quantity"))["total"] or 0
    last_batch_time = batches.aggregate(last=Max("created_at"))["last"]

    # template counts per workspace
    template_counts = (
        LabelTemplate.objects
        .filter(workspace_id__in=ws_ids)
        .values("workspace_id")
        .annotate(count=Count("id"))
    )
    template_map = {r["workspace_id"]: r["count"] for r in template_counts}

    # usage per workspace
    usage_per_ws = (
        batches.values("workspace_id")
        .annotate(total=Sum("quantity"), last=Max("created_at"))
    )
    usage_map = {r["workspace_id"]: r for r in usage_per_ws}

    # pick 3 most recently active workspaces
    sorted_ws = sorted(
        workspaces,
        key=lambda w: usage_map.get(w.id, {}).get("last") or timezone.datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )[:3]

    lines = []
    lines.append(f"Org: {user.org.name}")
    lines.append(f"Accessible workspaces: {len(ws_ids)}")
    lines.append(f"Labels generated (30d): {int(total_labels_30d)}")

    if last_batch_time:
        lines.append(f"Last label batch: {last_batch_time.strftime('%d %b %Y')}")

    lines.append("Recent workspaces:")
    for w in sorted_ws:
        u = usage_map.get(w.id, {})
        tcount = template_map.get(w.id, 0)
        lines.append(
            f"- {w.name}: {int(u.get('total') or 0)} labels / 30d, {tcount} templates"
        )

    # 🔹 Action cards
    cards = []
    for w in sorted_ws:
        cards.append({
            "kind": "action",
            "title": f"Generate labels in {w.name}",
            "type": "WORKSPACE",
            "url": f"/workspaces/{w.id}/generate/",
            "description": "Start printing labels",
            "image_url": "",
        })
        cards.append({
            "kind": "action",
            "title": f"View templates in {w.name}",
            "type": "WORKSPACE",
            "url": f"/workspaces/{w.id}/templates/",
            "description": "Manage templates",
            "image_url": "",
        })

    return "\n".join(lines), cards
