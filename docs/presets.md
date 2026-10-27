# Presets

CustomRP saves presets as `.crp` files. customrp-core reads and writes the same format, so presets
move freely between the Windows app, this library and customrp-cli.

```python
from customrp_core import dump_preset, load_preset, parse_preset, save_preset

presence = load_preset("preset.crp")       # From a file
presence = parse_preset(data)              # From bytes or str
save_preset(presence, "preset.crp")
data = dump_preset(presence)               # bytes
```

Errors raise `PresetError`, with a message that can be shown to users as is.

## Format

A `.crp` file is what .NET's `XmlSerializer` produces for CustomRP's `Preset` struct:

```xml
<?xml version="1.0"?>
<Preset xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <ID>1234567890</ID>
  <Type>0</Type>
  <Display>0</Display>
  <Name />
  <Details>Coding</Details>
  ...
</Preset>
```

| Element | `Presence` field | Notes |
|---|---|---|
| `ID` | `application_id` | |
| `Type` | `type` | Discord's activity type number |
| `Display` | `status_display` | Discord's status display number |
| `Name`, `Details`, `DetailsURL`, `State`, `StateURL` | `name`, `details`, `details_url`, `state`, `state_url` | |
| `PartySize`, `PartyMax` | `party_size`, `party_max` | |
| `Timestamps` | `timestamps` | 0 since last connection, 1 since startup, 2 local time, 3 custom, 4 since presence update |
| `CustomTimestamp` | `custom_start` | `xs:dateTime`; `0001-01-01T00:00:00` means unset |
| `CustomTimestampEndEnabled`, `CustomTimestampEnd` | `custom_end` | The end is used only when enabled is `true` |
| `LargeKey`, `LargeText`, `LargeURL` | `large_image`, `large_text`, `large_url` | |
| `SmallKey`, `SmallText`, `SmallURL` | `small_image`, `small_text`, `small_url` | |
| `Button1Text`, `Button1URL`, `Button2Text`, `Button2URL` | `button1`, `button2` | |

Reading:

- A missing element means empty or 0, as in the Windows app.
- Dates with an offset or `Z` become aware datetimes; dates without one are local time. .NET writes up
  to seven fractional digits, which are cut to microseconds.
- A `Type`, `Display` or `Timestamps` value the library doesn't know is an error rather than being
  guessed at.
- Files with a `<!DOCTYPE>` are refused. The Windows app never writes one, and refusing them rules out
  XML entity tricks in presets downloaded from elsewhere.

Writing:

- Elements are written in the Windows app's order, with the same namespace declarations.
- Dates are written in local time with their offset. With no `custom_end`, `CustomTimestampEnd` repeats
  the start and `CustomTimestampEndEnabled` is `false`, because the Windows app always stores a date there.
