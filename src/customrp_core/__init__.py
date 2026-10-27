"""customrp-core: the platform-independent parts of CustomRP, as a library.

Build a :class:`Presence`, then either turn it into a payload with :func:`build_activity` and send it
with :class:`DiscordIPC`, or let :class:`PresenceSession` handle connecting, retrying and resending.
"""

__version__ = "0.1.1"

from .errors import AssetsError, CustomRPError, PresenceError, PresetError  # noqa: E402
from .ipc import DiscordIPC, display_name, ipc_paths, open_transport  # noqa: E402
from .presence import (  # noqa: E402
    DEFAULT_APPLICATION_ID,
    MAX_LENGTH,
    Activity,
    ActivityType,
    Button,
    Issue,
    Presence,
    StatusDisplay,
    TimestampMode,
    build_activity,
    check,
    normalize,
    validate,
)
from .preset import dump_preset, load_preset, parse_preset, save_preset  # noqa: E402
from .session import PresenceSession, SessionState  # noqa: E402

__all__ = [
    "Activity", "ActivityType", "AssetsError", "Button", "CustomRPError", "DEFAULT_APPLICATION_ID",
    "DiscordIPC", "Issue", "MAX_LENGTH", "Presence", "PresenceError", "PresenceSession", "PresetError",
    "SessionState", "StatusDisplay", "TimestampMode", "build_activity", "check", "display_name",
    "dump_preset", "ipc_paths", "load_preset", "normalize", "open_transport", "parse_preset",
    "save_preset", "validate",
]
