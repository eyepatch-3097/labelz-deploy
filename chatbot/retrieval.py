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


def build_context_blocks(query, user=None, intent="support", search_terms=None):
    search_terms = search_terms or [query]

    kb = kb_search(search_terms, intent=intent)
    links = links_search(search_terms, intent=intent) if intent in ("general","pricing") else []
    docs = cms_search(search_terms, intent=intent)  # still small

    user_block = ""
    user_cards = []

    if user and intent in ("support","feature"):
        user_block = user_context_summary(user)   # you already added this
        # no user_cards needed unless you want

    # Build tiny context_text (clip aggressively)
    def clip(s, n): return (s or "").strip()[:n]

    parts = []
    if intent == "pricing":
        parts.append("## Pricing\n" + "\n".join(f"- {clip(e.content, 700)}" for e in kb))
    else:
        if kb:
            parts.append("## KB\n" + "\n".join(f"- {e.title}: {clip(e.content, 450)}" for e in kb))

    if user_block:
        parts.append("## User Context\n" + clip(user_block, 900))

    if docs:
        parts.append("## Support Docs\n" + "\n".join(
            f"- {d.title}: {clip(d.meta_description, 250)}" for d in docs
        ))

    # Cards: only CMS + links
    doc_cards = []
    for d in docs[:2]:
        doc_cards.append({
            "kind": "cms",
            "title": d.title,
            "type": d.type,
            "url": f"/cms/post/{d.slug}/",  # ✅ FIXED
            "description": clip(d.meta_description, 160),
            "image_url": d.preview_image.url if getattr(d, "preview_image", None) else "",
        })
    for l in links[:1]:
        doc_cards.append({
            "kind": "link",
            "title": l.title,
            "type": "LINK",
            "url": l.url,
            "description": clip(l.description, 160),
            "image_url": "",
        })

    return "\n\n".join(parts).strip(), doc_cards
