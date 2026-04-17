# SPDX-License-Identifier: MPL-2.0

from __future__ import annotations

import asyncio


def test_mcp_smoke(mcp):
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}
    assert "solaris.open_session" in names
    assert "solaris.query" in names
    assert "solaris.recall" in names
    assert "solaris.explain_memory" in names
    assert "solaris.reconsider" in names
