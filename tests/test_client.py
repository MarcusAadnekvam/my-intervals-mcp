import httpx
import pytest
import respx

from intervals_mcp.client import IntervalsClient, IntervalsError, _clean_params

BASE = "https://intervals.icu"


@pytest.fixture
def client():
    return IntervalsClient(api_key="secret", athlete_id="i1")


async def test_missing_api_key_is_reported_clearly(monkeypatch):
    monkeypatch.delenv("INTERVALS_API_KEY", raising=False)
    with pytest.raises(IntervalsError, match="INTERVALS_API_KEY is not set"):
        IntervalsClient()


@respx.mock
async def test_sends_basic_auth_with_the_api_key_username(client):
    route = respx.get(f"{BASE}/api/v1/athletes").mock(return_value=httpx.Response(200, json=[]))
    await client.get("/api/v1/athletes")
    auth = route.calls[0].request.headers["authorization"]
    assert auth.startswith("Basic ")
    import base64

    assert base64.b64decode(auth.split()[1]).decode() == "API_KEY:secret"


@respx.mock
async def test_resolves_and_caches_the_athlete_id():
    unconfigured = IntervalsClient(api_key="secret")
    route = respx.get(f"{BASE}/api/v1/athlete/0").mock(
        return_value=httpx.Response(200, json={"id": "i42"})
    )
    assert await unconfigured.athlete() == "i42"
    assert await unconfigured.athlete() == "i42"
    assert route.call_count == 1


async def test_explicit_athlete_id_wins(client):
    assert await client.athlete("i99") == "i99"


@respx.mock
@pytest.mark.parametrize(
    "status,expected",
    [
        (401, "INTERVALS_API_KEY"),
        (403, "Not authorised"),
        (404, "Not found"),
    ],
)
async def test_error_statuses_map_to_short_messages(client, status, expected):
    respx.get(f"{BASE}/api/v1/athlete/i1").mock(return_value=httpx.Response(status))
    with pytest.raises(IntervalsError, match=expected):
        await client.get("/api/v1/athlete/i1")


@respx.mock
async def test_html_error_pages_are_truncated_not_dumped(client):
    respx.get(f"{BASE}/api/v1/x").mock(
        return_value=httpx.Response(500, text="<html>" + "y" * 5000 + "</html>")
    )
    with pytest.raises(IntervalsError) as exc:
        await client.get("/api/v1/x")
    assert len(str(exc.value)) < 300


@respx.mock
async def test_rate_limit_is_retried_once(client, monkeypatch):
    monkeypatch.setattr("intervals_mcp.client.asyncio.sleep", _no_sleep)
    route = respx.get(f"{BASE}/api/v1/x").mock(
        side_effect=[httpx.Response(429), httpx.Response(200, json={"ok": True})]
    )
    assert await client.get("/api/v1/x") == {"ok": True}
    assert route.call_count == 2


@respx.mock
async def test_empty_body_returns_none(client):
    respx.delete(f"{BASE}/api/v1/x").mock(return_value=httpx.Response(204))
    assert await client.delete("/api/v1/x") is None


def test_clean_params_drops_none_joins_lists_and_lowercases_bools():
    assert _clean_params(
        {"a": None, "b": ["x", "y"], "c": True, "d": False, "e": [], "f": 3}
    ) == {"b": "x,y", "c": "true", "d": "false", "f": 3}


async def _no_sleep(_seconds):
    return None
