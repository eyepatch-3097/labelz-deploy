# cms/sanitize.py
from __future__ import annotations

import re
import bleach
from bleach.css_sanitizer import CSSSanitizer


# Allow tables, lists, headings, images, links, basic formatting.
BLOG_ALLOWED_TAGS = [
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "b", "em", "i", "u", "s",
    "blockquote", "pre", "code",
    "ul", "ol", "li",
    "table", "thead", "tbody", "tfoot", "tr", "th", "td",
    "span", "div",
    "a",
    "img",
]

BLOG_ALLOWED_ATTRS = {
    "*": ["class", "style"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "title", "width", "height", "style"],
    "table": ["border", "cellpadding", "cellspacing", "style"],
    "th": ["colspan", "rowspan", "style"],
    "td": ["colspan", "rowspan", "style"],
}

# Keep styles safe + limited (so tables/lists/images look right but no weird CSS attacks)
BLOG_ALLOWED_CSS_PROPS = [
    "color", "background-color",
    "font-size", "font-weight", "font-style", "text-decoration",
    "text-align", "line-height",
    "border", "border-width", "border-style", "border-color", "border-collapse",
    "padding", "padding-left", "padding-right", "padding-top", "padding-bottom",
    "margin", "margin-left", "margin-right", "margin-top", "margin-bottom",
    "width", "height", "max-width", "min-width", "max-height", "min-height",
    "vertical-align",
    "list-style-type",
    "border-radius",
    "white-space",
]

blog_css_sanitizer = CSSSanitizer(allowed_css_properties=BLOG_ALLOWED_CSS_PROPS)


def sanitize_blog_html(html: str) -> str:
    html = (html or "").strip()
    if not html:
        return ""

    cleaned = bleach.clean(
        html,
        tags=BLOG_ALLOWED_TAGS,
        attributes=BLOG_ALLOWED_ATTRS,
        protocols=["http", "https", "mailto"],
        strip=True,
        css_sanitizer=blog_css_sanitizer,
    )

    # Post-processing: enforce safe link attributes
    # (Bleach won't automatically set rel/target)
    # We do a simple replace on <a ... target="_blank"> etc is hard without parser,
    # so we keep it minimal: strip javascript: already handled by bleach protocols.
    return cleaned


# Video embed: allow ONLY a YouTube iframe embed.
VIDEO_ALLOWED_TAGS = ["iframe"]
VIDEO_ALLOWED_ATTRS = {
    "iframe": [
        "src", "width", "height", "title",
        "frameborder", "allow", "allowfullscreen",
        "referrerpolicy", "loading",
    ]
}

# strict: youtube embed only
YOUTUBE_EMBED_RE = re.compile(r"^https://www\.youtube\.com/embed/[\w-]+(\?.*)?$", re.I)


def sanitize_youtube_embed_html(html: str) -> str:
    html = (html or "").strip()
    if not html:
        return ""

    cleaned = bleach.clean(
        html,
        tags=VIDEO_ALLOWED_TAGS,
        attributes=VIDEO_ALLOWED_ATTRS,
        protocols=["http", "https"],
        strip=True,
    ).strip()

    # Validate that the iframe src is a YouTube embed URL
    # Extract src quickly via regex (since we allow only iframe, this is safe enough)
    m = re.search(r'src\s*=\s*["\']([^"\']+)["\']', cleaned, flags=re.I)
    src = (m.group(1).strip() if m else "")

    if not src or not YOUTUBE_EMBED_RE.match(src):
        return ""  # treat as invalid

    return cleaned
