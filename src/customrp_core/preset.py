"""Reading and writing CustomRP's ``.crp`` preset files.

A preset is what .NET's ``XmlSerializer`` makes of CustomRP's ``Preset`` struct: a ``<Preset>``
element with one child per field. Presets written here open in the Windows app and vice versa.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Union

from .errors import PresetError
from .presence import ActivityType, Button, Presence, StatusDisplay, TimestampMode

PathLike = Union[str, Path]

# Element names in the order the Windows app writes them
ELEMENTS = [
    "ID", "Type", "Display", "Name", "Details", "DetailsURL", "State", "StateURL", "PartySize", "PartyMax",
    "Timestamps", "CustomTimestamp", "CustomTimestampEndEnabled", "CustomTimestampEnd",
    "LargeKey", "LargeText", "LargeURL", "SmallKey", "SmallText", "SmallURL",
    "Button1Text", "Button1URL", "Button2Text", "Button2URL",
]

# Element -> Presence attribute, for the plain string fields
_STRINGS = {
    "ID": "application_id", "Name": "name", "Details": "details", "DetailsURL": "details_url",
    "State": "state", "StateURL": "state_url", "LargeKey": "large_image", "LargeText": "large_text",
    "LargeURL": "large_url", "SmallKey": "small_image", "SmallText": "small_text", "SmallURL": "small_url",
}

# .NET's DateTime.MinValue, which is what an unset date looks like
_UNSET_DATE = "0001-01-01T00:00:00"


def parse_xml_datetime(text: str) -> datetime | None:
    """Parses an ``xs:dateTime`` as .NET writes it (up to 7 fractional digits).

    Returns None for ``DateTime.MinValue``, an aware datetime when the text has an offset,
    and a naive (local) one otherwise.
    """
    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})?", text.strip())
    if not m:
        raise PresetError(f"Not a valid date: {text!r}")

    base, fraction, zone = m.groups()
    if base.startswith("0001-01-01"):
        return None

    try:
        moment = datetime.fromisoformat(base)
    except ValueError as e:
        raise PresetError(f"Not a valid date: {text!r}") from e
    if fraction:
        moment = moment.replace(microsecond=int(fraction[:6].ljust(6, "0")))
    if zone:
        moment = datetime.fromisoformat(moment.isoformat() + ("+00:00" if zone == "Z" else zone))
    return moment


def format_xml_datetime(moment: datetime | None) -> str:
    if moment is None:
        return _UNSET_DATE
    return moment.astimezone().replace(microsecond=0).isoformat()


def _int(text: str, element: str) -> int:
    try:
        return int(text) if text else 0
    except ValueError:
        raise PresetError(f"{element}: {text!r} isn't a number") from None


def _enum(kind, text: str, element: str):
    value = _int(text, element)
    try:
        return kind(value)
    except ValueError:
        raise PresetError(f"{element}: {value} isn't a known value") from None


def parse_preset(data: bytes | str) -> Presence:
    """Reads a preset from the contents of a ``.crp`` file."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    # The Windows app never writes a DOCTYPE; refusing one rules out entity expansion tricks
    if b"<!doctype" in raw.lower():
        raise PresetError("Preset files can't contain a DOCTYPE")

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise PresetError(f"Not a valid preset file: {e}") from e
    if root.tag != "Preset":
        raise PresetError(f"Not a preset file (the root element is <{root.tag}>, not <Preset>)")

    def text(element):
        node = root.find(element)
        return (node.text or "") if node is not None else ""

    p = Presence()
    for element, attr in _STRINGS.items():
        setattr(p, attr, text(element))

    p.type = _enum(ActivityType, text("Type"), "Type")
    p.status_display = _enum(StatusDisplay, text("Display"), "Display")
    p.timestamps = _enum(TimestampMode, text("Timestamps"), "Timestamps")
    p.party_size = _int(text("PartySize"), "PartySize")
    p.party_max = _int(text("PartyMax"), "PartyMax")
    p.button1 = Button(text("Button1Text"), text("Button1URL"))
    p.button2 = Button(text("Button2Text"), text("Button2URL"))

    if text("CustomTimestamp"):
        p.custom_start = parse_xml_datetime(text("CustomTimestamp"))
    if text("CustomTimestampEndEnabled") == "true" and text("CustomTimestampEnd"):
        p.custom_end = parse_xml_datetime(text("CustomTimestampEnd"))

    return p


def dump_preset(presence: Presence) -> bytes:
    """Writes a presence in the ``.crp`` format."""
    p = presence
    values = {element: getattr(p, attr) for element, attr in _STRINGS.items()}
    values.update({
        "Type": str(int(p.type)),
        "Display": str(int(p.status_display)),
        "PartySize": str(p.party_size),
        "PartyMax": str(p.party_max),
        "Timestamps": str(int(p.timestamps)),
        "CustomTimestamp": format_xml_datetime(p.custom_start),
        "CustomTimestampEndEnabled": "true" if p.custom_end is not None else "false",
        # The Windows app always stores an end date; reuse the start when there's none
        "CustomTimestampEnd": format_xml_datetime(p.custom_end if p.custom_end is not None else p.custom_start),
        "Button1Text": p.button1.label,
        "Button1URL": p.button1.url,
        "Button2Text": p.button2.label,
        "Button2URL": p.button2.url,
    })

    root = ET.Element("Preset", {
        "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
    })
    for element in ELEMENTS:
        ET.SubElement(root, element).text = values[element]

    ET.indent(root, space="  ")
    return b'<?xml version="1.0"?>\n' + ET.tostring(root, encoding="unicode").encode("utf-8")


def load_preset(path: PathLike) -> Presence:
    """Reads a ``.crp`` file. Raises :class:`PresetError` if it can't be used."""
    try:
        data = Path(path).read_bytes()
    except OSError as e:
        raise PresetError(f"Can't read {path}: {e.strerror or e}") from e
    return parse_preset(data)


def save_preset(presence: Presence, path: PathLike) -> None:
    """Writes a ``.crp`` file."""
    try:
        Path(path).write_bytes(dump_preset(presence))
    except OSError as e:
        raise PresetError(f"Can't write {path}: {e.strerror or e}") from e
