"""Looking up the art assets uploaded to a Discord application.

CustomRP fills its image dropdowns from the same public endpoint; it needs no token.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from . import __version__
from .errors import AssetsError

ASSETS_URL = "https://discord.com/api/oauth2/applications/{}/assets"
ASSETS_PAGE_URL = "https://discord.com/developers/applications/{}/rich-presence/assets"


@dataclass(frozen=True)
class Asset:
    id: str
    name: str
    #: Discord's asset type number, passed through as is (CustomRP doesn't use it)
    type: int


def _check_id(application_id: str):
    if not (application_id.isdigit() and application_id.isascii()):
        raise AssetsError(f"{application_id!r} isn't a valid application ID")


def assets_page_url(application_id: str) -> str:
    """The Developer Portal page where the application's assets are managed."""
    _check_id(application_id)
    return ASSETS_PAGE_URL.format(application_id)


def fetch_assets(application_id: str, *, timeout: float = 10.0) -> list[Asset]:
    """Fetches the list of assets uploaded to an application. Raises :class:`AssetsError` on failure."""
    _check_id(application_id)
    request = urllib.request.Request(ASSETS_URL.format(application_id),
                                     headers={"User-Agent": f"customrp-core/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise AssetsError(f"There's no application with the ID {application_id}") from e
        raise AssetsError(f"Discord answered with HTTP {e.code} {e.reason}") from e
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise AssetsError(f"Couldn't reach Discord: {reason}") from e
    except ValueError as e:
        raise AssetsError("Discord sent something that isn't JSON") from e

    return parse_assets(data)


def parse_assets(data) -> list[Asset]:
    if not isinstance(data, list):
        raise AssetsError("Unexpected answer from Discord")
    return [Asset(str(item.get("id", "")), str(item.get("name", "")), int(item.get("type", 0) or 0))
            for item in data if isinstance(item, dict)]
