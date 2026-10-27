# Assets

Images uploaded to a Discord application under **Rich Presence → Art Assets** can be used by name
in `large_image` and `small_image`. CustomRP lists them in its image dropdowns, and so can you:

```python
from customrp_core.assets import assets_page_url, fetch_assets

for asset in fetch_assets("896771305108553788"):
    print(asset.name)

print(assets_page_url("896771305108553788"))
# https://discord.com/developers/applications/896771305108553788/rich-presence/assets
```

`fetch_assets(application_id, timeout=10)` calls
`https://discord.com/api/oauth2/applications/<id>/assets`, the public endpoint CustomRP uses. It needs
no token. It returns a list of `Asset(id, name, type)`, where `type` is Discord's number, passed through
unchanged.

It raises `AssetsError` when:

- the ID isn't all digits (checked before any request is made)
- Discord answers 404, meaning there's no application with that ID
- Discord answers with another HTTP error, or the network is unreachable
- the answer isn't the expected JSON

Any asset can go in either image slot, and image URLs work too, so there's no need to use assets at all.
