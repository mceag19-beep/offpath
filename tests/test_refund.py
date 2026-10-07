"""The failing test used by scenarios S1-S4.

Orders a refund in JPY, which the legacy processor rejects with
ValueError("invalid currency") while REFUND_V2=off.
"""

import pytest

from offpath_fixture import checkout


@pytest.fixture(autouse=True)
def _flag_off(monkeypatch):
    monkeypatch.setenv("REFUND_V2", "off")


def test_refund():
    order = {
        "sku": "sku-200",
        "quantity": 1,
        "currency": "JPY",  # unsupported by the legacy processor
    }
    result = checkout.process_refund(order)
    assert result["refund_cents"] > 0
