# Low-level IPC

`customrp_core.ipc` is a minimal client for the Discord desktop client's local RPC interface. Most
programs should use [`PresenceSession`](sessions.md), which is built on it.

## Where Discord listens

Discord opens an endpoint named `discord-ipc-N`, where N is 0 to 9. N is usually 0; it goes higher
when several Discord clients (for example stable and Canary) run at once.

| Platform | Endpoint |
|---|---|
| Windows | Named pipe `\\.\pipe\discord-ipc-N` |
| Linux, macOS | Unix socket `<dir>/discord-ipc-N` |

On Unix, `<dir>` is tried in this order: `$XDG_RUNTIME_DIR`, `$TMPDIR`, `$TMP`, `$TEMP`, then `/tmp`.
Each of those is also searched for these subdirectories, which sandboxed clients use:

| Subdirectory | Client |
|---|---|
| `app/com.discordapp.Discord` | Flatpak Discord |
| `app/com.discordapp.DiscordCanary`, `app/com.discordapp.DiscordPTB` | Flatpak Canary and PTB |
| `snap.discord`, `snap.discord-canary` | Snap Discord |
| `.flatpak/dev.vencord.Vesktop/xdg-run`, `app/dev.vencord.Vesktop` | Vesktop |

These subdirectories come from other Rich Presence projects and haven't been tested with real clients
here. `ipc_paths(pipe)` lists every candidate; `open_transport(pipe)` connects to the first one that
answers. `pipe=-1` tries all ten numbers.

A sandboxed **client** (Flatpak Discord) is handled by the list above. A sandboxed **program using this
library** needs access to the directory Discord's socket is in, for example
`--filesystem=xdg-run/discord-ipc-0` for Flatpak.

## DiscordIPC

```python
from customrp_core import DiscordIPC

client = DiscordIPC(
    "896771305108553788",
    pipe=-1,
    on_ready=lambda user: print("ready", user["username"]),
    on_presence_update=lambda activity: print("accepted"),
    on_error=lambda code, message: print("error", code, message),
    on_connection_failed=lambda message: print("failed", message),
)
client.set_activity({"details": "Hello"})   # Queued until Discord is ready
client.start()
...
client.close()
```

- All I/O happens on one worker thread, and the callbacks are called from it. This matters on Windows:
  a blocking read on a synchronous pipe handle would also block writes to it from another thread.
- `set_activity()` can be called before the handshake finishes; the command is sent once Discord sends
  `READY`.
- After `close()` returns, no more callbacks fire.
- A `DiscordIPC` connects once. To reconnect, make a new one (`PresenceSession` does this).

`transport_factory(pipe)` returns a transport, an object with `send(bytes)`, `poll(timeout) -> bool`,
`recv(n) -> bytes` and `close()`. `connect_path(path)` opens a specific socket or pipe, and
`SocketTransport` wraps any connected socket, which is handy in tests.

## The protocol

This is the subset used here. Discord publishes no formal specification for local RPC; this matches
what Discord's clients accept and what other RPC libraries do.

Each message is a frame:

```
int32 little-endian   opcode
int32 little-endian   payload length in bytes
UTF-8 JSON            payload
```

| Opcode | Name | Direction | Payload |
|---|---|---|---|
| 0 | HANDSHAKE | → Discord | `{"v": 1, "client_id": "<application id>"}` |
| 1 | FRAME | both | Commands and their replies |
| 2 | CLOSE | ← Discord | `{"code": 4000, "message": "Invalid Client ID"}` etc.; the connection ends |
| 3 | PING | ← Discord | Answered with PONG and the same payload |
| 4 | PONG | → Discord | |

After the handshake Discord sends `{"cmd": "DISPATCH", "evt": "READY", "data": {"user": {...}, ...}}`.
A presence is set with:

```json
{"cmd": "SET_ACTIVITY", "args": {"pid": 12345, "activity": {...}}, "nonce": "<uuid>"}
```

Discord replies with a frame carrying the same `cmd` and `nonce`. On success, `data` holds the activity
as Discord stored it. On failure, `evt` is `"ERROR"` and `data` has `code` and `message`. Discord clears
the presence when the connection closes.

## Helpers

- `display_name(user)`: `name`, or `name#1234` for accounts that still have a discriminator.
