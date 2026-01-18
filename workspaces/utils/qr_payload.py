import json

EXCLUDE_QR_KEYS = {"serial", "barcode", "qrcode"}  # safety

def build_qr_payload(ean: str, gs1: str, field_values: dict, template_items: list) -> str:
    """
    Build QR encoded string from all variable fields on the template.
    Excludes SERIAL and special fields automatically by using template_items.
    """

    payload = {
        "ean": (ean or "").strip(),
        "gs1": (gs1 or "").strip(),
    }

    # Only include keys that actually exist on template (and are user fields)
    for it in (template_items or []):
        ft = (it.get("field_type") or "").upper()
        key = (it.get("key") or "").strip()
        if not key:
            continue
        if ft in ("BARCODE", "QRCODE", "SHAPE", "STATIC_TEXT", "SERIAL"):
            continue
        if key.lower() in EXCLUDE_QR_KEYS:
            continue

        payload[key] = (field_values.get(key, "") or "").strip()

    # compact JSON
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
