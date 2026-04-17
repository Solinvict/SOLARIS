# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations


class EmbeddingProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[] for _ in texts]
