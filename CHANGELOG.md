# Changelog

## Unreleased

- Releases are automatic: pushing a new version to `main` publishes it, tags it and creates a GitHub release

## 0.1.2

- Published on PyPI: `pip install customrp-core`
- README links are absolute, so they work on PyPI too
- No code changes

## 0.1.1

- On macOS, also look for Discord's socket in the per-user temporary folder reported by the system,
  for programs started by launchd without `TMPDIR` set
- `PresenceSession` logs "Presence updated" at INFO level each time Discord accepts a presence

## 0.1.0

First release.

- `Presence` model covering everything CustomRP 1.19.4.1 can set, with validation and payload building
- `PresenceSession`: connects, retries, reconnects, refreshes local time, and resends on updates
- `DiscordIPC`: a dependency-free client for Discord's local IPC (Unix sockets and Windows named pipes)
- `.crp` preset reading and writing, compatible with the Windows app
- Application asset lookup
- `customrp_core.testing.FakeDiscord` for tests
