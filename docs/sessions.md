# Sessions

`PresenceSession` keeps a presence up in Discord. It does what CustomRP's main window does behind
the buttons: connect, send, retry, and resend when needed.

```python
PresenceSession(
    presence,
    pipe=-1,                    # Which discord-ipc-N endpoint to use; -1 tries 0 to 9
    retry_interval=10.0,        # Seconds between connection attempts
    max_retries=30,             # None retries forever
    proxy_discord_cdn=True,     # See presence.md
    on_state_change=None,       # Callable(state, message)
    transport_factory=open_transport,
)
```

The defaults match CustomRP: after a failure it tries again every 10 seconds, 30 times, and then gives up.

## Running

| Method | Does |
|---|---|
| `run()` | Runs on the current thread. Returns `True` after `stop()`, `False` when the retries run out. |
| `start()` | Runs `run()` on a new daemon thread and returns the thread |
| `wait(timeout=None)` | Waits for a session started with `start()` to end |
| `update(presence)` | Shows a different presence (thread-safe) |
| `stop()` | Disconnects and makes `run()` return (thread-safe) |

When the session stops, the connection to Discord closes and Discord removes the presence.

## What happens when

| Event | Reaction |
|---|---|
| Start | Connects, and sends the presence once Discord says it's ready |
| Discord accepts the presence | State becomes `CONNECTED`, and the retry count resets |
| No Discord found, or the connection drops | State becomes `WAITING`; reconnects after `retry_interval` |
| Discord returns an error | Same as a dropped connection. CustomRP also retries in this case. |
| `update()` with the same application ID | Sends the new presence on the open connection |
| `update()` with a different application ID | Reconnects, since the ID is fixed per connection |
| Presence has validation errors | Logs `Presence not sent: ...` and keeps the connection; fix it with `update()` |
| `LOCAL_TIME` timestamps | Resends 5 seconds after midnight so the day rolls over |
| Retries exhausted | `run()` returns `False` and `gave_up` is `True` |

## State and callbacks

`session.state` is a `SessionState`: `STOPPED`, `CONNECTING`, `CONNECTED` or `WAITING`.
`on_state_change(state, message)` is called from the session's thread on every change, and on every
retry while `WAITING`. `message` describes the failure for `WAITING`.

```python
def report(state, message):
    print(state.value, message or "")

PresenceSession(presence, on_state_change=report).run()
```

Other attributes: `user` is Discord's user object while connected, `presence` is a copy of the current
presence, and `started_at` and `connected_at` are what the "since startup" and "since last connection"
timestamps use.

## Threads

The session runs on one thread, and the connection uses another (see [ipc.md](ipc.md)). Callbacks and
logging come from these threads. `update()` and `stop()` only post a message to the session's queue,
so they're safe to call from anywhere, including signal handlers.

`run()` wakes up at least twice a second, so a `KeyboardInterrupt` on the main thread is noticed
quickly on every platform.
