"""The presence model, its validation, and how it becomes a Discord activity payload.

The rules here follow CustomRP 1.19.4.1 (``MainForm.cs``, ``SetPresence``) unless a comment
says otherwise.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import IntEnum
from typing import NamedTuple
from urllib.parse import quote, urlsplit, urlunsplit

from .errors import PresenceError

#: CustomRP's own Discord application, used when no application ID is given.
DEFAULT_APPLICATION_ID = "896771305108553788"


class ActivityType(IntEnum):
    """The verb in front of the application name. Values are Discord's."""

    PLAYING = 0
    LISTENING = 2
    WATCHING = 3
    COMPETING = 5


class StatusDisplay(IntEnum):
    """Which field Discord shows next to your name in the member list. Values are Discord's."""

    NAME = 0
    STATE = 1
    DETAILS = 2


class TimestampMode(IntEnum):
    """Where the elapsed/remaining time comes from. Values match CustomRP's settings and presets."""

    SINCE_LAST_CONNECTION = 0
    SINCE_STARTUP = 1
    LOCAL_TIME = 2
    CUSTOM = 3
    SINCE_PRESENCE_UPDATE = 4


@dataclass
class Button:
    label: str = ""
    url: str = ""


@dataclass
class Presence:
    """Everything CustomRP lets you set, under Pythonic names.

    Empty strings mean "not set". ``custom_start`` and ``custom_end`` are only used with
    :attr:`TimestampMode.CUSTOM`; naive datetimes are taken as local time.
    """

    application_id: str = ""
    type: ActivityType = ActivityType.PLAYING
    status_display: StatusDisplay = StatusDisplay.NAME
    name: str = ""
    details: str = ""
    details_url: str = ""
    state: str = ""
    state_url: str = ""
    party_size: int = 0
    party_max: int = 0
    timestamps: TimestampMode = TimestampMode.SINCE_LAST_CONNECTION
    custom_start: datetime | None = None
    custom_end: datetime | None = None
    large_image: str = ""
    large_text: str = ""
    large_url: str = ""
    small_image: str = ""
    small_text: str = ""
    small_url: str = ""
    button1: Button = field(default_factory=Button)
    button2: Button = field(default_factory=Button)

    @property
    def effective_application_id(self) -> str:
        return self.application_id or DEFAULT_APPLICATION_ID

    @property
    def buttons(self) -> tuple[Button, Button]:
        return self.button1, self.button2

    def copy(self) -> Presence:
        return dataclasses.replace(self, button1=dataclasses.replace(self.button1),
                                   button2=dataclasses.replace(self.button2))


# --- Limits --------------------------------------------------------------------

#: Maximum lengths, the same as the text boxes in CustomRP. Keys are field names;
#: ``button.label`` and ``button.url`` apply to both buttons.
MAX_LENGTH = {
    "application_id": 19,
    "name": 256,
    "details": 128,
    "details_url": 256,
    "state": 128,
    "state_url": 256,
    "large_image": 256,
    "large_text": 128,
    "large_url": 256,
    "small_image": 256,
    "small_text": 128,
    "small_url": 256,
    "button.label": 31,
    "button.url": 512,
}

#: Fields Discord measures in UTF-8 bytes rather than characters.
BYTE_LIMITED = {"details", "state", "large_text", "small_text", "button.label"}

#: Text fields Discord rejects when they're exactly one character long.
MIN_TWO_CHARS = {"name", "details", "state", "large_text", "small_text", "button.label"}

URL_FIELDS = ("details_url", "state_url", "large_url", "small_url")

NBSP = "\u00a0"
ZWSP = "\u200b"


def _limit_key(name: str) -> str:
    return re.sub(r"^button\d", "button", name)


def _get(presence: Presence, name: str):
    """Reads a field by name; ``button1.url`` style names reach into the buttons."""
    if "." in name:
        button, attr = name.split(".")
        return getattr(getattr(presence, button), attr)
    return getattr(presence, name)


def _text_fields():
    yield from ("name", "details", "state", "large_text", "small_text")
    for n in (1, 2):
        yield f"button{n}.label"


# --- Validation ----------------------------------------------------------------

@dataclass(frozen=True)
class Issue:
    """A problem :func:`validate` found. Errors stop the presence from being sent; warnings don't."""

    field: str | None
    message: str
    is_error: bool = True

    def __str__(self):
        return f"{self.field}: {self.message}" if self.field else self.message


def validate(presence: Presence, *, now: datetime | None = None) -> list[Issue]:
    """Lists everything wrong with a presence without changing it."""
    issues = []

    def error(name, message):
        issues.append(Issue(name, message))

    def warn(name, message):
        issues.append(Issue(name, message, is_error=False))

    app_id = presence.application_id
    if app_id and not (app_id.isdigit() and app_id.isascii()):
        error("application_id", "must contain only digits")
    elif len(app_id) > MAX_LENGTH["application_id"]:
        error("application_id", f"must be at most {MAX_LENGTH['application_id']} digits")

    for name in _text_fields():
        value = _get(presence, name)
        limit = MAX_LENGTH[_limit_key(name)]
        if len(value) == 1:
            error(name, "must be at least 2 characters long (Discord rejects single characters)")
        if _limit_key(name) in BYTE_LIMITED:
            size = len(value.encode("utf-8"))
            if size > limit:
                error(name, f"is {size} bytes long in UTF-8; Discord allows {limit}")
        elif len(value) > limit:
            error(name, f"is {len(value)} characters long; the limit is {limit}")

    url_fields = list(URL_FIELDS) + ["button1.url", "button2.url"]
    for name in url_fields:
        value = _get(presence, name).strip()
        limit = MAX_LENGTH[_limit_key(name)]
        if not value:
            continue
        if len(value) > limit:
            error(name, f"is {len(value)} characters long; the limit is {limit}")
        elif not _looks_like_url(process_url(value, limit)):
            error(name, f"{value!r} isn't a valid URL")

    for prefix in ("large", "small"):
        name = prefix + "_image"
        key = _get(presence, name).strip()
        if len(key) > MAX_LENGTH[name]:
            error(name, f"is {len(key)} characters long; the limit is {MAX_LENGTH[name]}")
        elif "://" in key and _mp_external_over_limit(_encode_url(key)):
            error(name, "the image URL is too long for Discord (it must fit in 256 characters "
                        "after Discord rewrites it); try a shorter link")
        if not key and (_get(presence, prefix + "_text") or _get(presence, prefix + "_url")):
            warn(name, f"{prefix}_text and {prefix}_url are only shown together with an image")

    if presence.party_size < 0 or presence.party_max < 0:
        error("party_size", "party sizes can't be negative")
    elif presence.party_size > presence.party_max:
        warn("party_max", f"is smaller than party_size; it will be raised to {presence.party_size}")
    if presence.type != ActivityType.PLAYING and (presence.party_size or presence.party_max):
        warn("party_size", "a party is only shown with the Playing activity type")

    if presence.timestamps == TimestampMode.CUSTOM and presence.type != ActivityType.COMPETING:
        if presence.custom_start is None:
            error("custom_start", "is required when timestamps is set to custom")
        elif presence.custom_end is not None and presence.custom_end.astimezone() < presence.custom_start.astimezone():
            warn("custom_end", "is earlier than custom_start")

    for n, button in enumerate(presence.buttons, 1):
        if bool(button.label.strip()) != bool(button.url.strip()):
            missing = "url" if button.label.strip() else "label"
            warn(f"button{n}", f"has no {missing}, so it won't be shown")

    return issues


def check(presence: Presence) -> None:
    """Raises :class:`PresenceError` for the first error :func:`validate` finds."""
    for issue in validate(presence):
        if issue.is_error:
            raise PresenceError(issue.message, issue.field)


# --- Normalization -------------------------------------------------------------

def protect_leading_space(text: str, max_length: int) -> str:
    """Discord trims leading whitespace, but not when a zero-width space comes first.

    CustomRP only protects no-break spaces, so users can still opt in to a leading blank.
    """
    if text.startswith(NBSP) and len(text) < max_length:
        return ZWSP + text
    if text.startswith(NBSP + NBSP):
        return ZWSP + text[1:]
    return text


def _encode_url(url: str) -> str:
    """Converts the host to punycode and percent-encodes characters URLs can't contain."""
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return url
    if not host:
        return url

    try:
        ascii_host = host.encode("idna").decode("ascii")
    except UnicodeError:
        ascii_host = host

    netloc = ascii_host + (f":{port}" if port else "")
    if parts.username:
        userinfo = parts.username + (f":{parts.password}" if parts.password else "")
        netloc = f"{userinfo}@{netloc}"

    safe = "/%:@!$&'()*+,;=-._~"
    return urlunsplit((parts.scheme.lower(), netloc, quote(parts.path, safe=safe),
                       quote(parts.query, safe=safe + "?"), quote(parts.fragment, safe=safe + "?")))


def _looks_like_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
        return bool(parts.scheme and parts.hostname) and not re.search(r"\s", parts.netloc)
    except ValueError:
        return False


def process_url(url: str, max_length: int) -> str:
    """Adds ``https://`` when there's no scheme, encodes the URL, and cuts it to ``max_length``."""
    if not url:
        return url
    if "://" not in url:
        url = "https://" + url
    return _encode_url(url)[:max_length]


def _mp_external_over_limit(url: str) -> bool:
    """Discord stores external images as ``mp:external/<id>/<query>/<scheme>/<host><path>``,
    which must fit in 256 characters."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if host == "media.discordapp.net":
        host = "cdn.discordapp.com"
    query = "?" + parts.query if parts.query else ""
    return len(f"mp:external/{'x' * 43}/{quote(query, safe='')}/{parts.scheme}/{host}{parts.path}") > 256


def proxify(key: str) -> str:
    """Discord won't show images from its own CDN, so CustomRP sends them through its proxy at
    customrp.xyz, which is run by CustomRP's developer."""
    return re.sub(r"//(cdn|media)\.discordapp\.(com|net)/", "//customrp.xyz/proxy/", key)


def normalize(presence: Presence) -> Presence:
    """Returns a cleaned-up copy, the way CustomRP tidies its fields before sending them.

    Raises :class:`PresenceError` if the presence has errors (see :func:`validate`).
    """
    check(presence)
    p = presence.copy()

    p.details = protect_leading_space(p.details, MAX_LENGTH["details"])
    p.state = protect_leading_space(p.state, MAX_LENGTH["state"])

    if p.party_size > p.party_max:
        p.party_max = p.party_size

    p.large_image = p.large_image.strip()
    p.small_image = p.small_image.strip()
    for name in URL_FIELDS:
        setattr(p, name, process_url(getattr(p, name).strip(), MAX_LENGTH[name]))
    for button in p.buttons:
        button.url = process_url(button.url.strip(), MAX_LENGTH["button.url"])

    for name in ("large_image", "small_image"):
        key = getattr(p, name)
        if "://" in key:
            setattr(p, name, _encode_url(key))

    return p


# --- Payload -------------------------------------------------------------------

class Activity(NamedTuple):
    """What :func:`build_activity` returns."""

    payload: dict
    #: Seconds until the presence must be sent again (for :attr:`TimestampMode.LOCAL_TIME`), or None
    refresh_in: float | None


def _ms(moment: datetime) -> int:
    return int(moment.timestamp() * 1000)


def build_activity(presence: Presence, *, connected_at: datetime, started_at: datetime,
                   now: datetime | None = None, proxy_discord_cdn: bool = True) -> Activity:
    """Builds the ``activity`` object of a ``SET_ACTIVITY`` command.

    ``connected_at`` and ``started_at`` feed the "since last connection" and "since startup"
    timestamp modes. Raises :class:`PresenceError` if the presence has errors.
    """
    p = normalize(presence)
    now = now or datetime.now().astimezone()

    activity = {"type": int(p.type), "status_display_type": int(p.status_display), "instance": False}

    def put(target, key, value):
        if value:
            target[key] = value

    put(activity, "name", p.name)
    put(activity, "details", p.details)
    put(activity, "details_url", p.details_url)
    put(activity, "state", p.state)
    put(activity, "state_url", p.state_url)

    assets = {}
    for prefix in ("large", "small"):
        key = getattr(p, prefix + "_image")
        put(assets, prefix + "_image", proxify(key) if proxy_discord_cdn else key)
        put(assets, prefix + "_text", getattr(p, prefix + "_text"))
        put(assets, prefix + "_url", getattr(p, prefix + "_url"))
    put(activity, "assets", assets)

    # CustomRP's UI disables the party for types other than Playing, and the timestamps for
    # Competing; this leaves them out of the payload instead.
    if p.type == ActivityType.PLAYING and p.party_size > 0 and p.party_max > 0:
        activity["party"] = {"id": "CustomRP", "size": [p.party_size, p.party_max]}

    buttons = [{"label": b.label, "url": b.url} for b in p.buttons if b.label and b.url]
    put(activity, "buttons", buttons)

    refresh_in = None
    timestamps = {}
    mode = p.timestamps

    if p.type != ActivityType.COMPETING:
        if mode == TimestampMode.SINCE_LAST_CONNECTION:
            timestamps["start"] = _ms(connected_at)
        elif mode == TimestampMode.SINCE_STARTUP:
            timestamps["start"] = _ms(started_at)
        elif mode == TimestampMode.SINCE_PRESENCE_UPDATE:
            timestamps["start"] = _ms(now)
        elif mode == TimestampMode.LOCAL_TIME:
            # "Elapsed" time since midnight reads as the current time of day
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            timestamps["start"] = _ms(midnight)
            refresh_in = ((midnight + timedelta(days=1, seconds=5)) - now).total_seconds()
        elif mode == TimestampMode.CUSTOM:
            start = p.custom_start.astimezone()
            if p.custom_end is not None:
                timestamps = {"start": _ms(start), "end": _ms(p.custom_end.astimezone())}
            elif start < now:
                timestamps["start"] = _ms(start)
            else:  # A start in the future becomes a countdown
                timestamps = {"start": _ms(now), "end": _ms(start)}

    put(activity, "timestamps", timestamps)
    return Activity(activity, refresh_in)
