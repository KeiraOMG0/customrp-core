# customrp-core

A small Python library for setting a custom Discord Rich Presence, and the engine behind
[customrp-cli](https://github.com/KeiraOMG0/customrp-cli). It follows the rules of
[CustomRP](https://www.customrp.xyz), the Windows app by maximmax42, but has no GUI and no Windows-only parts.

> **Independent project.** customrp-core is not part of CustomRP and is not maintained by its developer.
> Report problems here, not on the CustomRP repository.

## What it does

- **Talks to the Discord desktop client** over its local IPC socket (Linux, macOS) or named pipe (Windows).
  No extra libraries are needed.
- **Models everything CustomRP can set:** activity type, name, details and state (with links), party size,
  five timestamp modes, large and small images (asset keys or URLs) with tooltips and links, two buttons,
  and which field shows in the member list.
- **Validates a presence the way Discord will.** It checks length limits (in characters or UTF-8 bytes),
  single-character fields, bad URLs, and image URLs Discord would truncate, so you get a readable error
  instead of a rejection.
- **Cleans up the input the same way CustomRP does:** it adds `https://`, converts hosts to punycode,
  percent-encodes characters URLs can't contain, keeps a leading no-break space, and routes images from
  Discord's own CDN through CustomRP's proxy.
- **Keeps a presence up** with `PresenceSession`. It retries every 10 seconds when Discord isn't running,
  reconnects when Discord restarts, refreshes the local time display at midnight, and resends when the
  presence changes.
- **Reads and writes `.crp` presets** that open in the Windows app and the other way round.
- **Lists an application's art assets**, using the public endpoint CustomRP uses.
- **Ships a fake Discord server** (`customrp_core.testing`) for testing your own code without Discord.

It has no dependencies outside the Python standard library.

## Install

Python 3.9 or newer. Install from [PyPI](https://pypi.org/project/customrp-core/), ideally inside a
virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install customrp-core
```

Or straight from Git, at a release tag:

```sh
pip install "customrp-core @ git+https://github.com/KeiraOMG0/customrp-core.git@v0.1.2"
```

In a `requirements.txt`:

```
customrp-core>=0.1.2,<0.2
```

## Example

```python
import logging
from customrp_core import Button, Presence, PresenceSession, validate

logging.basicConfig(level=logging.INFO)

presence = Presence(
    application_id="",                # empty: CustomRP's default application
    details="Writing a library",
    state="in Python",
    large_image="https://example.com/logo.png",
    button1=Button("Source", "github.com/KeiraOMG0/customrp-core"),
)

for issue in validate(presence):
    print(issue)                      # e.g. "details: must be at least 2 characters long ..."

session = PresenceSession(presence)   # retries 30 times, every 10 s, like CustomRP
try:
    session.run()                     # blocks; Ctrl+C to stop
except KeyboardInterrupt:
    pass
```

More in [docs/getting-started.md](https://github.com/KeiraOMG0/customrp-core/blob/main/docs/getting-started.md).

## Documentation

| Page | Contents |
|---|---|
| [Getting started](https://github.com/KeiraOMG0/customrp-core/blob/main/docs/getting-started.md) | Installing, a first presence, common tasks |
| [Presence model](https://github.com/KeiraOMG0/customrp-core/blob/main/docs/presence.md) | Every field, its limits, validation, and how the payload is built |
| [Sessions](https://github.com/KeiraOMG0/customrp-core/blob/main/docs/sessions.md) | `PresenceSession`: connecting, retries, updates, threads |
| [Low-level IPC](https://github.com/KeiraOMG0/customrp-core/blob/main/docs/ipc.md) | `DiscordIPC`, where Discord's socket is looked for, the wire protocol |
| [Presets](https://github.com/KeiraOMG0/customrp-core/blob/main/docs/presets.md) | The `.crp` format and how it maps to `Presence` |
| [Assets](https://github.com/KeiraOMG0/customrp-core/blob/main/docs/assets.md) | Listing an application's uploaded images |
| [Testing with FakeDiscord](https://github.com/KeiraOMG0/customrp-core/blob/main/docs/testing.md) | Testing code that uses this library |
| [Compatibility with CustomRP](https://github.com/KeiraOMG0/customrp-core/blob/main/docs/compatibility.md) | What matches the Windows app, what differs, what isn't verified |
| [Development](https://github.com/KeiraOMG0/customrp-core/blob/main/docs/development.md) | Running the tests, project layout, releasing |

## Platform support

| Platform | Status |
|---|---|
| Windows 10/11 | Unit tests pass. A handshake with a real Discord client over its named pipe works. |
| Linux | Unit tests run in CI on Ubuntu, including a fake Discord over a real Unix socket. Not yet tried against a real Discord client. |
| macOS | Unit tests run in CI, as on Linux. Not yet tried against a real Discord client. |

The Discord client has to run on the same machine and user account, since Rich Presence only works
through its local IPC endpoint. Flatpak, Snap and Vesktop socket locations are searched too (see
[docs/ipc.md](https://github.com/KeiraOMG0/customrp-core/blob/main/docs/ipc.md)); those paths come from other Rich Presence projects, and none has been tested here.

## Credits

The presence rules, preset format and default application come from
[CustomRP](https://github.com/maximmax42/Discord-CustomRP) by maximmax42 (MIT license). Thanks to them for
the original app and for being open to an independent alternative.

## License

MIT. See [LICENSE](https://github.com/KeiraOMG0/customrp-core/blob/main/LICENSE).
