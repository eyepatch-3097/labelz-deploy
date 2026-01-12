from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.conf import settings
from django.conf.urls.static import static

from workspaces.models import Workspace


def landing_page(request):
    # Public landing page
    return render(request, "landingpage.html")


@login_required
def dashboard_view(request):
    user = request.user
    org_users = []
    workspaces = []

    if user.org:
        User = get_user_model()
        org_users = User.objects.filter(org=user.org).order_by("-date_joined")
        workspaces = Workspace.objects.filter(org=user.org).order_by("-created_at")

    return render(
        request,
        "dashboard.html",
        {
            "org_users": org_users,
            "workspaces": workspaces,
        },
    )


urlpatterns = [
    path("admin/", admin.site.urls),

    # ✅ Public landing
    path("", landing_page, name="landing"),

    # ✅ Logged-in dashboard
    path("dashboard/", dashboard_view, name="dashboard"),

    path("accounts/", include("accounts.urls")),
    path("workspaces/", include("workspaces.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
