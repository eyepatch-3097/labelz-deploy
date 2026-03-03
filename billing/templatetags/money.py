from decimal import Decimal, ROUND_HALF_UP
from django import template
register = template.Library()

@register.filter
def paise_to_inr(value):
    try:
        v = int(value or 0)
    except:
        v =0
    
    return f"{v/100:.2f}"


@register.filter
def cents_to_usd(value):
    try:
        amt = (Decimal(int(value or 0)) / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return format(amt, "f")
    except Exception:
        return "0.00"
