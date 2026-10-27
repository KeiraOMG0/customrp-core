"""Keeps a presence up: connects to Discord, sends the presence, retries and resends as needed.

This is the part of CustomRP's main window that isn't UI: the connect/retry timers, the local time
refresh, and resending when the presence changes.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Callable

from .errors import PresenceError
from .ipc import DiscordIPC, display_name, open_transport
from .presence import Presence, build_activity

log = logging.getLogger("customrp_core.session")

#: CustomRP waits this long between connection attempts...
DEFAULT_RETRY_INTERVAL = 10.0
#: ...and gives up after this many of them.
DEFAULT_MAX_RETRIES = 30

# How often the loop wakes up when nothing happens, so stop requests and Ctrl+C are noticed quickly
_TICK = 0.5


class SessionState(str, Enum):
    STOPPED = "stopped"
    CONNECTING = "connecting"
    CONNECTED = "connected"  # Discord accepted the presence
    WAITING = "waiting"  # Something failed; a retry is scheduled


class PresenceSession:
    """Shows a :class:`Presence` in Discord until stopped.

    Call :meth:`run` to do this on the current thread, or :meth:`start` to do it on a new one.
    :meth:`update` and :meth:`stop` can be called from any thread.

    ``max_retries`` of ``None`` retries forever. ``on_state_change(state, message)`` is called
    from the session's thread whenever :attr:`state` changes.
    """

    def __init__(self, presence: Presence, *, pipe: int = -1,
                 retry_interval: float = DEFAULT_RETRY_INTERVAL, max_retries: int | None = DEFAULT_MAX_RETRIES,
                 proxy_discord_cdn: bool = True,
                 on_state_change: Callable[[SessionState, str | None], None] | None = None,
                 transport_factory=open_transport):
        self.pipe = pipe
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self.proxy_discord_cdn = proxy_discord_cdn
        self.on_state_change = on_state_change or (lambda state, message: None)

        self.state = SessionState.STOPPED
        #: Discord's user object once connected, else None
        self.user: dict | None = None
        self.started_at = datetime.now().astimezone()
        self.connected_at = self.started_at

        self._presence = presence.copy()
        self._transport_factory = transport_factory
        self._events: queue.Queue = queue.Queue()
        self._client: DiscordIPC | None = None
        self._thread: threading.Thread | None = None
        self._finished = threading.Event()
        #: True if the last :meth:`run` ended because the retries ran out
        self.gave_up = False

        self._retries_left: int | None = None  # None when not retrying
        self._retry_at: float | None = None
        self._refresh_at: float | None = None

    @property
    def presence(self) -> Presence:
        return self._presence.copy()

    # --- Thread-safe controls ------------------------------------------------------

    def update(self, presence: Presence):
        """Shows a different presence. Changing the application ID reconnects."""
        self._events.put(("update", None, presence.copy()))

    def stop(self):
        """Asks the session to disconnect and return from :meth:`run`."""
        self._events.put(("stop", None))

    def start(self) -> threading.Thread:
        """Runs the session on a new daemon thread."""
        self._finished.clear()
        self._thread = threading.Thread(target=self.run, name="customrp-session", daemon=True)
        self._thread.start()
        return self._thread

    def wait(self, timeout: float | None = None) -> bool:
        """Waits for a session started with :meth:`start` to end; returns whether it has."""
        return self._finished.wait(timeout)

    # --- Loop ----------------------------------------------------------------------

    def run(self) -> bool:
        """Runs until :meth:`stop` is called (returns True) or the retries run out (returns False)."""
        self._finished.clear()
        self.gave_up = False
        try:
            self._connect()
            while True:
                event = self._next_event()
                if event is None:
                    if not self._timers_elapsed():
                        return False
                    continue

                kind, client, *args = event
                if kind == "stop":
                    log.info("Stopping")
                    return True
                if kind == "update":
                    self._apply_update(args[0])
                elif client is self._client:
                    self._handle_client_event(kind, *args)
        finally:
            self._disconnect()
            self._set_state(SessionState.STOPPED)
            self._finished.set()

    def _next_event(self):
        timeout = _TICK
        for deadline in (self._retry_at, self._refresh_at):
            if deadline is not None:
                timeout = min(timeout, max(0.0, deadline - time.monotonic()))
        try:
            return self._events.get(timeout=timeout)
        except queue.Empty:
            return None

    def _timers_elapsed(self) -> bool:
        """Fires due timers; returns False when it's time to give up."""
        now = time.monotonic()

        if self._retry_at is not None and now >= self._retry_at:
            self._retry_at = None
            if self._retries_left is None:
                self._retries_left = self.max_retries
            if self._retries_left is not None:
                if self._retries_left <= 0:
                    log.error("Couldn't connect to Discord; giving up after %d retries", self.max_retries)
                    self.gave_up = True
                    return False
                self._retries_left -= 1
            self._connect()

        if self._refresh_at is not None and now >= self._refresh_at:
            self._refresh_at = None
            self._send()

        return True

    def _apply_update(self, presence: Presence):
        old_id = self._presence.effective_application_id
        self._presence = presence
        if presence.effective_application_id != old_id:
            log.info("Application ID changed, reconnecting")
            self._retries_left = None
            self._connect(reset_connected_at=False)
        elif self.user is not None:
            self._send()

    def _handle_client_event(self, kind, *args):
        if kind == "ready":
            self.user = args[0]
            log.info("Connected to Discord as %s", display_name(self.user) or "unknown user")
            self._send()
        elif kind == "presence":
            log.info("Presence updated")
            self._retries_left = None
            self._set_state(SessionState.CONNECTED, "Presence updated")
        elif kind == "error":
            code, message = args
            self._schedule_retry(f"Discord returned an error ({code}): {message}")
        elif kind == "failed":
            self._schedule_retry(args[0])

    # --- Helpers -------------------------------------------------------------------

    def _connect(self, reset_connected_at=True):
        self._disconnect()
        app_id = self._presence.effective_application_id
        log.info("Connecting to Discord with application ID %s", app_id)

        client = DiscordIPC(app_id, self.pipe, transport_factory=self._transport_factory)
        events = self._events
        client.on_ready = lambda user: events.put(("ready", client, user))
        client.on_presence_update = lambda activity: events.put(("presence", client, activity))
        client.on_error = lambda code, message: events.put(("error", client, code, message))
        client.on_connection_failed = lambda message: events.put(("failed", client, message))

        self._client = client
        if reset_connected_at:
            self.connected_at = datetime.now().astimezone()
        self._set_state(SessionState.CONNECTING)
        client.start()

    def _disconnect(self):
        self._retry_at = self._refresh_at = None
        self.user = None
        if self._client is not None:
            self._client.close()
            self._client = None

    def _send(self):
        if self._client is None or self.user is None:
            return
        self._refresh_at = None
        try:
            activity, refresh_in = build_activity(self._presence, connected_at=self.connected_at,
                                                  started_at=self.started_at,
                                                  proxy_discord_cdn=self.proxy_discord_cdn)
        except PresenceError as e:
            log.error("Presence not sent: %s", e)
            return

        log.debug("Sending presence")
        self._client.set_activity(activity)
        if refresh_in is not None:
            self._refresh_at = time.monotonic() + refresh_in

    def _schedule_retry(self, reason: str):
        self._disconnect()
        left = ""
        if self.max_retries is not None:
            remaining = self.max_retries if self._retries_left is None else self._retries_left
            left = f" ({remaining} attempt(s) left)"
        log.warning("%s; retrying in %g s%s", reason, self.retry_interval, left)
        self._retry_at = time.monotonic() + self.retry_interval
        self._set_state(SessionState.WAITING, reason)

    def _set_state(self, state: SessionState, message: str | None = None):
        if state != self.state or state == SessionState.WAITING:
            self.state = state
            self.on_state_change(state, message)
