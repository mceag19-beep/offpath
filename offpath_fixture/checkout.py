"""Checkout / refund routing.

Routes to the legacy processor when REFUND_V2 is "off" (the fixture
default) and to the V2 pricing pipeline when REFUND_V2 is "on".
Imports are lazy so the inactive processor module is never imported
on the other path; this is what makes off-path edits invisible to
coverage, which is exactly the situation the spike studies.
"""

import os

from . import catalog


def process_refund(order):
    """Route a refund to the active processor."""
    order = dict(order)
    order["sku"] = catalog.normalize_sku(order["sku"])
    flag = os.environ.get("REFUND_V2", "off")
    if flag == "on":
        from . import pricing

        return pricing.refund(order)
    from . import legacy_processor

    return legacy_processor.refund(order)
