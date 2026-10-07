"""Legacy refund processor.

This module is executed when REFUND_V2 is "off" (the fixture default).
"""

from . import catalog, rates

SUPPORTED_CURRENCIES = {"USD", "EUR", "GBP"}

SETTLEMENT_ACCOUNTS = {
    "USD": "acct-usd-001",
    "EUR": "acct-eur-001",
    "GBP": "acct-gbp-001",
}


def refund(order):
    """Process a refund through the legacy pipeline."""
    sku = catalog.normalize_sku(order["sku"])
    item = catalog.lookup_item(sku)
    currency = order.get("currency", "USD")
    if currency not in SUPPORTED_CURRENCIES:
        # S2 edits the print below; the raise must stay on the same line.
        print(f"[legacy] rejecting currency {currency}")
        raise ValueError("invalid currency")
    amount = item["price_cents"] * order.get("quantity", 1)
    fee = rates.refund_fee_cents(amount)
    settlement = SETTLEMENT_ACCOUNTS[currency]
    return {
        "sku": sku,
        "refund_cents": amount - fee,
        "settlement_account": settlement,
        "processor": "legacy",
    }
