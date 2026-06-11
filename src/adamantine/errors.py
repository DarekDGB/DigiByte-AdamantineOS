from __future__ import annotations


class AdamantineError(Exception):
    """Base error for AdamantineOS."""


class TVAError(AdamantineError):
    """Raised when Truth Vector Authority denies continuation."""
