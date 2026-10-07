"""In-process control test.

Passes, exercises catalog/rates only, and never touches pricing.py or
legacy_processor.py. Used to prove that (a) a passing run with zero
intersection is RESOLVED, not UNKNOWN, and (b) healthy in-process
visibility is not misclassified as insufficient.
"""

from offpath_fixture import catalog, rates


def test_catalog_paths():
    sku = catalog.normalize_sku(" 100 ")
    assert sku == "SKU-100"
    item = catalog.lookup_item(sku)
    assert item["price_cents"] == 1299
    total = catalog.price_with_tax(item, "eu")
    assert total > item["price_cents"]
    receipt = catalog.format_receipt({"sku": sku, "quantity": 2}, 2598)
    assert "SKU-100" in receipt
    assert rates.refund_fee_cents(10_000) > 0
