import json
import socket
import struct
import sys
import threading

import pytest

from customrp_core import ipc
from customrp_core.testing import FakeDiscord, ipc_address


def frame(op, payload):
    data = json.dumps(payload).encode()
    return struct.pack("<ii", op, len(data)) + data


def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        assert chunk, "client hung up"
        data += chunk
    return data


def read_frame(sock):
    op, length = struct.unpack("<ii", recv_exact(sock, 8))
    return op, json.loads(recv_exact(sock, length))


def run_client(fake_discord, activity=None):
    """Runs a DiscordIPC client against a scripted Discord, ``fake_discord(sock)``, over a socket pair."""
    client_sock, server_sock = socket.socketpair()
    events = []
    done = threading.Event()

    client = ipc.DiscordIPC(
        "123", transport_factory=lambda pipe: ipc.SocketTransport(client_sock),
        on_ready=lambda user: events.append(("ready", user["username"])),
        on_presence_update=lambda data: (events.append(("presence", data)), done.set()),
        on_error=lambda code, msg: (events.append(("error", code, msg)), done.set()),
        on_connection_failed=lambda msg: (events.append(("failed",)), done.set()),
    )
    if activity is not None:
        client.set_activity(activity)  # Queued until READY

    server = threading.Thread(target=fake_discord, args=(server_sock,))
    server.start()
    client.start()
    assert done.wait(5)
    client.close()
    server.join(5)
    server_sock.close()
    return events


def test_handshake_ping_and_activity():
    received = {}

    def fake_discord(sock):
        received["handshake"] = read_frame(sock)
        sock.sendall(frame(ipc.OP_PING, {"x": 1}))
        received["pong"] = read_frame(sock)
        sock.sendall(frame(1, {"cmd": "DISPATCH", "evt": "READY", "data": {"user": {"username": "tester"}}}))
        _, cmd = read_frame(sock)
        received["cmd"] = cmd
        sock.sendall(frame(1, {"cmd": "SET_ACTIVITY", "evt": None, "data": cmd["args"]["activity"],
                               "nonce": cmd["nonce"]}))

    events = run_client(fake_discord, activity={"details": "hi"})

    assert received["handshake"] == (ipc.OP_HANDSHAKE, {"v": 1, "client_id": "123"})
    assert received["pong"] == (ipc.OP_PONG, {"x": 1})
    assert received["cmd"]["cmd"] == "SET_ACTIVITY"
    assert events == [("ready", "tester"), ("presence", {"details": "hi"})]


def test_invalid_client_id():
    def fake_discord(sock):
        read_frame(sock)
        sock.sendall(frame(ipc.OP_CLOSE, {"code": 4000, "message": "Invalid Client ID"}))

    assert run_client(fake_discord) == [("error", 4000, "Invalid Client ID")]


def test_error_event():
    def fake_discord(sock):
        read_frame(sock)
        sock.sendall(frame(1, {"cmd": "DISPATCH", "evt": "READY", "data": {"user": {"username": "t"}}}))
        _, cmd = read_frame(sock)
        sock.sendall(frame(1, {"cmd": "SET_ACTIVITY", "evt": "ERROR", "nonce": cmd["nonce"],
                               "data": {"code": 4002, "message": "child \"activity\" fails"}}))

    events = run_client(fake_discord, activity={"details": "x"})
    assert events[-1] == ("error", 4002, "child \"activity\" fails")


def test_connection_dropped():
    def fake_discord(sock):
        read_frame(sock)
        sock.close()

    assert run_client(fake_discord) == [("failed",)]


def test_no_discord():
    def failing(pipe):
        raise ConnectionError("no discord")

    messages = []
    done = threading.Event()
    client = ipc.DiscordIPC("1", transport_factory=failing,
                            on_connection_failed=lambda m: (messages.append(m), done.set()))
    client.start()
    assert done.wait(5)
    assert messages == ["no discord"]


def test_real_endpoint(discord):
    """Talks to the fake server over a real Unix socket or named pipe."""
    got = threading.Event()
    client = ipc.DiscordIPC("777", transport_factory=discord.transport_factory,
                            on_presence_update=lambda activity: got.set())
    client.set_activity({"details": "over the wire"})
    client.start()
    try:
        assert discord.wait_for_activity() == {"details": "over the wire"}
        assert got.wait(5)
        assert discord.handshakes == ["777"]
    finally:
        client.close()


@pytest.mark.skipif(sys.platform == "win32", reason="Unix socket discovery")
def test_socket_discovery(ipc_dir, monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", ipc_dir)
    with FakeDiscord(ipc_address(3, ipc_dir)):
        transport = ipc.open_transport(-1)
        transport.close()
        transport = ipc.open_transport(3)
        transport.close()
        with pytest.raises(ConnectionError):
            ipc.open_transport(4)


def test_ipc_paths(monkeypatch):
    if sys.platform == "win32":
        assert list(ipc.ipc_paths(2)) == [r"\\.\pipe\discord-ipc-2"]
        assert len(list(ipc.ipc_paths(-1))) == 10
    else:
        monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
        paths = list(ipc.ipc_paths(0))
        assert paths[0] == "/run/user/1000/discord-ipc-0"
        assert "/run/user/1000/app/com.discordapp.Discord/discord-ipc-0" in paths
        assert "/tmp/discord-ipc-0" in paths


def test_display_name():
    assert ipc.display_name({"username": "a", "discriminator": "0"}) == "a"
    assert ipc.display_name({"username": "a", "discriminator": "1234"}) == "a#1234"
