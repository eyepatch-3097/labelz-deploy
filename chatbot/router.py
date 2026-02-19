import json
from django.conf import settings
from openai import OpenAI

client = OpenAI(api_key=getattr(settings, "OPENAI_API_KEY", None) or None)

def route_intent(user_query: str, is_authed: bool) -> dict:
    """
    Returns dict:
      intent: general|pricing|feature|support
      needs_user_context: bool
      needs_docs: bool
      search_terms: list[str] (max 5)
    """
    sys = """You are an intent router for a support chatbot.
Return ONLY valid JSON (no markdown, no extra text).
Pick intent from: general, pricing, feature, support.

Rules:
- general: fit, industry, use-cases, what can it do for my business
- pricing: pricing, cost, plan, subscription, limits, renewal
- feature: capabilities, export, batch size, formats, integrations, limits
- support: how-to steps, navigation, can't find, errors, troubleshooting

Decide if user context is needed:
- needs_user_context=true ONLY when intent is feature/support AND user is authenticated.

Decide if docs are needed:
- needs_docs=true when user asks for guide/steps/tutorial/blog/video or question seems complex.

Also output search_terms: 2–5 short phrases to search in KB/CMS/Links.
"""

    prompt = {
        "query": user_query,
        "is_authenticated": bool(is_authed),
    }

    resp = client.responses.create(
        model=getattr(settings, "OPENAI_MODEL", "gpt-5-nano"),
        input=[
            {"role": "system", "content": sys},
            {"role": "user", "content": json.dumps(prompt)},
        ],
    )

    raw = (resp.output_text or "").strip()
    try:
        data = json.loads(raw)
    except Exception:
        # safe fallback
        data = {
            "intent": "support",
            "needs_user_context": bool(is_authed),
            "needs_docs": True,
            "search_terms": [user_query[:60]],
        }

    # Normalize / clamp
    data["intent"] = data.get("intent", "support")
    if data["intent"] not in ("general", "pricing", "feature", "support"):
        data["intent"] = "support"

    data["needs_user_context"] = bool(data.get("needs_user_context", False)) and bool(is_authed)
    data["needs_docs"] = bool(data.get("needs_docs", False))

    terms = data.get("search_terms") or []
    terms = [t.strip() for t in terms if isinstance(t, str) and t.strip()]
    data["search_terms"] = terms[:5] or [user_query[:60]]

    return data
