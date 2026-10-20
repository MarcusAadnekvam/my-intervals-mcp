"""Exercise the tools end to end against a mocked Intervals.icu."""

import json

import httpx
import pytest
import respx

from intervals_mcp.client import IntervalsClient
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from intervals_mcp.tools import activities, athlete, calendar, wellness

BASE = "https://intervals.icu"


@pytest.fixture
def mcp():
    server = MCPServer("test")
    client = IntervalsClient(api_key="secret", athlete_id="i1")
    for module in (athlete, activities, wellness, calendar):
        module.register(server, client)
    return server


async def call(mcp, tool, args):
    """Invoke a tool and return its value the way an MCP client would see it."""
    result = await mcp.call_tool(tool, args)
    assert not result.is_error, result.content[0].text
    structured = result.structured_content
    if isinstance(structured, dict) and set(structured) == {"result"}:
        return structured["result"]
    if structured is not None:
        return structured
    return json.loads(result.content[0].text)


@respx.mock
async def test_list_activities_projects_fields_and_filters_by_sport(mcp):
    route = respx.get(f"{BASE}/api/v1/athlete/i1/activities").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "a1", "type": "Ride", "name": "Z2", "hrv": None, "icu_api_key": "leak"},
                {"id": "a2", "type": "Run", "name": "Easy"},
            ],
        )
    )
    rows = await call(mcp, "list_activities", {"oldest": "2025-08-01", "sport": "Ride"})
    assert rows == [{"id": "a1", "type": "Ride", "name": "Z2"}]
    # The field allowlist is pushed to the server, and nulls/unknown fields never return.
    assert "icu_training_load" in route.calls[0].request.url.params["fields"]


@respx.mock
async def test_get_activity_streams_summarises_and_downsamples(mcp):
    respx.get(f"{BASE}/api/v1/activity/a1/streams").mock(
        return_value=httpx.Response(
            200, json=[{"type": "watts", "data": list(range(3600))}]
        )
    )
    out = await call(
        mcp, "get_activity_streams", {"activity_id": "a1", "types": ["watts"], "max_points": 50}
    )
    assert out["watts"]["raw_length"] == 3600
    assert len(out["watts"]["points"]) == 50
    assert out["watts"]["summary"] == {"count": 3600, "min": 0, "mean": 1799.5, "max": 3599}


@respx.mock
async def test_get_activity_streams_rejects_oversized_requests(mcp):
    # IntervalsError subclasses ToolError, so the message survives to the model
    # rather than being masked as a generic "Error executing tool".
    with pytest.raises(ToolError, match="max_points cannot exceed 1000"):
        await mcp.call_tool(
            "get_activity_streams",
            {"activity_id": "a1", "types": ["watts"], "max_points": 5000},
        )


@respx.mock
async def test_get_fitness_trend_computes_form_and_summary(mcp):
    respx.get(f"{BASE}/api/v1/athlete/i1/wellness").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"id": "2025-08-02", "ctl": 62.0, "atl": 70.0},
                {"id": "2025-08-01", "ctl": 60.0, "atl": 55.0},
            ],
        )
    )
    out = await call(mcp, "get_fitness_trend", {"oldest": "2025-08-01", "newest": "2025-08-02"})
    assert [d["date"] for d in out["days"]] == ["2025-08-01", "2025-08-02"]
    assert out["days"][0]["form"] == 5.0
    assert out["days"][1]["form"] == -8.0
    assert out["summary"]["ctl_change"] == 2.0
    assert out["summary"]["form_end"] == -8.0


@respx.mock
async def test_update_wellness_sends_only_the_fields_given(mcp):
    route = respx.put(f"{BASE}/api/v1/athlete/i1/wellness/2025-08-14").mock(
        return_value=httpx.Response(200, json={"id": "2025-08-14"})
    )
    await call(
        mcp,
        "update_wellness",
        {"date": "2025-08-14", "weight": 72.5, "comments": "easy day"},
    )
    assert json.loads(route.calls[0].request.content) == {
        "weight": 72.5,
        "comments": "easy day",
    }


@respx.mock
async def test_wellness_carries_the_custom_alcohol_field(mcp):
    get_route = respx.get(f"{BASE}/api/v1/athlete/i1/wellness").mock(
        return_value=httpx.Response(200, json=[{"id": "2025-08-14", "Alcohol": 2}])
    )
    rows = await call(mcp, "list_wellness", {"oldest": "2025-08-14"})
    assert rows == [{"id": "2025-08-14", "Alcohol": 2}]
    assert "Alcohol" in get_route.calls[0].request.url.params["fields"]

    put_route = respx.put(f"{BASE}/api/v1/athlete/i1/wellness/2025-08-14").mock(
        return_value=httpx.Response(200, json={"id": "2025-08-14"})
    )
    await call(mcp, "update_wellness", {"date": "2025-08-14", "Alcohol": 2})
    assert json.loads(put_route.calls[0].request.content) == {"Alcohol": 2}


@respx.mock
async def test_create_event_builds_the_event_body(mcp):
    route = respx.post(f"{BASE}/api/v1/athlete/i1/events").mock(
        return_value=httpx.Response(200, json={"id": 7, "name": "Sweet spot"})
    )
    out = await call(
        mcp,
        "create_event",
        {
            "start_date_local": "2025-09-04",
            "category": "WORKOUT",
            "name": "Sweet spot",
            "sport": "Ride",
            "description": "- 10m 55%\n3x\n- 12m 90%",
            "moving_time": 4500,
        },
    )
    body = json.loads(route.calls[0].request.content)
    assert body["type"] == "Ride"  # `sport` is mapped onto the API's `type` field
    assert body["category"] == "WORKOUT"
    assert "indoor" not in body  # unset optionals are not sent
    assert out["id"] == 7


@respx.mock
async def test_delete_event_targets_a_single_event(mcp):
    route = respx.delete(f"{BASE}/api/v1/athlete/i1/events/7").mock(
        return_value=httpx.Response(200)
    )
    await mcp.call_tool("delete_event", {"event_id": 7})
    assert "others" not in route.calls[0].request.url.params


@respx.mock
async def test_athlete_profile_summarises_sports_and_hides_the_api_key(mcp):
    respx.get(f"{BASE}/api/v1/athlete/i1").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "i1",
                "name": "Test",
                "icu_api_key": "secret",
                "sportSettings": [{"id": 5, "types": ["Ride"], "ftp": 280, "lthr": 165}],
            },
        )
    )
    out = await call(mcp, "get_athlete_profile", {})
    assert "icu_api_key" not in json.dumps(out)
    assert out["sports"] == [{"id": 5, "types": ["Ride"], "ftp": 280, "lthr": 165}]


@respx.mock
async def test_best_efforts_curve_routes_by_metric(mcp):
    route = respx.get(f"{BASE}/api/v1/athlete/i1/hr-curves").mock(
        return_value=httpx.Response(200, json={"curves": []})
    )
    await call(mcp, "get_best_efforts_curve", {"metric": "hr", "sport": "Run"})
    assert route.called
    assert route.calls[0].request.url.params["type"] == "Run"
