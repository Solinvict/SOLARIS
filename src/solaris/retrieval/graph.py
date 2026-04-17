# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations


def entity_neighborhood(relations_repo, connection, *, scope_key: str, entity_id: str) -> list[dict]:
    return relations_repo.neighborhood(connection, scope_key=scope_key, entity_id=entity_id)
