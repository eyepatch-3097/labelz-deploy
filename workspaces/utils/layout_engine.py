# workspaces/utils/layout_engine.py
from __future__ import annotations
import json
from typing import Any, Dict, List, Tuple


UI_MAX_SIDE_PX = 700.0

def get_ui_px_per_cm(width_cm: float, height_cm: float) -> float:
    max_side = max(width_cm, height_cm) or 1.0
    return UI_MAX_SIDE_PX / max_side

def ensure_layout_schema(raw: Any, width_cm: float, height_cm: float) -> Dict[str, Any]:
    """
    Normalizes stored layout into:
    {"_meta": {...}, "items":[...]}
    Supports legacy storage where raw might be a list.
    """
    ui_px_per_cm = get_ui_px_per_cm(width_cm, height_cm)

    if isinstance(raw, dict) and "items" in raw:
        meta = raw.get("_meta") or {}
        # backfill meta if missing
        meta.setdefault("ui_max_side_px", UI_MAX_SIDE_PX)
        meta.setdefault("ui_px_per_cm", ui_px_per_cm)
        return {"_meta": meta, "items": raw.get("items") or []}

    if isinstance(raw, list):
        return {
            "_meta": {"ui_max_side_px": UI_MAX_SIDE_PX, "ui_px_per_cm": ui_px_per_cm},
            "items": raw,
        }

    return {
        "_meta": {"ui_max_side_px": UI_MAX_SIDE_PX, "ui_px_per_cm": ui_px_per_cm},
        "items": [],
    }

def canvas_ui_size(width_cm: float, height_cm: float, ui_px_per_cm: float) -> Tuple[int, int]:
    return (
        int(round(width_cm * ui_px_per_cm)),
        int(round(height_cm * ui_px_per_cm)),
    )

def px_to_mm(px: float, ui_px_per_cm: float) -> float:
    # 1 cm = 10 mm
    return (px / ui_px_per_cm) * 10.0

# workspaces/utils/layout_engine.py
def normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    ft = (item.get("field_type") or "TEXT").upper()
    ta = (item.get("text_align") or "left").lower()
    if ta not in ("left", "center", "right"):
        ta = "left"

    return {
        "name": (item.get("name") or "").strip() or (item.get("key") or "Field"),
        "key": (item.get("key") or "").strip(),
        "field_type": ft,

        "workspace_field_id": item.get("workspace_field_id") or None,
        "show_label": bool(item.get("show_label", True)),

        "x": int(item.get("x") or 0),
        "y": int(item.get("y") or 0),
        "width": max(1, int(item.get("width") or 10)),
        "height": max(1, int(item.get("height") or 10)),
        "z_index": int(item.get("z_index") or 0),

        "font_family": (item.get("font_family") or "Inter").strip() or "Inter",
        "font_size": int(item.get("font_size") or 14),
        "font_bold": bool(item.get("font_bold")),
        "font_italic": bool(item.get("font_italic")),
        "font_underline": bool(item.get("font_underline")),
        "text_align": ta,
        "text_color": (item.get("text_color") or "#000000").strip() or "#000000",
        "bg_color": (item.get("bg_color") or "transparent").strip() or "transparent",

        "shape_type": (item.get("shape_type") or "RECT").upper(),
        "shape_color": (item.get("shape_color") or "#000000").strip() or "#000000",
    }
    
def normalize_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        out.append(normalize_item(it))
    return out

def save_layout_to_template(template, incoming_items: List[Dict[str, Any]]) -> None:
    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)
    ui_px_per_cm = get_ui_px_per_cm(width_cm, height_cm)

    payload = {
        "_meta": {
            "ui_max_side_px": UI_MAX_SIDE_PX,
            "ui_px_per_cm": ui_px_per_cm,
        },
        "items": normalize_items(incoming_items),
    }
    template.layout_json = payload
    template.save(update_fields=["layout_json"])

def load_layout_from_template(template) -> Dict[str, Any]:
    width_cm = float(template.width_cm or 10)
    height_cm = float(template.height_cm or 10)
    raw = template.layout_json or {}
    return ensure_layout_schema(raw, width_cm, height_cm)

def compute_label_engine(width_cm: float, height_cm: float, dpi: int, ui_max_side_px: int = 700) -> dict:
    """
    Canonical: real_px (DPI-based)
    UI: scaled canvas that fits within ui_max_side_px
    """
    width_cm = float(width_cm or 0) or 10.0
    height_cm = float(height_cm or 0) or 10.0
    dpi = int(dpi or 300)

    # 1 inch = 2.54 cm
    real_px_per_cm = dpi / 2.54
    real_w_px = int(round(width_cm * real_px_per_cm))
    real_h_px = int(round(height_cm * real_px_per_cm))

    max_real_side = max(real_w_px, real_h_px, 1)
    ui_scale = float(ui_max_side_px) / float(max_real_side)

    ui_w_px = int(round(real_w_px * ui_scale))
    ui_h_px = int(round(real_h_px * ui_scale))
    ui_px_per_cm = real_px_per_cm * ui_scale

    return {
        "width_cm": width_cm,
        "height_cm": height_cm,
        "dpi": dpi,
        "real_px_per_cm": real_px_per_cm,
        "real_w_px": real_w_px,
        "real_h_px": real_h_px,
        "ui_scale": ui_scale,
        "ui_w_px": ui_w_px,
        "ui_h_px": ui_h_px,
        "ui_px_per_cm": ui_px_per_cm,
    }


def ui_to_real(ui_value: int, ui_scale: float) -> int:
    if not ui_scale or ui_scale <= 0:
        return int(ui_value)
    return int(round(float(ui_value) / float(ui_scale)))


def real_to_ui(real_value: int, ui_scale: float) -> int:
    return int(round(float(real_value) * float(ui_scale)))