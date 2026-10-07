"""Normalized failure signatures.

Signature inputs: exception type + normalized message template + measured
frame-chain identity. The event stores the full structured inputs (not just
the final hash) so the signature can be independently recomputed from the
raw traceback artifact plus the stored inputs.
"""

from __future__ import annotations

import hashlib
import json


def frames_hash(frames: list[str]) -> str:
    return hashlib.sha1(json.dumps(frames).encode()).hexdigest()[:8]


def make_signature(
    exc_type: str | None, message: str | None, frames: list[str]
) -> tuple[str, dict]:
    inputs = {
        "exception": exc_type,
        "message_template": message,
        "frames": frames,
        "frames_hash": frames_hash(frames),
    }
    digest = hashlib.sha1(json.dumps(inputs, sort_keys=True).encode()).hexdigest()[:8]
    return digest, inputs


def recompute_signature(
    exc_type: str | None, message: str | None, frames: list[str]
) -> tuple[str, dict]:
    """Independent recomputation entry point (used by tests/verify logic)."""
    return make_signature(exc_type, message, frames)
