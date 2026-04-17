# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from enum import Enum


class ArtifactType(str, Enum):
    event = "event"
    entity = "entity"
    relation = "relation"
    claim = "claim"
    episode = "episode"
    state_lease = "state_lease"


class RememberState(str, Enum):
    candidate = "candidate"
    remembered = "remembered"
    disputed = "disputed"
    superseded = "superseded"
    retired = "retired"


class ActivationState(str, Enum):
    active = "active"
    dormant = "dormant"
    suppressed = "suppressed"


class ReviewStatus(str, Enum):
    pending = "pending"
    reviewed = "reviewed"


class SessionKind(str, Enum):
    runtime = "runtime"
    interaction = "interaction"
    manual = "manual"
    import_session = "import"


class ScopeMode(str, Enum):
    local = "local"
    broader = "broader"


class RecallMode(str, Enum):
    default = "default"
    deep = "deep"
    archive = "archive"


class EditorialAction(str, Enum):
    promote = "promote"
    reinforce = "reinforce"
    leave_candidate = "leave_candidate"
    fade = "fade"
    pin = "pin"
    retire = "retire"
    mark_disputed = "mark_disputed"
    mark_superseded = "mark_superseded"
