# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations


def build_timeline(events: list[dict]) -> list[dict]:
    return sorted(events, key=lambda item: str(item.get("timestamp") or ""))
