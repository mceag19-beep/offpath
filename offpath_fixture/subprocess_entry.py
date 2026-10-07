"""Run a refund in a child process (used by the S5 scenario).

Invoked as: python -m offpath_fixture.subprocess_entry
The ValueError raised here is NOT visible to the parent process's
coverage collection, which is the visibility gap S5 studies.
"""

from . import checkout


def main():
    order = {"sku": "sku-200", "quantity": 1, "currency": "JPY"}
    checkout.process_refund(order)


if __name__ == "__main__":
    main()
