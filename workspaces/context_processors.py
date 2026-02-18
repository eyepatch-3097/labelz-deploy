from workspaces.models import Workspace

def sidebar_recent_workspaces(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or not getattr(user, "org", None):
        return {"sidebar_recent_workspaces": []}

    # Latest 3 for org (or user-scoped if you prefer)
    qs = Workspace.objects.filter(org=user.org).order_by("-created_at")[:3]
    return {"sidebar_recent_workspaces": list(qs)}
