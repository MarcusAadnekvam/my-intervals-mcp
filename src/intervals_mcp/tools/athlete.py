"""Athlete profile, thresholds and training zones."""

from __future__ import annotations

from typing import Any

from ..client import IntervalsClient
from ..compact import ATHLETE_FIELDS, SPORT_SETTINGS_FIELDS, project

# Enough to answer "what are my numbers?" without dumping every zone boundary.
_THRESHOLD_KEYS = (
    "id",
    "types",
    "ftp",
    "indoor_ftp",
    "w_prime",
    "p_max",
    "lthr",
    "max_hr",
    "threshold_pace",
    "pace_units",
)


def register(mcp: Any, client: IntervalsClient) -> None:
    @mcp.tool()
    async def get_athlete_profile(athlete_id: str | None = None) -> dict:
        """Get the athlete's profile plus a per-sport summary of their thresholds.

        Returns basic profile info (name, sex, timezone, date of birth, current weight
        and resting HR) and, for every sport the athlete has set up, the key numbers:
        FTP, W', Pmax, LTHR, max HR and threshold pace. Call get_sport_settings for the
        full zone boundaries of one sport.
        """
        aid = await client.athlete(athlete_id)
        data = await client.get(f"/api/v1/athlete/{aid}")
        profile = project(data, ATHLETE_FIELDS)
        settings = data.get("sportSettings") or []
        profile["sports"] = [project(s, _THRESHOLD_KEYS) for s in settings]
        return profile

    @mcp.tool()
    async def get_sport_settings(sport: str, athlete_id: str | None = None) -> dict:
        """Get full training zones and thresholds for one sport.

        `sport` is an activity type such as Ride, Run, Swim, VirtualRide or TrailRun
        (or a sport-settings id). Returns FTP/W'/Pmax with power zone boundaries and
        names, LTHR/max HR with heart rate zones, and threshold pace with pace zones —
        everything needed to judge which zone an effort fell in.
        """
        aid = await client.athlete(athlete_id)
        data = await client.get(f"/api/v1/athlete/{aid}/sport-settings/{sport}")
        return project(data, SPORT_SETTINGS_FIELDS)
