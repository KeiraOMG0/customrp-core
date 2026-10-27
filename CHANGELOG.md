# Changelog

## 0.1.0

First release.

- `Presence` model covering everything CustomRP 1.19.4.1 can set, with validation and payload building
- `PresenceSession`: connects, retries, reconnects, refreshes local time, and resends on updates
- `DiscordIPC`: a dependency-free client for Discord's local IPC (Unix sockets and Windows named pipes)
- `.crp` preset reading and writing, compatible with the Windows app
- Application asset lookup
- `customrp_core.testing.FakeDiscord` for tests
