# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(slots=True)
class Clock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def iso(self) -> str:
        return self.now().isoformat()


@dataclass(slots=True)
class FixedClock(Clock):
    fixed: datetime

    def now(self) -> datetime:
        return self.fixed.astimezone(timezone.utc)

