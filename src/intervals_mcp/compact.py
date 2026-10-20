"""Response shaping.

Intervals.icu returns very wide objects: Activity has 183 fields, Athlete 158,
Interval 84, SportSettings 62, Event 60, Wellness 46. Returning them raw would
flood the model's context, so every response is projected onto an explicit
allowlist and stripped of nulls. Allowlists (rather than denylists) also keep
secrets such as ``Athlete.icu_api_key`` out of responses by construction.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

# Passed to the API as the `fields` query param on GET /athlete/{id}/activities.
ACTIVITY_FIELDS: tuple[str, ...] = (
    "id",
    "start_date_local",
    "name",
    "type",
    "description",
    "distance",
    "moving_time",
    "elapsed_time",
    "total_elevation_gain",
    "icu_training_load",
    "icu_intensity",
    "icu_ftp",
    "icu_average_watts",
    "icu_weighted_avg_watts",
    "average_heartrate",
    "max_heartrate",
    "average_cadence",
    "average_speed",
    "pace",
    "gap",
    "calories",
    "icu_atl",
    "icu_ctl",
    "icu_rpe",
    "feel",
    "trainer",
    "race",
    "icu_zone_times",
    "icu_hr_zone_times",
    "tags",
)

INTERVAL_FIELDS: tuple[str, ...] = (
    "id",
    "label",
    "type",
    "group_id",
    "start_time",
    "end_time",
    "moving_time",
    "distance",
    "average_watts",
    "weighted_average_watts",
    "max_watts",
    "intensity",
    "zone",
    "average_heartrate",
    "max_heartrate",
    "average_cadence",
    "average_speed",
    "gap",
    "total_elevation_gain",
    "training_load",
    "decoupling",
)

# Passed to the API as the `fields` query param on GET /athlete/{id}/wellness.
WELLNESS_FIELDS: tuple[str, ...] = (
    "id",  # the local ISO-8601 date
    "ctl",
    "atl",
    "rampRate",
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
    "Alcohol",  # custom wellness field, not part of the standard Wellness object
)

EVENT_FIELDS: tuple[str, ...] = (
    "id",
    "start_date_local",
    "end_date_local",
    "category",
    "type",
    "name",
    "description",
    "indoor",
    "moving_time",
    "distance",
    "icu_training_load",
    "icu_intensity",
    "target",
    "load_target",
    "time_target",
    "distance_target",
    "tags",
    "external_id",
    "plan_workout_id",
)

ATHLETE_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "sex",
    "city",
    "country",
    "timezone",
    "locale",
    "measurement_preference",
    "icu_date_of_birth",
    "icu_weight",
    "icu_resting_hr",
    "bio",
)

SPORT_SETTINGS_FIELDS: tuple[str, ...] = (
    "id",
    "types",
    "ftp",
    "indoor_ftp",
    "w_prime",
    "p_max",
    "power_zones",
    "power_zone_names",
    "sweet_spot_min",
    "sweet_spot_max",
    "lthr",
    "max_hr",
    "hr_zones",
    "hr_zone_names",
    "threshold_pace",
    "pace_units",
    "pace_zones",
    "pace_zone_names",
    "best_effort_distances",
)

WORKOUT_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "description",
    "type",
    "indoor",
    "folder_id",
    "day",
    "moving_time",
    "distance",
    "icu_training_load",
    "icu_intensity",
    "target",
    "tags",
)

FOLDER_FIELDS: tuple[str, ...] = (
    "id",
    "name",
    "type",
    "description",
    "activity_types",
    "num_workouts",
    "duration_weeks",
    "start_date_local",
)


def project(obj: Any, fields: Sequence[str] | None) -> Any:
    """Keep only `fields` (all of them when None) and drop empty values."""
    if not isinstance(obj, dict):
        return obj
    keys = fields if fields is not None else obj.keys()
    return {k: obj[k] for k in keys if k in obj and not _is_empty(obj[k])}


def project_all(objs: Any, fields: Sequence[str] | None) -> list[Any]:
    if not isinstance(objs, list):
        return []
    return [project(o, fields) for o in objs]


def _is_empty(value: Any) -> bool:
    return value is None or value == [] or value == {} or value == ""


def downsample(values: Sequence[Any], max_points: int) -> list[Any]:
    """Evenly thin a series to at most `max_points`, always keeping the last point."""
    if max_points <= 0 or len(values) <= max_points:
        return list(values)
    step = len(values) / max_points
    thinned = [values[min(int(i * step), len(values) - 1)] for i in range(max_points)]
    thinned[-1] = values[-1]
    return thinned


def summarise(values: Iterable[Any]) -> dict[str, float] | None:
    """min/mean/max/count over the numeric points of a stream."""
    nums = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
    if not nums:
        return None
    return {
        "count": len(nums),
        "min": round(min(nums), 2),
        "mean": round(sum(nums) / len(nums), 2),
        "max": round(max(nums), 2),
    }
