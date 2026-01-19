from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404

from .models import CMSPost


def content_list(request):
    """
    Paginated listing of all published content.
    Optional filter: ?type=BLOG or ?type=VIDEO
    """
    qs = CMSPost.objects.filter(status=CMSPost.STATUS_PUBLISHED).order_by(
        "-published_at", "-created_at", "-id"
    )

    t = (request.GET.get("type") or "").strip().upper()
    if t in (CMSPost.TYPE_BLOG, CMSPost.TYPE_VIDEO):
        qs = qs.filter(type=t)

    paginator = Paginator(qs, 12)  # 12 cards/page
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    return render(request, "cms/content_list.html", {"page_obj": page_obj, "filter_type": t})


def post_detail(request, slug):
    post = get_object_or_404(CMSPost, slug=slug, status=CMSPost.STATUS_PUBLISHED)

    if post.type == CMSPost.TYPE_BLOG:
        tpl = "cms/blog_detail.html"
    else:
        tpl = "cms/video_detail.html"

    return render(request, tpl, {"post": post})
