"""Completed activities: listing, search, detail, intervals, streams and best-effort curves."""

from __future__ import annotations

from typing import Any

from ..client import IntervalsClient, IntervalsError
from ..compact import (
    ACTIVITY_FIELDS,
    INTERVAL_FIELDS,
    downsample,
    project,
    project_all,
    summarise,
)

_CURVE_PATHS = {
    "power": "power-curves",
    "hr": "hr-curves",
    "pace": "pace-curves",
}

MAX_STREAM_POINTS = 1000


def register(mcp: Any, client: IntervalsClient) -> None:
    @mcp.tool()
    async def list_activities(
        oldest: str,
        newest: str | None = None,
        sport: str | None = None,
        limit: int | None = None,
        fields: list[str] | None = None,
        athlete_id: str | None = None,
    ) -> list[dict]:
        """List completed activities in a date range, newest first.

        `oldest` and `newest` are local ISO-8601 dates (2025-08-01) or date-times;
        `newest` defaults to now. `sport` filters by activity type (Ride, Run, Swim...).
        A curated set of ~30 fields is returned; pass `fields` to ask for different ones
        (any field of the Intervals.icu activity object).
        """
        aid = await client.athlete(athlete_id)
        data = await client.get(
            f"/api/v1/athlete/{aid}/activities",
            oldest=oldest,
            newest=newest,
            limit=limit,
            fields=list(fields) if fields else list(ACTIVITY_FIELDS),
        )
        rows = project_all(data, fields or ACTIVITY_FIELDS)
        if sport:
            rows = [r for r in rows if str(r.get("type", "")).lower() == sport.lower()]
        return rows

    @mcp.tool()
    async def search_activities(
        query: str, limit: int = 20, athlete_id: str | None = None
    ) -> list[dict]:
        """Search activities by name, or by tag when the query starts with '#'.

        Case insensitive name search; '#race' does an exact tag search. Returns compact
        summaries (id, name, date, type, distance, moving time, tags) — follow up with
        get_activity for the full picture.
        """
        aid = await client.athlete(athlete_id)
        data = await client.get(
            f"/api/v1/athlete/{aid}/activities/search", q=query, limit=limit
        )
        return project_all(data, None)

    @mcp.tool()
    async def get_activity(activity_id: str, include_intervals: bool = False) -> dict:
        """Get one completed activity in detail.

        Includes duration, distance, elevation, average and normalised power, heart rate,
        cadence, pace, training load, intensity, RPE/feel and time-in-zone. Set
        `include_intervals` to also get the laps/intervals inline.
        """
        data = await client.get(f"/api/v1/activity/{activity_id}", intervals=include_intervals)
        activity = project(data, ACTIVITY_FIELDS)
        if include_intervals:
            activity["intervals"] = project_all(data.get("icu_intervals"), INTERVAL_FIELDS)
        return activity

    @mcp.tool()
    async def get_activity_intervals(activity_id: str) -> list[dict]:
        """Get the laps/intervals of an activity.

        Per interval: label, duration, distance, average and normalised power, zone,
        heart rate, cadence, speed/GAP, training load and decoupling. Use this to analyse
        how an interval session was actually executed.
        """
        data = await client.get(f"/api/v1/activity/{activity_id}/intervals")
        intervals = data.get("icu_intervals") if isinstance(data, dict) else data
        return project_all(intervals, INTERVAL_FIELDS)

    @mcp.tool()
    async def get_activity_streams(
        activity_id: str, types: list[str], max_points: int = 200
    ) -> dict:
        """Get time-series data for an activity, summarised and downsampled.

        `types` names the streams wanted, e.g. watts, heartrate, cadence, velocity_smooth,
        altitude, distance, temp, torque. Raw streams are one sample per second, so each
        stream is returned as min/mean/max/count plus a series evenly thinned to
        `max_points` (default 200, maximum 1000). Ask for only the streams you need.
        """
        if max_points > MAX_STREAM_POINTS:
            raise IntervalsError(f"max_points cannot exceed {MAX_STREAM_POINTS}")
        if not types:
            raise IntervalsError("Name at least one stream in `types`, e.g. ['watts'].")
        data = await client.get(
            f"/api/v1/activity/{activity_id}/streams",
            types=types,
            includeDefaults=False,
        )
        out: dict[str, Any] = {"activity_id": activity_id, "max_points": max_points}
        for stream in data or []:
            values = stream.get("data") or []
            out[stream.get("type", "unknown")] = {
                "summary": summarise(values),
                "points": downsample(values, max_points),
                "raw_length": len(values),
            }
        return out

    @mcp.tool()
    async def find_intervals(
        min_secs: int,
        max_secs: int,
        min_intensity: int,
        max_intensity: int,
        sport: str | None = None,
        min_reps: int | None = None,
        max_reps: int | None = None,
        limit: int | None = None,
        athlete_id: str | None = None,
    ) -> list[dict]:
        """Find past activities containing intervals of a given duration and intensity.

        Intensity is a percentage of threshold. For example 240-360 seconds at 105-120%
        finds VO2max sets. `min_reps`/`max_reps` restrict how many matching intervals an
        activity must contain. Useful for "when did I last do X?" and for comparing
        repeats of the same session over time.
        """
        aid = await client.athlete(athlete_id)
        data = await client.get(
            f"/api/v1/athlete/{aid}/activities/interval-search",
            minSecs=min_secs,
            maxSecs=max_secs,
            minIntensity=min_intensity,
            maxIntensity=max_intensity,
            type=sport,
            minReps=min_reps,
            maxReps=max_reps,
            limit=limit,
        )
        return project_all(data, None)

    @mcp.tool()
    async def get_best_efforts_curve(
        metric: str,
        sport: str,
        curves: list[str] | None = None,
        newest: str | None = None,
        athlete_id: str | None = None,
    ) -> Any:
        """Get the athlete's best-efforts curve for a sport.

        `metric` is 'power' (best watts by duration), 'hr' (best heart rate by duration)
        or 'pace' (best pace by distance). `sport` is an activity type such as Ride or Run.
        `curves` selects the periods to compare, e.g. ['s1440','s90d','all'] — the default
        is the last year. Use this for "am I fitter than last season?" questions.
        """
        if metric not in _CURVE_PATHS:
            raise IntervalsError("metric must be one of: power, hr, pace")
        aid = await client.athlete(athlete_id)
        return await client.get(
            f"/api/v1/athlete/{aid}/{_CURVE_PATHS[metric]}",
            type=sport,
            curves=curves,
            newest=newest,
        )
