# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import ScopeMode


class ScopeRef(BaseModel):
    tenant: str = Field(min_length=1)
    namespace: str = Field(min_length=1)
    workspace: str = "default"
    project: str = "default"

    def key(self) -> str:
        return "::".join(
            [
                self.tenant.strip().casefold(),
                self.namespace.strip().casefold(),
                self.workspace.strip().casefold(),
                self.project.strip().casefold(),
            ]
        )

    def as_db_tuple(self) -> tuple[str, str, str, str]:
        return (self.tenant, self.namespace, self.workspace, self.project)


__all__ = ["ScopeMode", "ScopeRef"]

