"""Exceptions raised by customrp-core."""

from __future__ import annotations


class CustomRPError(Exception):
    """Base class for every error this library raises on purpose."""


class PresenceError(CustomRPError, ValueError):
    """A presence can't be sent as it is.

    ``field`` names the :class:`~customrp_core.presence.Presence` attribute at fault
    (for example ``"large_image"`` or ``"button1.url"``), or is ``None`` when the problem
    isn't tied to one field.
    """

    def __init__(self, message: str, field: str | None = None):
        super().__init__(f"{field}: {message}" if field else message)
        self.message = message
        self.field = field


class PresetError(CustomRPError):
    """A ``.crp`` preset file can't be read or written."""


class AssetsError(CustomRPError):
    """The list of an application's art assets couldn't be fetched."""
