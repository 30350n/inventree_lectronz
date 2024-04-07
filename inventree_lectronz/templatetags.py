import re

from plugin.templatetags.plugin_extras import register

@register.filter
def lectronz_float_eq(a, b):
    return abs(float(a) - float(b)) < 0.001

@register.filter
def lectronz_valid_customer_reference(reference):
    return VALID_CUSTOMER_REFERENCE.fullmatch(reference) is not None

VALID_CUSTOMER_REFERENCE = re.compile(r"^#?(\d+)$")

@register.filter
def lectronz_invoice_url(order_id):
    return f"https://lectronz.com/seller/orders/{order_id}/customer_invoice.pdf"
