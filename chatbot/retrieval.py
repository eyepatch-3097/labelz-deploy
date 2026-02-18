from django.db.models import Q
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
import re
from cms.models import CMSPost
from .models import LabelzKBEntry, ImportantLink


def _norm(q: str) -> str:
    q = (q or "").lower().strip()
    q = re.sub(r"[^a-z0-9\s]", " ", q)
    q = re.sub(r"\s+", " ", q)
    return q

def kb_search(query: str, limit: int = 5):
    q = _norm(query)
    if not q:
        return LabelzKBEntry.objects.none()

    # optional: treat questions like "what is a workspace" as keyword "workspace"
    tokens = [t for t in q.split() if t not in {"what", "is", "a", "an", "the", "define", "explain", "meaning"}]
    key = " ".join(tokens) if tokens else q

    return (
        LabelzKBEntry.objects
        .filter(is_active=True)  # if you have it; otherwise remove
        .filter(
            Q(title__icontains=key) |
            Q(content__icontains=key)
        )
        .order_by("-updated_at", "-id")[:limit]
    )


def links_search(query: str, limit=5):
    if not query:
        return list(ImportantLink.objects.filter(is_active=True)[:3])

    qs = ImportantLink.objects.filter(is_active=True).filter(
        Q(title__icontains=query) |
        Q(tags__icontains=query) |
        Q(description__icontains=query)
    ).order_by("-created_at")

    return list(qs[:limit])


def cms_search(query: str, limit=5):
    if not query:
        return []

    search_query = SearchQuery(query)

    vector = (
        SearchVector("title", weight="A") +
        SearchVector("meta_description", weight="B") +
        SearchVector("blog_html", weight="C") +
        SearchVector("video_description", weight="C")
    )

    qs = (
        CMSPost.objects
        .filter(status=CMSPost.STATUS_PUBLISHED)
        .annotate(rank=SearchRank(vector, search_query))
        .filter(rank__gte=0.05)
        .order_by("-rank", "-published_at", "-id")
    )

    return list(qs[:limit])


def build_context_blocks(query: str, user=None):
    """
    Returns:
      context_text (string)
      doc_cards (list of dict for UI)
    """
    kb = kb_search(query)
    links = links_search(query)
    docs = cms_search(query)

    parts = []
    doc_cards = []

    if kb:
        parts.append("## Labelz Knowledge Base\n" + "\n\n".join(
            f"- **{e.title}** ({e.category})\n{e.content.strip()[:1200]}"
            for e in kb
        ))

    if links:
        parts.append("## Important Links\n" + "\n\n".join(
            f"- **{l.title}**: {l.url}\n{(l.description or '').strip()[:400]}"
            for l in links
        ))

    if docs:
        parts.append("## Support Docs (Blogs/Videos)\n" + "\n\n".join(
            f"- **{d.title}** ({d.type})\n" +
            (
                (d.meta_description or '').strip()[:400]
                if d.type == d.TYPE_BLOG
                else (d.video_description or '').strip()[:400]
            )
            for d in docs
        ))

    

    
    for d in docs[:3]:
        doc_cards.append({
            "kind": "cms",
            "title": d.title,
            "type": d.type,
            "url": f"/cms/post/{d.slug}/" if hasattr(d, "slug") else "",
            "description": (
                (d.meta_description or "")[:160]
                if d.type == d.TYPE_BLOG
                else (d.video_description or "")[:160]
            ),
            "image_url": d.preview_image.url if getattr(d, "preview_image", None) else "",
        })
    for l in links[:2]:
        doc_cards.append({
            "kind": "link",
            "title": l.title,
            "type": "LINK",
            "url": l.url,
            "description": (l.description or "")[:160],
            "image_url": "",
        })

    from .user_context import build_user_context

    if user is not None:
        user_ctx_text, user_cards = build_user_context(user, query=query)
        parts.append("## User Context\n" + user_ctx_text)
        doc_cards = (user_cards or []) + (doc_cards or [])

    return "\n\n".join(parts).strip(), doc_cards
