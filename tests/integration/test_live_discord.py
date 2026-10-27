"""Tests against a real Discord client. They're skipped unless asked for:

    pytest -m integration

Only the handshake test runs by default; set CUSTOMRP_LIVE_PRESENCE=1 to also set (and then clear)
a presence on your account for a few seconds.
"""

import os
import threading

import pytest

from customrp_core import DiscordIPC, Presence, PresenceSession, SessionState, display_name
from customrp_core.presence import DEFAULT_APPLICATION_ID
from customrp_core.testing import wait_until

pytestmark = pytest.mark.integration


def test_handshake():
    ready = threading.Event()
    failures = []
    client = DiscordIPC(DEFAULT_APPLICATION_ID, on_ready=lambda user: ready.set(),
                        on_connection_failed=failures.append, on_error=lambda code, msg: failures.append(msg))
    client.start()
    try:
        assert wait_until(lambda: ready.is_set() or failures, timeout=10)
        assert not failures, failures
        assert display_name(client.user)
    finally:
        client.close()


@pytest.mark.skipif(os.environ.get("CUSTOMRP_LIVE_PRESENCE") != "1", reason="set CUSTOMRP_LIVE_PRESENCE=1")
def test_presence_is_accepted():
    session = PresenceSession(Presence(details="customrp-core test", state="This goes away in a moment"),
                              max_retries=0)
    session.start()
    try:
        assert wait_until(lambda: session.state == SessionState.CONNECTED or session.gave_up, timeout=15)
        assert session.state == SessionState.CONNECTED
    finally:
        session.stop()
        session.wait(5)
