import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import re
from .retrieval import build_context_blocks
from django.conf import settings
from openai import OpenAI
from .router import route_intent
# later: from openai import OpenAI
client = OpenAI(api_key=getattr(settings, "OPENAI_API_KEY", None) or None)

SUPPORT_EMAIL = "shyamagupta94@gmail.com"

SYSTEM_INSTRUCTIONS = f"""
You are Labelz Support Assistant. Labelz is a label design and generation tool for fashion, FMCG and any D2C/SMB retail brand. You can come design your packaging and label stickers like Canva and create unique single labels or in bulk in minutes

Style:
- Friendly, simple, helpful and not technical.
- 40-50 words max.
- If unsure, say you are not sure and ask them to email {SUPPORT_EMAIL}.

Rules:
- Use ONLY the provided Context.
- Do not invent features or UI paths.
"""

@require_POST
def chat_public(request):
    """
    Landing page bot: KB + CMS + Links only.
    """
    body = json.loads(request.body.decode("utf-8") or "{}")
    user_msg = (body.get("message") or "").strip()

    context_text, cards = build_context_blocks(user_msg, user=None)

    answer = f"(stub) You asked: {user_msg}\n\nContext found:\n{context_text[:600]}"

    return JsonResponse({"answer": answer, "cards": cards})


@login_required
@require_POST
def chat_authed(request):
    body = json.loads(request.body.decode("utf-8") or "{}")
    user_msg = (body.get("message") or "").strip()

    context_text, cards = build_context_blocks(user_msg, user=request.user)

    answer = f"(stub authed) You asked: {user_msg}\n\nContext found:\n{context_text[:600]}"
    return JsonResponse({"answer": answer, "cards": cards})

def _get_model():
    return getattr(settings, "OPENAI_MODEL", "gpt-5-nano")

@require_POST
@csrf_exempt  # later: remove and send CSRF token properly
def chat_api(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Invalid JSON"}, status=400)

    user_query = (payload.get("message") or "").strip()
    if not user_query:
        return JsonResponse({"ok": False, "error": "Message is required"}, status=400)

    user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
    is_authed = bool(getattr(request, "user", None) and request.user.is_authenticated)
    route = route_intent(user_query, is_authed=is_authed)
    user = request.user if (is_authed and route["needs_user_context"]) else None
    context_text, doc_cards = build_context_blocks(
        user_query,
        user=user,
        intent=route["intent"],
        search_terms=route["search_terms"],
    )

    prompt = f"""
Intent: {route['intent']}
User question: {user_query}

Context (use ONLY this):
{context_text}

Return only the answer text (40-50 words).
""".strip()

    def _needs_docs(q: str) -> bool:
        q = (q or "").lower()
        hints = [
            "how", "steps", "guide", "tutorial", "help", "docs",
            "blog", "video", "learn", "setup",
            "workspace", "generate", "template", "labels",
            "usage", "stats"
        ]
        return any(h in q for h in hints)

    def _clamp_words(text: str, max_words: int = 50) -> str:
        words = (text or "").strip().split()
        if len(words) <= max_words:
            return (text or "").strip()
        return " ".join(words[:max_words]).rstrip() + "…"

    # --- OpenAI call ---
    try:
        resp = client.responses.create(
            model=_get_model(),
            input=[
                {"role": "system", "content": SYSTEM_INSTRUCTIONS.strip()},
                {"role": "user", "content": prompt},
            ],
        )
        answer = (resp.output_text or "").strip()
    except Exception:
        answer = ""

    # Fallback if model returns nothing / fails
    if not answer:
        answer = f"I don’t have that in my Labelz docs yet. Please email {SUPPORT_EMAIL} and we’ll help you quickly."

    
    answer = _clamp_words(answer, 50)

    # Cards policy: show only if user seems to want help/steps/docs
    cards_to_send = []
    if route["needs_docs"]:
        cms_cards = [c for c in (doc_cards or []) if c.get("kind") == "cms"]
        cards_to_send = cms_cards[:2]


    return JsonResponse({
        "ok": True,
        "answer": answer,
        "cards": cards_to_send,
    })
