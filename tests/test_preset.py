from datetime import datetime, timedelta, timezone

import pytest

from customrp_core import (ActivityType, Button, Presence, PresetError, StatusDisplay, TimestampMode, dump_preset,
                           load_preset, parse_preset, save_preset)
from customrp_core.preset import ELEMENTS, parse_xml_datetime

# Written by the Windows app's XmlSerializer (fields it leaves empty are missing or self-closing)
WINDOWS_PRESET = """\ufeff<?xml version="1.0"?>
<Preset xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <ID>1234567890</ID>
  <Type>2</Type>
  <Display>1</Display>
  <Name />
  <Details>Listening</Details>
  <State>to stuff</State>
  <PartySize>0</PartySize>
  <PartyMax>0</PartyMax>
  <Timestamps>3</Timestamps>
  <CustomTimestamp>2024-05-01T12:00:00.1234567+00:00</CustomTimestamp>
  <CustomTimestampEndEnabled>false</CustomTimestampEndEnabled>
  <CustomTimestampEnd>0001-01-01T00:00:00</CustomTimestampEnd>
  <LargeKey>logo</LargeKey>
  <Button1Text>Site</Button1Text>
  <Button1URL>https://example.com/</Button1URL>
</Preset>
"""


def test_load_windows_preset():
    p = parse_preset(WINDOWS_PRESET.encode("utf-8"))
    assert p.application_id == "1234567890"
    assert p.type == ActivityType.LISTENING
    assert p.status_display == StatusDisplay.STATE
    assert (p.name, p.details, p.state, p.large_image, p.small_image) == ("", "Listening", "to stuff", "logo", "")
    assert p.timestamps == TimestampMode.CUSTOM
    assert p.custom_start == datetime(2024, 5, 1, 12, 0, 0, 123456, tzinfo=timezone.utc)
    assert p.custom_end is None
    assert p.button1 == Button("Site", "https://example.com/")
    assert p.button2 == Button()


def test_roundtrip(tmp_path):
    original = Presence(application_id="42", type=ActivityType.LISTENING, status_display=StatusDisplay.DETAILS,
                        name="n", details="d\u00e9tails & <stuff>", details_url="https://a.b/", state="s",
                        party_size=1, party_max=3, timestamps=TimestampMode.CUSTOM,
                        custom_start=datetime(2025, 6, 7, 8, 9, 10).astimezone(),
                        custom_end=datetime(2025, 6, 8, 8, 9, 10).astimezone(),
                        large_image="l", large_text="lt", large_url="https://l/", small_image="s",
                        small_text="st", small_url="https://s/", button1=Button("b1", "https://1/"),
                        button2=Button("b2", "https://2/"))
    path = tmp_path / "p.crp"
    save_preset(original, path)
    assert load_preset(path) == original


def test_written_layout_matches_the_windows_app():
    data = dump_preset(Presence()).decode("utf-8")
    assert data.startswith('<?xml version="1.0"?>\n<Preset xmlns:xsi=')
    positions = [data.index(f"<{element}") for element in ELEMENTS]
    assert positions == sorted(positions)
    # An unset date is written the way .NET writes DateTime.MinValue
    assert "<CustomTimestamp>0001-01-01T00:00:00</CustomTimestamp>" in data
    assert "<CustomTimestampEndEnabled>false</CustomTimestampEndEnabled>" in data


def test_xml_datetimes():
    assert parse_xml_datetime("0001-01-01T00:00:00") is None
    assert parse_xml_datetime("2024-01-02T03:04:05") == datetime(2024, 1, 2, 3, 4, 5)
    assert parse_xml_datetime("2024-01-02T03:04:05Z") == datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    assert parse_xml_datetime("2024-01-02T03:04:05.5-02:00").utcoffset() == timedelta(hours=-2)
    with pytest.raises(PresetError):
        parse_xml_datetime("yesterday")


@pytest.mark.parametrize("data", [
    b"<NotAPreset/>",
    b"not xml at all",
    b"<Preset><Type>seven</Type></Preset>",
    b"<Preset><Type>4</Type></Preset>",  # Not an activity type
    b'<!DOCTYPE x [<!ENTITY a "aaaa">]><Preset><Details>&a;</Details></Preset>',
])
def test_bad_presets(data):
    with pytest.raises(PresetError):
        parse_preset(data)


def test_missing_file(tmp_path):
    with pytest.raises(PresetError, match="Can't read"):
        load_preset(tmp_path / "nope.crp")
