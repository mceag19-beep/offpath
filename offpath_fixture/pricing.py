"""New refund pipeline (V2). Executed only when REFUND_V2=on."""

from . import catalog, rates

LOYALTY_DISCOUNT_PCT = 5


def refund(order):
    """Process a refund through the V2 pipeline."""
    sku = catalog.normalize_sku(order["sku"])
    item = catalog.lookup_item(sku)
    currency = order.get("currency", "USD")
    amount = item["price_cents"] * order.get("quantity", 1)
    if order.get("loyalty"):
        amount = amount * (100 - LOYALTY_DISCOUNT_PCT) // 100
    fee = rates.refund_fee_cents(amount)
    net = amount - fee
    # S1 edits the lines below; none of them run while REFUND_V2=off.
    print(f"[v2] refund {net} cents in {currency}")
    return {
        "sku": sku,
        "refund_cents": net,
        "settlement_account": f"acct-{currency.lower()}-v2",
        "processor": "v2",
    }
