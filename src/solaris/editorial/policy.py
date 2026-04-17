# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import json
from pathlib import Path


class PolicyRegistry:
    def __init__(self, policies_dir: Path):
        self.policies_dir = Path(policies_dir)
        self._cache: dict[str, dict] = {}

    def get(self, name: str) -> dict:
        key = str(name or "").strip() or "default_v1"
        if key not in self._cache:
            path = self.policies_dir / f"{key}.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            self._cache[key] = payload
        return self._cache[key]
