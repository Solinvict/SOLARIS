# SPDX-License-Identifier: MPL-2.0

class SolarisError(Exception):
    """Base Solaris exception."""


class NotFoundError(SolarisError):
    """Requested resource not found."""

