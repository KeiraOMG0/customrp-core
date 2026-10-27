import io
import json
import urllib.error

import pytest

from customrp_core import AssetsError, assets


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_fetch_assets(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse(json.dumps([{"id": "1", "name": "logo", "type": 1},
                                        {"id": "2", "name": "icon", "type": 2}]).encode())

    monkeypatch.setattr(assets.urllib.request, "urlopen", fake_urlopen)
    result = assets.fetch_assets("123")

    assert [a.name for a in result] == ["logo", "icon"]
    assert result[0] == assets.Asset("1", "logo", 1)
    assert requests[0].full_url == "https://discord.com/api/oauth2/applications/123/assets"
    assert requests[0].get_header("User-agent").startswith("customrp-core/")


def test_unknown_application(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, None)

    monkeypatch.setattr(assets.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(AssetsError, match="no application"):
        assets.fetch_assets("123")


def test_offline(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("Name or service not known")

    monkeypatch.setattr(assets.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(AssetsError, match="Couldn't reach Discord"):
        assets.fetch_assets("123")


@pytest.mark.parametrize("bad_id", ["", "12a", "1/../2", "\u0663"])
def test_rejects_bad_ids(bad_id):
    with pytest.raises(AssetsError):
        assets.fetch_assets(bad_id)
    with pytest.raises(AssetsError):
        assets.assets_page_url(bad_id)


def test_parse_assets():
    assert assets.parse_assets([{"name": "x"}, "junk"]) == [assets.Asset("", "x", 0)]
    with pytest.raises(AssetsError):
        assets.parse_assets({"message": "nope"})
