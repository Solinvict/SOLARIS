# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import secrets
import time


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_crockford(value: int, length: int) -> str:
    chars: list[str] = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def new_ulid(prefix: str = "") -> str:
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    randomness = secrets.randbits(80)
    raw = (_encode_crockford(timestamp_ms, 10) + _encode_crockford(randomness, 16)).lower()
    clean_prefix = str(prefix or "").strip().strip("_")
    return f"{clean_prefix}_{raw}" if clean_prefix else raw

