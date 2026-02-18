import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
import re
from .retrieval import build_context_blocks
from django.conf import settings
from openai import OpenAI

# later: from openai import OpenAI
client = OpenAI(api_key=getattr(settings, "OPENAI_API_KEY", None) or None)

SUPPORT_EMAIL = "shyamagupta94@gmail.com"

SYSTEM_INSTRUCTIONS = f"""
You are Labelz Support Assistant.

GOAL:
Answer the user's question about Labelz using ONLY the provided context.

RULES (must follow):
1) Use ONLY the context provided in the user message. Do NOT invent features, UI paths, or docs.
2) Answer in 20–30 words. One short paragraph. No headings. No bullet points.
3) Be support-first: explain quickly what it is / what to do next.
4) If context does not contain the answer, say you don’t have it in Labelz docs yet and ask them to email {SUPPORT_EMAIL}.
5) Never mention "public blogs" or "workspace blogs". If docs are helpful, rely on the provided Support Docs only.
"""

@require_POST
def chat_public(request):
    """
    Landing page bot: KB + CMS + Links only.
    """
    body = json.loads(request.body.decode("utf-8") or "{}")
    user_msg = (body.get("message") or "").strip()

    context_text, cards = build_context_blocks(user_msg, user=None)

    # TODO: call OpenAI here (Phase 7)
    # For now: stub response
    answer = f"(stub) You asked: {user_msg}\n\nContext found:\n{context_text[:600]}"

    return JsonResponse({"answer": answer, "cards": cards})


@login_required
@require_POST
def chat_authed(request):
    """
    Logged-in bot: includes user knowledge (Phase 6).
    """
    body = json.loads(request.body.decode("utf-8") or "{}")
    user_msg = (body.get("message") or "").strip()

    context_text, cards = build_context_blocks(user_msg, user=request.user)

    # TODO: add user knowledge block here in Phase 6
    # TODO: call OpenAI here (Phase 7)

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

    context_text, doc_cards = build_context_blocks(user_query, user=user)

    prompt = f"""
User question:
{user_query}

Context (use ONLY this):
{context_text}

Write ONLY the answer text. 20–30 words.
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

    def _clamp_words(text: str, max_words: int = 30) -> str:
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

    # Hard enforce 20–30 words max (we enforce max; min is controlled by prompt)
    answer = _clamp_words(answer, 30)

    # Cards policy: show only if user seems to want help/steps/docs
    cards_to_send = []
    if _needs_docs(user_query):
        cms_cards = [c for c in (doc_cards or []) if c.get("kind") == "cms"]
        cards_to_send = (cms_cards[:2] if cms_cards else (doc_cards or [])[:2])


    return JsonResponse({
        "ok": True,
        "answer": answer,
        "cards": cards_to_send,
    })