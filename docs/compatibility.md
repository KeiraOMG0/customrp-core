# Compatibility with CustomRP

customrp-core follows CustomRP 1.19.4.1. The rules were taken from its source code (mainly
`MainForm.cs`), not guessed. This page lists what matches, what deliberately differs, and what hasn't
been verified.

## Matches CustomRP

- Field set, maximum lengths, and which fields Discord counts in UTF-8 bytes
- Default application ID `896771305108553788`
- URL handling: trimming, adding `https://`, punycode hosts, truncating to the field limit
- Image URL length check against Discord's `mp:external` form
- Discord CDN images routed through `customrp.xyz/proxy`
- Protecting a leading no-break space with a zero-width space
- Raising `party_max` to `party_size`
- Party ID `"CustomRP"`, sent only when both party numbers are above 0
- Buttons sent only when they have both a label and a URL
- The five timestamp modes, including a custom start in the future becoming a countdown, and the local
  time refresh 5 seconds after midnight
- Retrying every 10 seconds, giving up after 30 attempts, and also retrying after errors from Discord
- `.crp` preset format, read and written

## Deliberate differences

| CustomRP | customrp-core | Why |
|---|---|---|
| The UI disables the party for types other than Playing and the timestamps for Competing, but still sends values set earlier | Leaves them out of the payload | Matches what the UI shows the user |
| Single-character fields are highlighted in red, but still sent | Treated as errors | Discord rejects them anyway; the error message is clearer |
| Text boxes stop typing at the length limit | Too-long values are errors | A config file has no text box to stop you |
| A custom timestamp with no date set uses the date picker's default (now) | `custom_start` is required in custom mode | There's no date picker |
| `Uri` parsing from .NET | Python's `urllib.parse` plus checks | No .NET. Edge cases in unusual URLs may differ. |
| Uses Lachee's DiscordRPC library | Speaks the IPC protocol directly | No dependencies; the protocol is small |

## Not part of this library

These belong to an application, not to the library:

- settings storage, the tray, run on startup, themes, translations
- update checks for CustomRP
- the dialog for choosing a pipe (pass `pipe=` instead)

## Not verified

- Flatpak, Snap and Vesktop socket locations (see [ipc.md](ipc.md))
- Talking to a real Discord client on Linux and macOS. The protocol is the same as on Windows, where it
  has been tested, and CI covers the socket code with a fake server.
- How Discord displays some combinations, such as `name` on applications that aren't verified. The
  library sends what CustomRP sends; what Discord does with it is up to Discord.
