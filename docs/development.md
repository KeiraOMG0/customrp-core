# Development

## Setup

```sh
git clone https://github.com/KeiraOMG0/customrp-core.git
cd customrp-core
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[test]"
```

## Tests

```sh
pytest                    # Unit tests: no Discord needed
pytest -m integration     # Against the Discord client running on this machine
```

The unit tests use `FakeDiscord` over a real socket or named pipe, and mock the network for asset
lookups. They take a few seconds.

The integration tests are skipped by default. `test_handshake` only connects; it doesn't change your
status. `test_presence_is_accepted` sets a presence for a moment, and only runs with
`CUSTOMRP_LIVE_PRESENCE=1`.

CI (`.github/workflows/tests.yml`) runs the unit tests on Ubuntu, Windows and macOS, with the oldest
and newest supported Python.

## Layout

```
src/customrp_core/
  presence.py   Presence model, validation, normalization, payload
  session.py    PresenceSession: the connect/retry/resend loop
  ipc.py        Discord IPC client and transports
  preset.py     .crp files
  assets.py     Application asset lookup
  testing.py    FakeDiscord
  errors.py     Exceptions
tests/
  integration/  Tests that need a real Discord client
docs/
```

## Guidelines

- No dependencies outside the standard library.
- Python 3.9 compatible (`from __future__ import annotations` for newer type hint syntax).
- Behaviour copied from CustomRP gets a comment or a line in [compatibility.md](compatibility.md), so
  the reason survives.
- Don't add fields or behaviour Discord doesn't document or CustomRP doesn't have.
- Error messages describe the problem in words a user understands; applications show them as they are.

## Releasing

1. Update `__version__` in `src/customrp_core/__init__.py` and `CHANGELOG.md`.
2. Commit, then tag: `git tag v0.2.0 && git push origin main v0.2.0`.
3. Update the pinned tag in customrp-cli's `requirements.txt` and `pyproject.toml`.

Versions follow semantic versioning. Until 1.0, minor versions may change the API.
