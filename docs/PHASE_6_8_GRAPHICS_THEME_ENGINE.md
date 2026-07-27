# Phase 6.8 — Graphics Theme Engine

Phase 6.8 provides one reusable graphics engine with eight original genre-inspired presets. It does not create separate scorebug, caption, weather, or social implementations for each style.

## Included presets

1. Classic 1980s Broadcast
2. Early Cable Sports
3. Modern Network
4. Minimal Radio
5. Heritage Press Box
6. Friday Night Stadium
7. Digital Neon
8. Collegiate Traditional

The presets are original design directions. They do not reproduce the layout, marks, typography, animations, or protected trade dress of a television network.

## Shared theme coverage

The generated stylesheet controls:

- scorebug structure and center module;
- team panels and scores;
- lower thirds;
- player and personnel cards;
- sponsor bars;
- event ticker;
- caption cards and speaker labels;
- weather bug, advisory, and delay presentation;
- typography, radius, borders, textures, shadows, and motion;
- social-card tokens consumed by Phase 6.9.

Team identities retain their own home and visitor colors. The neutral broadcast chrome uses the organization colors unless the operator applies an allowlisted override.

## Controlled overrides

Operators may change only:

- primary, secondary, and accent colors;
- an allowlisted typography family;
- corner radius;
- panel opacity;
- texture intensity;
- motion scale.

Raw CSS, arbitrary font URLs, JavaScript, file paths, and remote assets are not accepted as theme overrides.

## Theme variants

A customer may save up to 24 named variants, such as `Home Broadcast`, `Playoffs`, or `Senior Night`. A variant stores a preset identifier plus controlled overrides. It does not duplicate graphics code.

## Season lock

The active theme can be locked for a season using the exact confirmation:

```text
LOCK SEASON THEME
```

Unlocking requires:

```text
UNLOCK SEASON THEME
```

Changing a locked design requires:

```text
CHANGE LOCKED SEASON THEME
```

The lock is intended to prevent accidental game-day style changes. It is not a licensing control.

## Theme manager

Authenticated operators can open:

```text
http://127.0.0.1:5050/themes
```

The manager provides the catalog, previews, activation, controlled overrides, variants, and season locking.

## Public overlay resources

Browser sources load the current generated stylesheet from:

```text
http://127.0.0.1:5050/themes/current.css
```

Read-only resolved theme state is available at:

```text
http://127.0.0.1:5050/api/themes/public-state
```

The stylesheet is served with no-store caching so OBS receives theme changes without requiring a new browser-source URL.

## Social publishing handoff

Phase 6.9 will use the same resolved theme tokens for platform-sized social cards. This keeps touchdown, turnover, halftime, final-score, sponsor, weather-delay, and game-resumption posts visually consistent with the live broadcast.
