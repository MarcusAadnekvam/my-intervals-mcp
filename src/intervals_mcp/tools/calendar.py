"""The training calendar: planned workouts, notes and races, plus the workout library."""

from __future__ import annotations

from typing import Any

from ..client import IntervalsClient
from ..compact import EVENT_FIELDS, FOLDER_FIELDS, WORKOUT_FIELDS, project, project_all


def register(mcp: Any, client: IntervalsClient) -> None:
    @mcp.tool()
    async def list_calendar(
        oldest: str,
        newest: str | None = None,
        category: list[str] | None = None,
        limit: int | None = None,
        resolve: bool = False,
        athlete_id: str | None = None,
    ) -> list[dict]:
        """List planned workouts, notes and races on the calendar for a date range.

        `oldest`/`newest` are local ISO-8601 dates; `newest` defaults to `oldest` plus
        six days. `category` filters, e.g. ['WORKOUT'] or ['RACE_A','RACE_B'] — valid
        values are WORKOUT, RACE_A, RACE_B, RACE_C, NOTE, PLAN, HOLIDAY, SICK, INJURED,
        SET_EFTP, FITNESS_DAYS, SEASON_START, TARGET, SET_FITNESS. Set `resolve` to turn
        percentage targets into absolute watts, bpm and m/s.
        """
        aid = await client.athlete(athlete_id)
        data = await client.get(
            f"/api/v1/athlete/{aid}/events",
            oldest=oldest,
            newest=newest,
            category=category,
            limit=limit,
            resolve=resolve,
        )
        return project_all(data, EVENT_FIELDS)

    @mcp.tool()
    async def get_event(event_id: int, athlete_id: str | None = None) -> dict:
        """Get one calendar event in full, including its workout steps.

        Returns the trimmed event plus `workout_doc`, the structured step definition,
        when the event is a planned workout.
        """
        aid = await client.athlete(athlete_id)
        data = await client.get(f"/api/v1/athlete/{aid}/events/{event_id}")
        event = project(data, EVENT_FIELDS)
        if data.get("workout_doc"):
            event["workout_doc"] = data["workout_doc"]
        return event

    @mcp.tool()
    async def create_event(
        start_date_local: str,
        category: str,
        name: str,
        description: str | None = None,
        sport: str | None = None,
        moving_time: int | None = None,
        indoor: bool | None = None,
        target: str | None = None,
        end_date_local: str | None = None,
        athlete_id: str | None = None,
    ) -> dict:
        """Add a planned workout, note or race to the calendar.

        `start_date_local` is a local ISO-8601 date or date-time. `category` is WORKOUT,
        NOTE, RACE_A, RACE_B, RACE_C, HOLIDAY, SICK or INJURED. `sport` is the activity
        type (Ride, Run, Swim...) and is required for a workout. `moving_time` is the
        planned duration in seconds. `target` is AUTO, POWER, HR or PACE.

        Workout steps go in `description` using the Intervals.icu text syntax, one step
        per line starting with '-'. Duration first, then intensity:

            Warm up
            - 10m 55-70%
            3x
            - 5m 105%
            - 3m 50%
            Cool down
            - 10m 55%

        Durations are written 30s, 10m or 1h. Intensity is a percentage of FTP (or of
        threshold HR/pace when `target` is HR or PACE), optionally a range with a dash.
        'Nx' on its own line repeats the block of steps that follows it.
        """
        aid = await client.athlete(athlete_id)
        body = _event_body(
            start_date_local=start_date_local,
            category=category,
            name=name,
            description=description,
            type=sport,
            moving_time=moving_time,
            indoor=indoor,
            target=target,
            end_date_local=end_date_local,
        )
        data = await client.post(f"/api/v1/athlete/{aid}/events", json=body)
        return project(data, EVENT_FIELDS)

    @mcp.tool()
    async def update_event(
        event_id: int,
        start_date_local: str | None = None,
        name: str | None = None,
        description: str | None = None,
        sport: str | None = None,
        moving_time: int | None = None,
        indoor: bool | None = None,
        target: str | None = None,
        category: str | None = None,
        athlete_id: str | None = None,
    ) -> dict:
        """Change an existing calendar event. Only the fields you pass are changed.

        Use this to move a session to another day, retime it, or rewrite its steps.
        `description` takes the same workout text syntax as create_event.
        """
        aid = await client.athlete(athlete_id)
        body = _event_body(
            start_date_local=start_date_local,
            category=category,
            name=name,
            description=description,
            type=sport,
            moving_time=moving_time,
            indoor=indoor,
            target=target,
        )
        data = await client.put(f"/api/v1/athlete/{aid}/events/{event_id}", json=body)
        return project(data, EVENT_FIELDS)

    @mcp.tool()
    async def delete_event(event_id: int, athlete_id: str | None = None) -> str:
        """Delete one event from the calendar. Only the event with this id is removed."""
        aid = await client.athlete(athlete_id)
        await client.delete(f"/api/v1/athlete/{aid}/events/{event_id}")
        return f"Deleted event {event_id}."

    @mcp.tool()
    async def list_workout_library(
        folder_id: int | None = None, athlete_id: str | None = None
    ) -> dict:
        """List the athlete's saved workouts and the folders and training plans holding them.

        Returns `folders` (name, type, activity types, workout count) and `workouts`
        (name, sport, duration, load, intensity), optionally limited to one folder.
        Use get_event or create_event to put one of these on the calendar.
        """
        aid = await client.athlete(athlete_id)
        folders = await client.get(f"/api/v1/athlete/{aid}/folders")
        workouts = await client.get(f"/api/v1/athlete/{aid}/workouts")
        rows = project_all(workouts, WORKOUT_FIELDS)
        if folder_id is not None:
            rows = [w for w in rows if w.get("folder_id") == folder_id]
        return {"folders": project_all(folders, FOLDER_FIELDS), "workouts": rows}


def _event_body(**fields: Any) -> dict:
    return {k: v for k, v in fields.items() if v is not None}
