"""A stand-in for the Discord client, for testing code that uses this library.

:class:`FakeDiscord` listens where Discord would (a Unix socket, or a named pipe on Windows) and
speaks just enough of the IPC protocol to accept presences::

    with FakeDiscord(address) as discord:
        session = PresenceSession(presence, transport_factory=discord.transport_factory)
        session.start()
        activity = discord.wait_for_activity()

It's not a faithful copy of Discord: it accepts any application ID, and replies to
``SET_ACTIVITY`` by echoing the activity back.
"""

from __future__ import annotations

import json
import os
import socket
import struct
import sys
import tempfile
import threading
import time

from .ipc import OP_CLOSE, OP_FRAME, OP_HANDSHAKE, OP_PING, OP_PONG, connect_path

_HEADER = struct.Struct("<ii")
_POLL = 0.1

DEFAULT_USER = {"id": "123456789012345678", "username": "tester", "discriminator": "0", "avatar": None}


def ipc_address(pipe: int = 0, directory: str | None = None) -> str:
    """Where Discord's endpoint number ``pipe`` lives: a named pipe on Windows, or a socket
    in ``directory`` elsewhere. Point ``XDG_RUNTIME_DIR`` at that directory so it's found."""
    if sys.platform == "win32":
        return rf"\\.\pipe\discord-ipc-{pipe}"
    return os.path.join(directory or tempfile.gettempdir(), f"discord-ipc-{pipe}")


class FakeDiscord:
    """A fake Discord IPC server. ``error`` of ``(code, message)`` makes it reject every presence."""

    def __init__(self, address: str, *, user: dict | None = None, error: tuple[int, str] | None = None):
        self.address = address
        self.user = dict(user or DEFAULT_USER)
        self.error = error
        #: Client IDs from each handshake, in order
        self.handshakes: list[str] = []
        #: Every activity received, in order (None for a cleared presence)
        self.activities: list[dict | None] = []

        self._lock = threading.Condition()
        self._stopping = threading.Event()
        self._listener = None
        self._threads: list[threading.Thread] = []
        self._connections: list = []

    # --- Lifecycle -------------------------------------------------------------------

    def start(self) -> FakeDiscord:
        if sys.platform == "win32":
            from multiprocessing.connection import Listener
            self._listener = Listener(self.address, family="AF_PIPE")
        else:
            if os.path.exists(self.address):
                os.unlink(self.address)
            self._listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._listener.bind(self.address)
            self._listener.listen()
            self._listener.settimeout(_POLL)
        self._spawn(self._accept_loop)
        return self

    def stop(self):
        self._stopping.set()
        if sys.platform == "win32":
            # Listener.accept() can't time out; a throwaway connection wakes it up
            try:
                connect_path(self.address).close()
            except OSError:
                pass
        self.disconnect_clients()
        for thread in self._threads:
            thread.join(timeout=2)
        try:
            self._listener.close()
        except OSError:
            pass
        if sys.platform != "win32" and os.path.exists(self.address):
            os.unlink(self.address)

    def __enter__(self) -> FakeDiscord:
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    def disconnect_clients(self):
        """Drops every open connection, like Discord quitting would."""
        with self._lock:
            connections, self._connections = self._connections, []
        for conn in connections:
            conn.close()

    # --- Helpers for tests --------------------------------------------------------------

    def transport_factory(self, pipe: int = -1):
        """Use as ``transport_factory`` to connect to this server whatever pipe is configured."""
        return connect_path(self.address)

    def wait_for_activity(self, count: int = 1, timeout: float = 5.0) -> dict | None:
        """Waits until ``count`` activities have arrived in total, and returns the last one."""
        with self._lock:
            if not self._lock.wait_for(lambda: len(self.activities) >= count, timeout):
                raise TimeoutError(f"Got {len(self.activities)} activities, expected {count}")
            return self.activities[count - 1]

    def wait_for_handshakes(self, count: int = 1, timeout: float = 5.0) -> list[str]:
        with self._lock:
            if not self._lock.wait_for(lambda: len(self.handshakes) >= count, timeout):
                raise TimeoutError(f"Got {len(self.handshakes)} handshakes, expected {count}")
            return list(self.handshakes)

    # --- Server -------------------------------------------------------------------------

    def _spawn(self, target, *args):
        thread = threading.Thread(target=target, args=args, daemon=True, name="fake-discord")
        self._threads.append(thread)
        thread.start()

    def _accept_loop(self):
        while not self._stopping.is_set():
            try:
                if sys.platform == "win32":
                    conn = _PipeConnection(self._listener.accept())
                else:
                    conn = _SocketConnection(self._listener.accept()[0])
            except socket.timeout:
                continue
            except OSError:
                return
            if self._stopping.is_set():
                conn.close()
                return
            with self._lock:
                self._connections.append(conn)
            self._spawn(self._serve, conn)

    def _serve(self, conn):
        buffer = b""
        try:
            while not self._stopping.is_set():
                chunk = conn.recv(_POLL)
                if chunk is None:
                    continue
                if not chunk:
                    return
                buffer += chunk
                while len(buffer) >= _HEADER.size:
                    op, length = _HEADER.unpack_from(buffer)
                    if len(buffer) < _HEADER.size + length:
                        break
                    payload = json.loads(buffer[_HEADER.size:_HEADER.size + length] or b"{}")
                    buffer = buffer[_HEADER.size + length:]
                    if not self._handle(conn, op, payload):
                        return
        except (OSError, EOFError, ValueError):
            return
        finally:
            conn.close()

    def _handle(self, conn, op, payload) -> bool:
        if op == OP_HANDSHAKE:
            with self._lock:
                self.handshakes.append(payload.get("client_id"))
                self._lock.notify_all()
            conn.send(OP_FRAME, {"cmd": "DISPATCH", "evt": "READY", "nonce": None,
                                 "data": {"v": 1, "user": self.user, "config": {}}})
        elif op == OP_PING:
            conn.send(OP_PONG, payload)
        elif op == OP_CLOSE:
            return False
        elif op == OP_FRAME and payload.get("cmd") == "SET_ACTIVITY":
            nonce = payload.get("nonce")
            if self.error:
                code, message = self.error
                conn.send(OP_FRAME, {"cmd": "SET_ACTIVITY", "evt": "ERROR", "nonce": nonce,
                                     "data": {"code": code, "message": message}})
                return True
            activity = (payload.get("args") or {}).get("activity")
            with self._lock:
                self.activities.append(activity)
                self._lock.notify_all()
            conn.send(OP_FRAME, {"cmd": "SET_ACTIVITY", "evt": None, "nonce": nonce, "data": activity})
        return True


def _frame(op: int, payload) -> bytes:
    data = json.dumps(payload).encode("utf-8")
    return _HEADER.pack(op, len(data)) + data


class _SocketConnection:
    def __init__(self, sock):
        self.sock = sock
        sock.settimeout(_POLL)

    def recv(self, timeout):
        try:
            return self.sock.recv(65536)
        except socket.timeout:
            return None

    def send(self, op, payload):
        self.sock.sendall(_frame(op, payload))

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()


class _PipeConnection:
    """A multiprocessing pipe connection; each client write arrives as one message."""

    def __init__(self, conn):
        self.conn = conn
        self._closed = False

    def recv(self, timeout):
        if self._closed:
            return b""
        if not self.conn.poll(timeout):
            return None
        return self.conn.recv_bytes()

    def send(self, op, payload):
        self.conn.send_bytes(_frame(op, payload))

    def close(self):
        self._closed = True
        try:
            self.conn.close()
        except OSError:
            pass


def wait_until(predicate, timeout: float = 5.0, interval: float = 0.02) -> bool:
    """Polls ``predicate`` until it's true or ``timeout`` passes; returns its last result."""
    deadline = time.monotonic() + timeout
    while True:
        result = predicate()
        if result or time.monotonic() >= deadline:
            return result
        time.sleep(interval)
