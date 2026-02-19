from django.db.models import Q
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
import re
from cms.models import CMSPost
from .models import LabelzKBEntry, ImportantLink
from django.db import connection
from .user_context import build_user_context


def _norm(q: str) -> str:
    q = (q or "").lower().strip()
    q = re.sub(r"[^a-z0-9\s]", " ", q)
    q = re.sub(r"\s+", " ", q)
    return q

def _terms_to_text(search_terms, fallback=""):
    if isinstance(search_terms, (list, tuple)):
        return " ".join([str(t).strip() for t in search_terms if str(t).strip()])
    return (search_terms or fallback or "").strip()

def kb_search(search_terms, intent="support", limit: int = 5):
    query = _terms_to_text(search_terms)
    q = _norm(query)
    if not q:
        return LabelzKBEntry.objects.none()

    tokens = [t for t in q.split() if t not in {"what","is","a","an","the","define","explain","meaning"}]
    key = " ".join(tokens) if tokens else q

    qs = LabelzKBEntry.objects.all()

    # ✅ only if these fields exist in your model:
    if hasattr(LabelzKBEntry, "is_active"):
        qs = qs.filter(is_active=True)

    qs = LabelzKBEntry.objects.filter(is_active=True)

    # 1️⃣ Filter by category first (strong signal)
    if intent == "pricing":
        qs = qs.filter(category=LabelzKBEntry.CATEGORY_PRICING)
    elif intent == "general":
        qs = qs.filter(category=LabelzKBEntry.CATEGORY_GENERAL)
    elif intent == "feature":
        qs = qs.filter(category=LabelzKBEntry.CATEGORY_FEATURES)
    elif intent == "support":
        qs = qs.filter(category__in=[
            LabelzKBEntry.CATEGORY_SUPPORT,
            LabelzKBEntry.CATEGORY_FEATURES
        ])

    # 2️⃣ Then optionally refine
    if key:
        qs = qs.filter(
            Q(title__icontains=key) |
            Q(content__icontains=key) |
            Q(tags__icontains=key)
        )
    
    results = list(qs[:limit])

    # 3️⃣ Fallback: if nothing matched, return category-level entries anyway
    if not results:
        results = list(
            LabelzKBEntry.objects.filter(
                category=qs.query.where.children[0].rhs  # category filter
            )[:limit]
        )
    
    return results
    
# ✅ only if updated_at exists
    if hasattr(LabelzKBEntry, "updated_at"):
        qs = qs.order_by("-updated_at", "-id")
    else:
        qs = qs.order_by("-id")

    return list(qs[:limit])


def links_search(search_terms, intent="support", limit=5):
    query = _terms_to_text(search_terms)
    qs = ImportantLink.objects.all()
    if hasattr(ImportantLink, "is_active"):
        qs = qs.filter(is_active=True)

    if not query:
        return list(qs.order_by("-id")[:3])

    qs = qs.filter(
        Q(title__icontains=query) |
        Q(tags__icontains=query) |
        Q(description__icontains=query)
    ).order_by("-id")

    return list(qs[:limit])


def cms_search(search_terms, intent="support", limit=5):
    query = _terms_to_text(search_terms)
    if not query:
        return []

    qs = CMSPost.objects.filter(status=CMSPost.STATUS_PUBLISHED)

    if connection.vendor == "postgresql":
        from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

        search_query = SearchQuery(query)
        vector = (
            SearchVector("title", weight="A") +
            SearchVector("meta_description", weight="B") +
            SearchVector("blog_html", weight="C") +
            SearchVector("video_description", weight="C")
        )
        qs = (
            qs.annotate(rank=SearchRank(vector, search_query))
              .filter(rank__gte=0.05)
              .order_by("-rank", "-published_at", "-id")
        )
    else:
        # ✅ SQLite/dev fallback
        qs = qs.filter(
            Q(title__icontains=query) |
            Q(meta_description__icontains=query) |
            Q(blog_html__icontains=query) |
            Q(video_description__icontains=query)
        ).order_by("-published_at", "-id")

    return list(qs[:limit])


def build_context_blocks(query, user=None, intent="support", search_terms=None):
    search_terms = search_terms or [query]

    kb = kb_search(search_terms, intent=intent)
    links = links_search(search_terms, intent=intent) if intent in ("general","pricing") else []
    docs = cms_search(search_terms, intent=intent)  # still small
    
    user_block = ""
    user_cards = []

    pinned = LabelzKBEntry.objects.filter(is_active=True, is_pinned=True)[:2]

    if user and intent in ("support","feature"):
        user_block, user_cards = build_user_context(user, query=query)
       

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
    doc_cards = (user_cards or []) + doc_cards
    return "\n\n".join(parts).strip(), doc_cards
