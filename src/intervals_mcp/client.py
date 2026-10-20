"""HTTP client for the Intervals.icu API.

Auth is HTTP basic with the literal username ``API_KEY`` and your key from
https://intervals.icu/settings as the password.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from mcp.server.mcpserver.exceptions import ToolError

BASE_URL = "https://intervals.icu"
TIMEOUT = 30.0


class IntervalsError(ToolError):
    """An API error with a message that is safe and useful to show the caller.

    Subclasses ToolError so the message reaches the model: the MCP SDK replaces any
    other exception with a generic "Error executing tool" and withholds the text.
    """


class IntervalsClient:
    def __init__(self, api_key: str | None = None, athlete_id: str | None = None) -> None:
        key = api_key or os.environ.get("INTERVALS_API_KEY")
        if not key:
            raise IntervalsError(
                "INTERVALS_API_KEY is not set. Copy your key from the API Key section of "
                "https://intervals.icu/settings and set it in the environment."
            )
        self._athlete_id = athlete_id or os.environ.get("INTERVALS_ATHLETE_ID") or None
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            auth=("API_KEY", key),
            timeout=TIMEOUT,
            headers={"Accept": "application/json"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def athlete(self, athlete_id: str | None = None) -> str:
        """Athlete to act on: the argument, the configured id, or the authenticated athlete."""
        if athlete_id:
            return athlete_id
        if self._athlete_id is None:
            try:
                me = await self.get("/api/v1/athlete/0")
            except IntervalsError as exc:
                raise IntervalsError(
                    f"Could not work out which athlete you are ({exc}). Set INTERVALS_ATHLETE_ID "
                    "in the environment to your id from https://intervals.icu/settings."
                ) from exc
            self._athlete_id = str(me.get("id") or "").strip()
            if not self._athlete_id:
                raise IntervalsError(
                    "Intervals.icu did not return an athlete id. Set INTERVALS_ATHLETE_ID "
                    "in the environment to your id from https://intervals.icu/settings."
                )
        return self._athlete_id

    async def get(self, path: str, **params: Any) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json: Any = None, **params: Any) -> Any:
        return await self._request("POST", path, params=params, json=json)

    async def put(self, path: str, json: Any = None, **params: Any) -> Any:
        return await self._request("PUT", path, params=params, json=json)

    async def delete(self, path: str, **params: Any) -> Any:
        return await self._request("DELETE", path, params=params)

    async def _request(
        self, method: str, path: str, params: dict[str, Any] | None = None, json: Any = None
    ) -> Any:
        query = _clean_params(params or {})
        for attempt in (1, 2):
            try:
                response = await self._client.request(method, path, params=query, json=json)
            except httpx.TimeoutException as exc:
                raise IntervalsError(f"Intervals.icu timed out after {TIMEOUT:.0f}s on {path}") from exc
            except httpx.HTTPError as exc:
                raise IntervalsError(f"Could not reach Intervals.icu: {exc}") from exc

            if response.status_code == 429 and attempt == 1:
                await asyncio.sleep(_retry_after(response))
                continue
            if response.is_success:
                return _parse(response)
            raise IntervalsError(_error_message(response, path))
        raise IntervalsError("Intervals.icu is rate limiting this API key. Try again in a minute.")


def _clean_params(params: dict[str, Any]) -> dict[str, Any]:
    """Drop unset params and join list values, which the API expects comma separated."""
    out: dict[str, Any] = {}
    for name, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            out[name] = "true" if value else "false"
        elif isinstance(value, (list, tuple)):
            if value:
                out[name] = ",".join(str(v) for v in value)
        else:
            out[name] = value
    return out


def _parse(response: httpx.Response) -> Any:
    if not response.content:
        return None
    if "json" in response.headers.get("content-type", ""):
        return response.json()
    try:
        return response.json()
    except ValueError:
        return response.text


def _retry_after(response: httpx.Response) -> float:
    try:
        return min(float(response.headers.get("Retry-After", 5)), 30.0)
    except ValueError:
        return 5.0


def _error_message(response: httpx.Response, path: str) -> str:
    """Short, actionable message. Never leak an HTML error page into the model's context."""
    code = response.status_code
    if code == 401:
        return "Invalid or missing INTERVALS_API_KEY (Intervals.icu returned 401)."
    if code == 403:
        return f"Not authorised for this athlete or resource: {path}"
    if code == 404:
        return f"Not found: {path}"
    return f"Intervals.icu returned {code} for {path}: {_body_hint(response)}"


def _body_hint(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        text = response.text.strip()
        return (text[:200] + "...") if len(text) > 200 else (text or "(no body)")
    if isinstance(body, dict):
        for key in ("message", "error", "detail"):
            if body.get(key):
                return str(body[key])[:300]
    return str(body)[:300]
