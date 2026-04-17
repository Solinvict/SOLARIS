# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations


ACTION_TO_STATES = {
    "promote": ("remembered", "active"),
    "reinforce": ("remembered", "active"),
    "leave_candidate": ("candidate", "suppressed"),
    "fade": ("remembered", "dormant"),
    "pin": ("remembered", "active"),
    "retire": ("retired", "suppressed"),
    "mark_disputed": ("disputed", "suppressed"),
    "mark_superseded": ("superseded", "suppressed"),
}


def states_for_action(action: str, *, current_remember_state: str | None = None) -> tuple[str, str]:
    if action in ACTION_TO_STATES:
        return ACTION_TO_STATES[action]
    return current_remember_state or "candidate", "suppressed"
