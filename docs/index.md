# customrp-core documentation

customrp-core is a Python library for custom Discord Rich Presence, following the rules of
[CustomRP](https://www.customrp.xyz). It's independent of CustomRP and maintained separately.

1. [Getting started](getting-started.md)
2. [Presence model](presence.md)
3. [Sessions](sessions.md)
4. [Low-level IPC](ipc.md)
5. [Presets](presets.md)
6. [Assets](assets.md)
7. [Testing with FakeDiscord](testing.md)
8. [Compatibility with CustomRP](compatibility.md)
9. [Development](development.md)

## Modules at a glance

| Import | What's there |
|---|---|
| `customrp_core` | The main API: `Presence`, `Button`, the enums, `validate`, `check`, `build_activity`, `PresenceSession`, `DiscordIPC`, preset functions, exceptions |
| `customrp_core.presence` | Also `MAX_LENGTH`, `normalize`, `process_url`, `proxify` |
| `customrp_core.assets` | `fetch_assets`, `assets_page_url` |
| `customrp_core.ipc` | Transports, `ipc_paths`, `connect_path`, protocol constants |
| `customrp_core.testing` | `FakeDiscord`, `ipc_address`, `wait_until` |
