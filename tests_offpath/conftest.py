"""Shared fixtures for the OffPath MVP test suite.

The suite drives the REAL implementation (git diff, coverage.py,
traceback parsing) against the REAL fixture app, with the timeline
isolated per-session via OFFPATH_DIR so the developer's `.offpath/`
history is never touched. Fixture sources mutated mid-suite are restored
byte-for-byte afterwards.
"""

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PRICING = ROOT / "offpath_fixture" / "pricing.py"
LEGACY = ROOT / "offpath_fixture" / "legacy_processor.py"

PYTEST_CMD = [sys.executable, "-m", "pytest", "tests/test_refund.py", "-x"]
SUBPROCESS_CMD = [
    sys.executable,
    "-m",
    "pytest",
    "tests/test_subprocess_refund.py",
    "-x",
]
CONTROL_CMD = [
    sys.executable,
    "-m",
    "pytest",
    "tests/test_control_catalog.py",
    "-x",
]

PRICING_S1 = '''"""New refund pipeline (V2). Executed only when REFUND_V2=on."""

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
    # S1: attempt to handle JPY here
    if currency == "JPY":
        net = int(net * 0.95)
    print(f"[v2] refund {net} cents in {currency} (s1)")
    return {
        "sku": sku,
        "refund_cents": net,
        "settlement_account": f"acct-{currency.lower()}-v2",
        "processor": "v2",
    }
'''

PRICING_S1B = PRICING_S1.replace("(s1)", "(s1b)")
PRICING_S1C = PRICING_S1.replace("(s1)", "(s1c)")
PRICING_S1D = PRICING_S1.replace("(s1)", "(s1d)")

LEGACY_S2 = '''"""Legacy refund processor.

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
        print(f"[legacy] rejecting currency {currency} (s2: on-path edit)")
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
'''

LEGACY_S3 = '''"""Legacy refund processor.

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
        print(f"[legacy] rejecting currency {currency} (s3)")
        if currency != "JPY":
            raise ValueError("invalid currency")
    amount = item["price_cents"] * order.get("quantity", 1)
    fee = rates.refund_fee_cents(amount)
    settlement = SETTLEMENT_ACCOUNTS[currency]   # KeyError for JPY: deeper failure
    return {
        "sku": sku,
        "refund_cents": amount - fee,
        "settlement_account": settlement,
        "processor": "legacy",
    }
'''


@pytest.fixture(scope="session", autouse=True)
def isolate_timeline(tmp_path_factory):
    """Point OFFPATH_DIR at a session temp dir for the whole suite."""
    d = tmp_path_factory.mktemp("offpath-timeline")
    os.environ["OFFPATH_DIR"] = str(d)
    yield d


@pytest.fixture(scope="session")
def work():
    """Session helper: run attempts, mutate/restore fixture sources."""
    from offpath import runner, store
    from offpath.project import find_root

    root = find_root(ROOT)
    saved = {}
    for path in (PRICING, LEGACY):
        saved[path] = path.read_bytes()

    class Work:
        def __init__(self):
            self.events = []

        def run(self, cmd):
            event, exit_code = runner.do_run(list(cmd), root=root)
            self.events.append(event)
            return event, exit_code

        def events_now(self):
            sdir = store.resolve_state_dir(root)
            return store.load_events(sdir)

    w = Work()
    yield w
    for path, data in saved.items():
        path.write_bytes(data)


@contextmanager
def mutate(path: Path, content: str):
    path.write_bytes(content.replace("\n", "\n").encode("utf-8"))
    try:
        yield
    finally:
        subprocess.run(
            ["git", "checkout", "--", path.relative_to(ROOT).as_posix()],
            cwd=str(ROOT),
            capture_output=True,
        )


def cli(*args, offpath_dir, extra_env=None):
    """Run the offpath CLI in a subprocess; return (returncode, stdout)."""
    env = dict(os.environ, OFFPATH_DIR=str(offpath_dir))
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, "-m", "offpath", *args],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout + proc.stderr
