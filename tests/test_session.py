import logging

import pytest

from customrp_core import Presence, PresenceSession, SessionState, session as session_module
from customrp_core.presence import Activity
from customrp_core.testing import FakeDiscord, wait_until


@pytest.fixture
def make_session():
    sessions = []

    def make(presence=None, **kwargs):
        kwargs.setdefault("retry_interval", 0.05)
        s = PresenceSession(presence or Presence(details="Testing"), **kwargs)
        sessions.append(s)
        return s

    yield make
    for s in sessions:
        s.stop()
        assert s.wait(5)


def test_sends_presence_and_stops(discord, make_session):
    states = []
    session = make_session(transport_factory=discord.transport_factory,
                           on_state_change=lambda state, message: states.append(state))
    session.start()

    assert discord.wait_for_activity()["details"] == "Testing"
    assert wait_until(lambda: session.state == SessionState.CONNECTED)
    assert session.user["username"] == "tester"

    session.stop()
    assert session.wait(5)
    assert session.gave_up is False
    assert states == [SessionState.CONNECTING, SessionState.CONNECTED, SessionState.STOPPED]


def test_run_returns_true_when_stopped(discord, make_session):
    session = make_session(transport_factory=discord.transport_factory)
    session.start()
    discord.wait_for_activity()
    session.stop()
    assert session.wait(5)


def test_update_resends(discord, make_session):
    session = make_session(transport_factory=discord.transport_factory)
    session.start()
    discord.wait_for_activity()

    session.update(Presence(details="Changed"))
    assert discord.wait_for_activity(2)["details"] == "Changed"
    assert len(discord.handshakes) == 1


def test_application_id_change_reconnects(discord, make_session):
    session = make_session(transport_factory=discord.transport_factory)
    session.start()
    discord.wait_for_activity()

    session.update(Presence(application_id="42", details="Other app"))
    assert discord.wait_for_activity(2)["details"] == "Other app"
    assert discord.handshakes[-1] == "42"


def test_retries_until_discord_appears(discord, make_session):
    attempts = []

    def flaky(pipe):
        attempts.append(pipe)
        if len(attempts) < 3:
            raise ConnectionError("Discord isn't running")
        return discord.transport_factory(pipe)

    session = make_session(transport_factory=flaky, pipe=4)
    session.start()
    discord.wait_for_activity()
    assert attempts == [4, 4, 4]


def test_gives_up_after_max_retries(make_session):
    attempts = []

    def failing(pipe):
        attempts.append(pipe)
        raise ConnectionError("Discord isn't running")

    session = make_session(transport_factory=failing, max_retries=2)
    assert session.run() is False
    assert session.gave_up is True
    assert len(attempts) == 3  # The first try and two retries
    assert session.state == SessionState.STOPPED


def test_reconnects_when_discord_restarts(discord, make_session):
    session = make_session(transport_factory=discord.transport_factory)
    session.start()
    discord.wait_for_activity()

    discord.disconnect_clients()
    discord.wait_for_handshakes(2)
    discord.wait_for_activity(2)


def test_discord_error_is_retried(fake_address, make_session):
    with FakeDiscord(fake_address, error=(4002, "Bad activity")) as discord:
        states = []
        session = make_session(transport_factory=discord.transport_factory,
                               on_state_change=lambda state, message: states.append((state, message)))
        session.start()
        assert wait_until(lambda: (SessionState.WAITING, "Discord returned an error (4002): Bad activity") in states)

        discord.error = None
        discord.wait_for_activity()


def test_invalid_presence_is_not_sent(discord, make_session, caplog):
    caplog.set_level(logging.ERROR, logger="customrp_core.session")
    session = make_session(Presence(details="x"), transport_factory=discord.transport_factory)
    session.start()

    discord.wait_for_handshakes()
    assert wait_until(lambda: "Presence not sent" in caplog.text)
    assert discord.activities == []

    session.update(Presence(details="Fixed"))
    assert discord.wait_for_activity()["details"] == "Fixed"


def test_refreshes_when_asked(discord, make_session, monkeypatch):
    real_build = session_module.build_activity

    def build_with_quick_refresh(*args, **kwargs):
        return Activity(real_build(*args, **kwargs).payload, 0.05)

    monkeypatch.setattr(session_module, "build_activity", build_with_quick_refresh)
    session = make_session(transport_factory=discord.transport_factory)
    session.start()
    discord.wait_for_activity(3)
    assert len(discord.handshakes) == 1
