# SPDX-License-Identifier: MPL-2.0

"""Solaris standalone memory MCP server."""

from .host import CapabilitySet, PublishReceipt, SolarisHost, StoreIdentity

__all__ = [
    "CapabilitySet",
    "PublishReceipt",
    "SolarisHost",
    "StoreIdentity",
    "__version__",
]

__version__ = "0.2.0"

