from datetime import datetime, timedelta, timezone

import pytest

from customrp_core import (ActivityType, Button, Presence, PresenceError, StatusDisplay, TimestampMode,
                           build_activity, normalize, validate)
from customrp_core.presence import DEFAULT_APPLICATION_ID, process_url, protect_leading_space, proxify

NOW = datetime(2026, 1, 2, 15, 30, 0).astimezone()
CONNECTED = NOW - timedelta(hours=1)
STARTED = NOW - timedelta(hours=2)


def ms(moment):
    return int(moment.timestamp() * 1000)


def build(presence, **kwargs):
    return build_activity(presence, connected_at=CONNECTED, started_at=STARTED, now=NOW, **kwargs)


def errors(presence):
    return {issue.field for issue in validate(presence) if issue.is_error}


def warnings(presence):
    return {issue.field for issue in validate(presence) if not issue.is_error}


# --- Payload --------------------------------------------------------------------

def test_minimal_presence():
    activity, refresh = build(Presence())
    assert activity == {"type": 0, "status_display_type": 0, "instance": False,
                        "timestamps": {"start": ms(CONNECTED)}}
    assert refresh is None


def test_full_presence():
    p = Presence(type=ActivityType.PLAYING, status_display=StatusDisplay.DETAILS, name="Game",
                 details="Coding", details_url="example.com/d", state="Rust", party_size=2, party_max=4,
                 large_image="logo", large_text="Logo", large_url="https://example.com/l",
                 small_image="https://example.com/s.png", small_text="Small",
                 button1=Button("Site", "example.com"), button2=Button("Repo", "https://github.com/x"))
    activity, _ = build(p)
    assert activity["name"] == "Game"
    assert activity["status_display_type"] == 2
    assert activity["details_url"] == "https://example.com/d"
    assert activity["party"] == {"id": "CustomRP", "size": [2, 4]}
    assert activity["assets"] == {"large_image": "logo", "large_text": "Logo", "large_url": "https://example.com/l",
                                  "small_image": "https://example.com/s.png", "small_text": "Small"}
    assert activity["buttons"] == [{"label": "Site", "url": "https://example.com"},
                                   {"label": "Repo", "url": "https://github.com/x"}]


def test_build_does_not_change_the_input():
    p = Presence(party_size=5, party_max=2, details="\u00a0x", button1=Button("ab", "example.com"))
    build(p)
    assert (p.party_max, p.details, p.button1.url) == (2, "\u00a0x", "example.com")


def test_party_only_for_playing_and_max_raised():
    activity, _ = build(Presence(party_size=5, party_max=2))
    assert activity["party"]["size"] == [5, 5]
    activity, _ = build(Presence(type=ActivityType.LISTENING, party_size=1, party_max=2))
    assert "party" not in activity


def test_incomplete_buttons_are_skipped():
    activity, _ = build(Presence(button1=Button("Only label", ""), button2=Button("", "example.com")))
    assert "buttons" not in activity


@pytest.mark.parametrize("mode, expected", [
    (TimestampMode.SINCE_LAST_CONNECTION, CONNECTED),
    (TimestampMode.SINCE_STARTUP, STARTED),
    (TimestampMode.SINCE_PRESENCE_UPDATE, NOW),
])
def test_timestamp_modes(mode, expected):
    activity, _ = build(Presence(timestamps=mode))
    assert activity["timestamps"] == {"start": ms(expected)}


def test_competing_has_no_timestamps():
    activity, _ = build(Presence(type=ActivityType.COMPETING, timestamps=TimestampMode.SINCE_STARTUP))
    assert "timestamps" not in activity


def test_local_time_refreshes_after_midnight():
    activity, refresh = build(Presence(timestamps=TimestampMode.LOCAL_TIME))
    assert activity["timestamps"]["start"] == ms(NOW.replace(hour=0, minute=0, second=0))
    assert refresh == pytest.approx(8.5 * 3600 + 5)


def test_custom_past_start():
    start = datetime(2026, 1, 1, 12, 0)
    activity, _ = build(Presence(timestamps=TimestampMode.CUSTOM, custom_start=start))
    assert activity["timestamps"] == {"start": ms(start.astimezone())}


def test_custom_future_start_counts_down():
    start = datetime(2026, 1, 3, 0, 0, tzinfo=timezone.utc)
    activity, _ = build(Presence(timestamps=TimestampMode.CUSTOM, custom_start=start))
    assert activity["timestamps"] == {"start": ms(NOW), "end": ms(start)}


def test_custom_start_and_end():
    start, end = datetime(2026, 1, 1), datetime(2026, 1, 5)
    activity, _ = build(Presence(timestamps=TimestampMode.CUSTOM, custom_start=start, custom_end=end))
    assert activity["timestamps"] == {"start": ms(start.astimezone()), "end": ms(end.astimezone())}


# --- Normalization ----------------------------------------------------------------

def test_leading_nbsp_gets_zwsp():
    assert protect_leading_space("\u00a0x", 128) == "\u200b\u00a0x"
    assert protect_leading_space("\u00a0\u00a0x", 3) == "\u200b\u00a0x"
    assert protect_leading_space(" x", 128) == " x"
    assert normalize(Presence(state="\u00a0hi")).state == "\u200b\u00a0hi"


def test_url_processing():
    assert process_url("b\u00fccher.de/a b", 256) == "https://xn--bcher-kva.de/a%20b"
    assert process_url("HTTP://example.com/x", 256) == "http://example.com/x"
    assert process_url("https://x.com/" + "a" * 300, 256) == ("https://x.com/" + "a" * 300)[:256]
    assert process_url("", 256) == ""


def test_discord_cdn_images_are_proxied():
    key = "https://cdn.discordapp.com/attachments/1/2/a.png"
    activity, _ = build(Presence(large_image=key))
    assert activity["assets"]["large_image"] == "https://customrp.xyz/proxy/attachments/1/2/a.png"
    activity, _ = build(Presence(large_image=key), proxy_discord_cdn=False)
    assert activity["assets"]["large_image"] == key
    assert proxify("https://media.discordapp.net/x.png") == "https://customrp.xyz/proxy/x.png"


def test_default_application_id():
    assert Presence().effective_application_id == DEFAULT_APPLICATION_ID
    assert Presence(application_id="42").effective_application_id == "42"


# --- Validation ----------------------------------------------------------------------

def test_valid_presence_has_no_issues():
    assert validate(Presence(details="Hello", button1=Button("Hi", "example.com"))) == []


def test_single_characters_are_rejected():
    assert errors(Presence(details="a", button2=Button("b", "example.com"))) == {"details", "button2.label"}


def test_byte_limits():
    assert errors(Presence(button1=Button("\u00e9" * 16, "example.com"))) == {"button1.label"}  # 32 bytes
    assert errors(Presence(button1=Button("\u00e9" * 15, "example.com"))) == set()
    assert errors(Presence(details="x" * 129)) == {"details"}


def test_character_limits():
    assert errors(Presence(name="x" * 257, details_url="example.com/" + "a" * 250)) == {"name", "details_url"}


def test_bad_application_id():
    assert errors(Presence(application_id="12ab")) == {"application_id"}
    assert errors(Presence(application_id="1" * 20)) == {"application_id"}


def test_bad_urls():
    assert errors(Presence(state_url="not a url", button1=Button("ab", "https://"))) == {"state_url", "button1.url"}


def test_long_image_url():
    p = Presence(small_image="https://example.com/" + "a" * 220)
    assert errors(p) == {"small_image"}
    with pytest.raises(PresenceError) as e:
        build(p)
    assert e.value.field == "small_image"


def test_custom_timestamps_need_a_start():
    assert errors(Presence(timestamps=TimestampMode.CUSTOM)) == {"custom_start"}
    end_before_start = Presence(timestamps=TimestampMode.CUSTOM, custom_start=datetime(2026, 2, 1),
                                custom_end=datetime(2026, 1, 1))
    assert warnings(end_before_start) == {"custom_end"}


def test_warnings():
    p = Presence(type=ActivityType.WATCHING, party_size=3, party_max=1, large_text="no image",
                 button1=Button("label only", ""))
    assert warnings(p) == {"party_size", "party_max", "large_image", "button1"}
    assert errors(p) == set()
    build(p)  # Warnings don't stop it from being sent
