# Testing with FakeDiscord

`customrp_core.testing.FakeDiscord` is a small server that pretends to be the Discord client. It
listens on a real Unix socket, or a named pipe on Windows, and handles the handshake, `PING` and
`SET_ACTIVITY`. With it you can test code built on this library without running Discord or touching
your account. It's part of the package, not of the test suite, so other projects can use it.

```python
from customrp_core import Presence, PresenceSession
from customrp_core.testing import FakeDiscord

def test_my_presence(tmp_path):
    with FakeDiscord(str(tmp_path / "discord")) as discord:
        session = PresenceSession(Presence(details="Hi"), transport_factory=discord.transport_factory)
        session.start()
        assert discord.wait_for_activity()["details"] == "Hi"
        session.stop()
        session.wait()
```

On Windows, pass a pipe name like `\\.\pipe\my-test-<random>` instead of a path. On macOS, keep socket
paths short: Unix socket paths are limited to about 100 characters, and macOS temporary directories are
long. A directory made with `tempfile.mkdtemp(dir="/tmp")` works.

## API

| Member | Purpose |
|---|---|
| `FakeDiscord(address, user=None, error=None)` | `user` is the user object sent with READY; `error=(code, message)` makes it reject every presence |
| `start()`, `stop()`, or use as a context manager | |
| `transport_factory` | Pass as `transport_factory=` to connect to this server whatever the configured pipe |
| `activities` | Every activity received, in order |
| `handshakes` | The client ID of every handshake, in order |
| `wait_for_activity(count=1, timeout=5)` | Waits until `count` activities have arrived, and returns the last one |
| `wait_for_handshakes(count=1, timeout=5)` | Same for handshakes |
| `disconnect_clients()` | Drops every connection, as if Discord quit |
| `error` | Can be changed while running |

`ipc_address(pipe, directory)` gives the address where real discovery would look:
`\\.\pipe\discord-ipc-N` on Windows, or `<directory>/discord-ipc-N` elsewhere. On Unix, point
`XDG_RUNTIME_DIR` at the directory to test discovery end to end, even from another process. On Windows
that address is the real Discord's pipe, so use a pipe number Discord isn't using.

`wait_until(predicate, timeout=5)` polls a condition, which is useful for state changes.

## Limits

FakeDiscord accepts any application ID and echoes activities back without checking them. It tests
your code's side of the conversation, not whether Discord would accept the presence. For that, see
the integration tests in [development.md](development.md).
