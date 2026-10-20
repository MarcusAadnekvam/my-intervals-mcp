"""Daily wellness records and the fitness/fatigue/form trend derived from them."""

from __future__ import annotations

from typing import Any

from ..client import IntervalsClient
from ..compact import WELLNESS_FIELDS, project_all

_FITNESS_FIELDS = ("id", "ctl", "atl", "rampRate")

# Fields worth logging by hand. Named explicitly so the tool schema documents itself.
_WRITABLE = (
    "weight",
    "restingHR",
    "hrv",
    "sleepSecs",
    "sleepScore",
    "sleepQuality",
    "soreness",
    "fatigue",
    "stress",
    "mood",
    "motivation",
    "injury",
    "spO2",
    "steps",
    "comments",
    "Alcohol",
)


def register(mcp: Any, client: IntervalsClient) -> None:
    @mcp.tool()
    async def list_wellness(
        oldest: str,
        newest: str | None = None,
        fields: list[str] | None = None,
        athlete_id: str | None = None,
    ) -> list[dict]:
        """List daily wellness records for a date range.

        Each record's `id` is its local ISO-8601 date. Returns fitness (ctl), fatigue
        (atl), ramp rate, weight, resting HR, HRV, sleep, the subjective 1-4 scores for
        soreness, fatigue, stress, mood and motivation, and `Alcohol` (the athlete's
        custom field for units consumed). Pass `fields` to request different fields of
        the Intervals.icu wellness object.
        """
        aid = await client.athlete(athlete_id)
        data = await client.get(
            f"/api/v1/athlete/{aid}/wellness",
            oldest=oldest,
            newest=newest,
            fields=list(fields) if fields else list(WELLNESS_FIELDS),
        )
        return project_all(data, fields or WELLNESS_FIELDS)

    @mcp.tool()
    async def get_fitness_trend(
        oldest: str, newest: str | None = None, athlete_id: str | None = None
    ) -> dict:
        """Get the fitness, fatigue and form trend over a date range.

        Returns a day-by-day series of CTL (fitness), ATL (fatigue), form (CTL - ATL)
        and ramp rate, plus a summary with the start and end values and the change over
        the period. Positive form means freshness, negative means accumulated fatigue.
        """
        aid = await client.athlete(athlete_id)
        data = await client.get(
            f"/api/v1/athlete/{aid}/wellness",
            oldest=oldest,
            newest=newest,
            fields=list(_FITNESS_FIELDS),
        )
        series = []
        for row in project_all(data, _FITNESS_FIELDS):
            ctl, atl = row.get("ctl"), row.get("atl")
            entry = {"date": row.get("id"), "ctl": ctl, "atl": atl}
            if ctl is not None and atl is not None:
                entry["form"] = round(ctl - atl, 1)
            if row.get("rampRate") is not None:
                entry["ramp_rate"] = row["rampRate"]
            series.append(entry)
        series.sort(key=lambda e: e.get("date") or "")
        return {"days": series, "summary": _summary(series)}

    @mcp.tool()
    async def update_wellness(
        date: str,
        weight: float | None = None,
        restingHR: int | None = None,
        hrv: float | None = None,
        sleepSecs: int | None = None,
        sleepScore: float | None = None,
        sleepQuality: int | None = None,
        soreness: int | None = None,
        fatigue: int | None = None,
        stress: int | None = None,
        mood: int | None = None,
        motivation: int | None = None,
        injury: int | None = None,
        spO2: float | None = None,
        steps: int | None = None,
        comments: str | None = None,
        Alcohol: float | None = None,
        athlete_id: str | None = None,
    ) -> dict:
        """Update the wellness record for one day. Only the fields you pass are changed.

        `date` is the local ISO-8601 day (2025-08-14). Weight is in kg, sleepSecs in
        seconds. The subjective scores (sleepQuality, soreness, fatigue, stress, mood,
        motivation, injury) are 1-4 in Intervals.icu, where 1 is best. `Alcohol` is the
        athlete's custom wellness field for units of alcohol consumed that day.
        """
        aid = await client.athlete(athlete_id)
        values = locals()
        body = {k: values[k] for k in _WRITABLE if values[k] is not None}
        return await client.put(f"/api/v1/athlete/{aid}/wellness/{date}", json=body)


def _summary(series: list[dict]) -> dict:
    dated = [e for e in series if e.get("ctl") is not None and e.get("atl") is not None]
    if not dated:
        return {}
    first, last = dated[0], dated[-1]
    return {
        "from": first["date"],
        "to": last["date"],
        "ctl_start": first["ctl"],
        "ctl_end": last["ctl"],
        "ctl_change": round(last["ctl"] - first["ctl"], 1),
        "atl_end": last["atl"],
        "form_start": first.get("form"),
        "form_end": last.get("form"),
    }
