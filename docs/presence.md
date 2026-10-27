# The presence model

`customrp_core.presence` holds the `Presence` dataclass, its validation, and `build_activity`, which turns
it into the `activity` object of Discord's `SET_ACTIVITY` command.

## Fields

An empty string always means "not set", and unset fields are left out of the payload.

| Field | Type | Limit | Meaning |
|---|---|---|---|
| `application_id` | `str` | 19 digits | Discord application to show the presence under. Empty uses CustomRP's default application (`DEFAULT_APPLICATION_ID`). |
| `type` | `ActivityType` | | `PLAYING`, `LISTENING`, `WATCHING` or `COMPETING`: the verb before the application name |
| `status_display` | `StatusDisplay` | | What the member list shows: `NAME` (the application name), `DETAILS` or `STATE` |
| `name` | `str` | 256 chars | Sent as the activity's `name` |
| `details` | `str` | 128 bytes | First line |
| `details_url` | `str` | 256 chars | Makes the first line a link |
| `state` | `str` | 128 bytes | Second line |
| `state_url` | `str` | 256 chars | Makes the second line a link |
| `party_size`, `party_max` | `int` | | "(2 of 4)" after the state. Only for `PLAYING`, and only when both are above 0 |
| `timestamps` | `TimestampMode` | | Where the elapsed or remaining time comes from (see below) |
| `custom_start`, `custom_end` | `datetime \| None` | | For `TimestampMode.CUSTOM`; naive datetimes are local time |
| `large_image`, `small_image` | `str` | 256 chars | An asset name from your application, or an image URL |
| `large_text`, `small_text` | `str` | 128 bytes | Tooltip on the image |
| `large_url`, `small_url` | `str` | 256 chars | Makes the image a link |
| `button1`, `button2` | `Button(label, url)` | label 31 bytes, url 512 chars | Up to two link buttons |

"Bytes" limits count the text's UTF-8 encoding, because that's how Discord counts these fields:
`é` takes 2 bytes and most emoji take 4.

The numeric values of `ActivityType` and `StatusDisplay` are Discord's own. `TimestampMode`'s values
are the ones CustomRP stores in its settings and presets.

## Timestamp modes

| Mode | Shows |
|---|---|
| `SINCE_LAST_CONNECTION` (default) | Time since the session last connected to Discord |
| `SINCE_STARTUP` | Time since the `PresenceSession` was created |
| `SINCE_PRESENCE_UPDATE` | Time since the presence was last sent |
| `LOCAL_TIME` | Time elapsed since midnight, which reads as the current time. `build_activity` returns a `refresh_in` so it can be resent just after midnight. |
| `CUSTOM` | With only `custom_start`: time elapsed since it, or a countdown to it if it's in the future. With both: Discord shows the span between them. |

`COMPETING` activities never get timestamps.

## Validation

`validate(presence)` returns a list of `Issue(field, message, is_error)` and doesn't change anything.
`check(presence)` raises `PresenceError` for the first error. `Issue.field` names the attribute, with
buttons written as `button1.label`, `button1.url` and so on.

**Errors** stop the presence from being sent:

- `application_id` contains anything but digits, or is longer than 19 digits
- a text field is exactly one character long (Discord requires at least two)
- a field is over its limit
- a URL field doesn't make a valid URL, even with `https://` added
- an image URL would be over 256 characters after Discord rewrites it to its `mp:external/...` form
- `timestamps` is `CUSTOM` but `custom_start` is missing

**Warnings** point out things that will be ignored or adjusted:

- `party_size` is bigger than `party_max` (`party_max` is raised to match)
- a party is set on an activity type other than `PLAYING`
- an image's text or link is set without the image
- a button has a label but no URL, or a URL but no label (it's skipped)
- `custom_end` is earlier than `custom_start`

## What `build_activity` changes

`build_activity` works on a cleaned-up copy made by `normalize()`; your `Presence` isn't modified.
It follows CustomRP:

- **URLs:** surrounding whitespace is trimmed, `https://` is added when there's no scheme, the host is
  converted to punycode (`bücher.de` → `xn--bcher-kva.de`), characters URLs can't contain are
  percent-encoded, and the result is cut to the field's limit.
- **Image URLs** are encoded the same way. Images on `cdn.discordapp.com` or `media.discordapp.net`
  are rewritten to `customrp.xyz/proxy/...`, because Discord won't show images from its own CDN.
  The proxy is run by CustomRP's developer. Pass `proxy_discord_cdn=False` to send these URLs unchanged.
- **Leading spaces:** Discord trims leading whitespace. A `details` or `state` that starts with a
  no-break space (U+00A0) gets a zero-width space (U+200B) in front so the indent survives.
- **Party:** `party_max` is raised to `party_size` if it's smaller.

```python
activity, refresh_in = build_activity(presence, connected_at=..., started_at=..., now=None,
                                      proxy_discord_cdn=True)
```

`now` defaults to the current time; pass it to get repeatable results in tests.

## Example payload

```python
Presence(details="Coding", state="Rust", party_size=2, party_max=4,
         large_image="logo", button1=Button("Site", "example.com"))
```

becomes

```json
{
  "type": 0,
  "status_display_type": 0,
  "instance": false,
  "details": "Coding",
  "state": "Rust",
  "assets": {"large_image": "logo"},
  "party": {"id": "CustomRP", "size": [2, 4]},
  "buttons": [{"label": "Site", "url": "https://example.com"}],
  "timestamps": {"start": 1767364200000}
}
```
