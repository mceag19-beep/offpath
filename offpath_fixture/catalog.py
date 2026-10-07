"""Item catalog with region rules."""

from . import rates

_ITEMS = {
    "SKU-100": {"title": "USB-C cable", "price_cents": 1299},
    "SKU-200": {"title": "Laptop stand", "price_cents": 4599},
    "SKU-300": {"title": "Mechanical keyboard", "price_cents": 8900},
}

_REGIONS = {
    "us": {"tax_pct": 8, "currency": "USD"},
    "eu": {"tax_pct": 21, "currency": "EUR"},
    "uk": {"tax_pct": 20, "currency": "GBP"},
}


def normalize_sku(sku):
    sku = sku.strip().upper()
    if not sku.startswith("SKU-"):
        sku = f"SKU-{sku}"
    return sku


def lookup_item(sku):
    item = _ITEMS.get(sku)
    if item is None:
        raise KeyError(f"unknown sku {sku}")
    return item


def region_rules(region):
    return _REGIONS.get(region, _REGIONS["us"])


def price_with_tax(item, region):
    rules = region_rules(region)
    tax = item["price_cents"] * rules["tax_pct"] // 100
    return item["price_cents"] + tax


def format_receipt(order, refund_cents):
    lines = [
        f"sku: {order['sku']}",
        f"qty: {order.get('quantity', 1)}",
        f"refund_cents: {refund_cents}",
        f"fee_note: {rates.fee_note()}",
    ]
    return "\n".join(lines)
