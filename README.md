# intervals-mcp

An MCP server that gives Claude access to your [Intervals.icu](https://intervals.icu)
training data — activities, planned workouts, wellness, fitness/form and training zones.

## Setup

```bash
pip install -e .
```

Both values are on the settings page at https://intervals.icu/settings — the key under
**API Key**, the athlete id in the page URL and next to your name (it looks like `i123456`).

```bash
export INTERVALS_API_KEY=...
export INTERVALS_ATHLETE_ID=i123456
```

Register with Claude Code:

```bash
claude mcp add intervals \
  --env INTERVALS_API_KEY=... \
  --env INTERVALS_ATHLETE_ID=i123456 \
  -- python -m intervals_mcp.server
```

### Claude Desktop

Claude Desktop runs local stdio servers like this one directly — no hosting, and the API
key never leaves the machine. Open **Settings > Developer > Edit Config**, which opens
`claude_desktop_config.json`, and merge in an `mcpServers` entry (the file usually already
holds other settings — add to it, don't replace it):

```json
{
  "mcpServers": {
    "intervals": {
      "command": "C:\\Program Files\\Python311\\python.exe",
      "args": ["-m", "intervals_mcp.server"],
      "env": {
        "INTERVALS_API_KEY": "...",
        "INTERVALS_ATHLETE_ID": "i123456"
      }
    }
  }
}
```

Use the **absolute path** to `python.exe`, not bare `python` — Claude Desktop launches
servers with a minimal environment and may not resolve it from `PATH`. Then quit Claude
Desktop completely (tray icon included) and reopen it; a reload is not enough.

**Where that file actually lives depends on how Claude Desktop was installed**, and getting
this wrong is the usual reason a server never appears:

| Install | Config path |
| --- | --- |
| Standard installer | `%APPDATA%\Claude\claude_desktop_config.json` |
| Microsoft Store (MSIX) | `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json` |

Store builds run under filesystem virtualisation, so their `%APPDATA%` is redirected into
the package folder; a config written to the plain `%APPDATA%\Claude` path is silently
ignored. **Settings > Developer > Edit Config** always opens the right one. To find it
yourself, check whether Claude runs from `C:\Program Files\WindowsApps\Claude_...`:

```powershell
Get-Process claude | Select-Object Path
```

Logs sit in a `logs\mcp.log` beside whichever config path applies.

### claude.ai in a browser

Not supported by this server as written. The web and mobile apps only take *remote*
connectors: Claude connects from Anthropic's cloud, so the server must sit at a public
HTTPS URL, which this stdio server is not. That would also need authentication of its own
— on stdio the OS is the security boundary, but on a public URL anyone who found it could
read your training history and write to your calendar, since the Intervals.icu key lives
in the server rather than with the caller.

### Which athlete the tools act on

In precedence order:

1. the `athlete_id` argument, which every tool accepts — use it to look at an athlete you
   coach rather than yourself;
2. `INTERVALS_ATHLETE_ID`;
3. failing both, `GET /api/v1/athlete/0` — Intervals.icu's alias for the athlete the API
   key belongs to. The result is cached for the life of the process, so this costs one
   request on the first tool call.

Set `INTERVALS_ATHLETE_ID` anyway. It skips that request, and the fallback resolves lazily,
so if it ever fails you find out mid-conversation as a tool error instead of at startup.

## Tools

**Athlete & zones** — `get_athlete_profile`, `get_sport_settings`

**Activities & analysis** — `list_activities`, `search_activities`, `get_activity`,
`get_activity_intervals`, `get_activity_streams`, `find_intervals`,
`get_best_efforts_curve`

**Wellness & fitness** — `list_wellness`, `get_fitness_trend`, `update_wellness`

**Calendar & workouts** — `list_calendar`, `get_event`, `create_event`, `update_event`,
`delete_event`, `list_workout_library`

## What it can and cannot change

Writes are limited to **calendar events and wellness records**. Everything else is
read-only by construction — these endpoints exist in the API but are deliberately not
exposed: deleting or editing activities, the bulk calendar range update and range delete,
sport settings (FTP and zones), gear, folders, and the athlete record. `delete_event`
removes only the single event you name; it never uses the API's "delete others added at
the same time" option.

## Design notes

The API is wide: an activity has 183 fields, an athlete 158, an interval 84. Returning
those raw would flood the model's context, so every response is projected onto an
explicit allowlist in `compact.py` and stripped of nulls. Where the API supports
server-side projection (activities and wellness) the allowlist is sent as the `fields`
query param; elsewhere it is applied on the way out. List tools take a `fields` argument
to override the default. Activity streams — one sample per second — are returned as
min/mean/max plus a series downsampled to at most 1000 points.

Allowlists rather than denylists also mean secrets such as `Athlete.icu_api_key` can
never appear in a response.

`intervals.icu-swagger.json` is the API spec, kept for reference. It is **UTF-16
encoded**, so read it with `encoding="utf-16"`.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The suite mocks HTTP and makes no live calls.
