# Phase 6.5 — Venue Weather Monitoring and Alert Overlay

Phase 6.5 adds venue-aware weather monitoring, National Weather Service alerts, operator-controlled weather graphics, game-delay states, and a manual lightning safety timer.

## Venue resolution

The service resolves the weather location in this order:

1. the active broadcast's `venue_id`;
2. an exact active venue-name match;
3. the active home school's configured venue when `weather.use_home_venue_address` is enabled.

The selected game venue is authoritative. The home venue is only a fallback.

Venues may store latitude and longitude directly. When they do not, the authenticated geocoding action uses the U.S. Census Geocoding Services API and persists the resulting coordinates on the venue record. Operators should verify coordinates before game day.

## Weather sources

The service uses:

- `https://api.weather.gov/points/{latitude},{longitude}` to resolve the NWS gridpoint;
- the returned `forecastHourly` URL for temperature, wind, conditions, and precipitation probability;
- `https://api.weather.gov/alerts/active?point={latitude},{longitude}` for active watches, warnings, and advisories.

Requests include a configurable `User-Agent`. The default polling interval is 60 seconds and can never be configured below 30 seconds. Last-known conditions and alerts remain available when a refresh fails, but the overlay state is marked stale.

## Operator approval policy

Weather alerts are preview-first by default. A received alert does not automatically appear on the broadcast. The operator selects and approves an alert before displaying it.

- Severe and Extreme alerts use the emergency banner.
- Moderate, Minor, and Unknown alerts use the advisory banner.
- Expired or cancelled selected alerts are automatically removed from the overlay.
- Alert receipt, display, dismissal, replacement, refresh failure, delay, resumption, and lightning events are retained in bounded audit history.

Emergency and weather-delay overlays set `sponsor_allowed` to false. Routine weather bugs and non-emergency advisories may use the normal broadcast package later when the theme engine is implemented.

## OBS browser source

Add a transparent OBS browser source pointing to:

```text
http://127.0.0.1:5050/weather-overlay
```

Recommended dimensions:

```text
1920 × 1080
```

The overlay supports:

- compact weather bug;
- advisory banner;
- severe-weather emergency banner;
- full-screen weather delay;
- game-resumption state;
- visible stale-data warning;
- lightning timer display during delay mode.

## Monitoring command

Run continuous monitoring from the repository root:

```cmd
python tools\run_weather_monitor.py --interval 60
```

Run a single refresh for testing:

```cmd
python tools\run_weather_monitor.py --once
```

The monitor is independent of Flask request handling. Network delays therefore do not block Command Center requests.

## Authenticated API

- `GET /api/weather/status`
- `POST /api/weather/refresh`
- `POST /api/weather/geocode`
- `POST /api/weather/alerts/<alert-id>/approve`
- `POST /api/weather/alerts/dismiss`
- `POST /api/weather/overlay`
- `POST /api/weather/delay/start`
- `POST /api/weather/delay/resume`
- `POST /api/weather/lightning/observed`
- `POST /api/weather/lightning/reset`

Public read-only presentation:

- `GET /weather-overlay`
- `GET /api/weather/overlay-state`

## Lightning policy

Recording a lightning or thunder observation starts or restarts a 30-minute timer. Completion of that timer does **not** declare the field safe. The application always states that school and venue officials make the resumption decision.

Resetting the timer early requires the exact confirmation phrase:

```text
RESET LIGHTNING TIMER
```

## Social publishing handoff

Weather delays and game-resumption events are retained for Phase 6.9 Social Publishing. Emergency-warning posts will not contain sponsor branding. Ordinary postponement, rescheduling, or resumption posts may use approved school and CSRN branding after operator review.

## Following stage

Phase 6.6 performs two complete operational rehearsals, including forced weather-data staleness, alert approval, weather-delay, lightning-timer, caption, OBS, mixer, network, application-restart, and recovery drills.
