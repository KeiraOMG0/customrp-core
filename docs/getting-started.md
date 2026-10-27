# Getting started

## Requirements

- Python 3.9 or newer
- A Discord desktop client running on the same machine and under the same user. Rich Presence doesn't
  work through the browser version of Discord.

## Installing

```sh
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install "customrp-core @ git+https://github.com/KeiraOMG0/customrp-core.git@v0.1.0"
```

Pin a tag (`@v0.1.0`) rather than `@main` so updates don't surprise you. The package imports as
`customrp_core`.

## A first presence

```python
from customrp_core import Presence, PresenceSession

session = PresenceSession(Presence(details="Hello from Python"))
session.run()   # Blocks until session.stop() is called from another thread, or the retries run out
```

`run()` connects to Discord, sends the presence, and keeps the connection open, because Discord clears
a presence as soon as the program that set it disconnects. Press Ctrl+C to end it.

To keep your own thread free, use `start()`. It runs the session on a daemon thread:

```python
session = PresenceSession(presence)
session.start()
...
session.update(new_presence)     # Show something else
...
session.stop()
session.wait()
```

## Using your own Discord application

Without an application ID, the presence appears under CustomRP's default application. To show your
own name and images:

1. Create an application at <https://discord.com/developers/applications>. Its name is what appears after
   "Playing".
2. Optionally upload images under **Rich Presence → Art Assets**.
3. Copy the **Application ID** into `Presence(application_id="...")`.

CustomRP's documentation has a [step-by-step guide](https://docs.customrp.xyz/setting-up) for this; it
applies here too.

## Checking a presence before sending it

```python
from customrp_core import Button, Presence, check, validate

presence = Presence(details="x", button1=Button("Docs", ""))
for issue in validate(presence):
    print("error" if issue.is_error else "warning", issue)
# error details: must be at least 2 characters long (Discord rejects single characters)
# warning button1: has no url, so it won't be shown

check(presence)   # Raises PresenceError for the first error
```

Sending a presence with errors fails with `PresenceError`. A `PresenceSession` logs the error and
keeps the connection.

## Seeing the payload

```python
from datetime import datetime
from customrp_core import Presence, build_activity

now = datetime.now().astimezone()
activity, refresh_in = build_activity(Presence(details="Hi"), connected_at=now, started_at=now)
print(activity)
# {'type': 0, 'status_display_type': 0, 'instance': False, 'details': 'Hi', 'timestamps': {'start': ...}}
```

## Presets from the Windows app

```python
from customrp_core import load_preset, save_preset

presence = load_preset("my preset.crp")
save_preset(presence, "copy.crp")
```

## Logging

The library logs through the standard `logging` module under the `customrp_core` logger, and never
configures logging itself. `INFO` reports connections and retries; `DEBUG` also shows every frame
exchanged with Discord.

```python
import logging
logging.basicConfig(level=logging.INFO)
```

## Next steps

- [Presence model](presence.md): every field and rule
- [Sessions](sessions.md): retries, callbacks, threading
- [Testing with FakeDiscord](testing.md)
