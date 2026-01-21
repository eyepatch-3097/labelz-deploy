from django import template
register = template.Library()

@register.filter
def paise_to_inr(value):
    try:
        v = int(value or 0)
    except:
        v =0
    
    return f"{v/100:.2f}"