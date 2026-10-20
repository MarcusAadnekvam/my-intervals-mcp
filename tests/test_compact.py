from intervals_mcp.compact import downsample, project, project_all, summarise


def test_project_keeps_allowlist_and_drops_empties():
    obj = {"id": 1, "name": "Ride", "hrv": None, "tags": [], "secret": "x", "watts": 0}
    assert project(obj, ("id", "name", "hrv", "tags", "watts")) == {
        "id": 1,
        "name": "Ride",
        "watts": 0,
    }


def test_project_excludes_fields_outside_the_allowlist():
    assert "icu_api_key" not in project({"id": 1, "icu_api_key": "secret"}, ("id",))


def test_project_none_keeps_every_field():
    assert project({"a": 1, "b": None}, None) == {"a": 1}


def test_project_all_ignores_non_lists():
    assert project_all(None, ("id",)) == []


def test_downsample_shortens_to_max_points_and_keeps_the_last():
    values = list(range(5000))
    thinned = downsample(values, 200)
    assert len(thinned) == 200
    assert thinned[0] == 0
    assert thinned[-1] == 4999


def test_downsample_leaves_short_series_alone():
    assert downsample([1, 2, 3], 200) == [1, 2, 3]


def test_summarise_skips_nulls_and_returns_none_when_empty():
    assert summarise([1, None, 3]) == {"count": 2, "min": 1, "mean": 2.0, "max": 3}
    assert summarise([None, None]) is None
