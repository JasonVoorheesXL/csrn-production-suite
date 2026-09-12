# Round 27 — Access model & sport context

Login-screen sport selection, a switchable in-app sport *context*, and
sport-scoped rosters / sponsors. Branch
`round27-access-model-sport-context-20260906`, off production tip
`64ed45a`. Nothing merges to production until after the Friday game.

## The model

| Concept | Where | Notes |
| --- | --- | --- |
| `SPORT_FAMILIES` | `sport_families.py` | `football, basketball, baseball, softball, soccer` — one login icon each, licensable. |
| `ENGINE_READY` | `sport_families.py` | `football` + `canadian_football` only. A broadcast engine exists for these; every other family/context is gated "coming soon" regardless of licence. |
| `GATEWAY` = `"all_others"` | `sport_families.py` | A sixth login tile. **Not a context.** Opens the secondary list. `POST /api/sport-context {sport:"all_others"}` → 400. |
| `OTHER_CONTEXTS` | `sport_families.py` | Behind the gateway: `canadian_football` (real engine), `hockey, lacrosse, tennis, swimming` (coming soon). |

### Engine-readiness vs licensing are separate axes

`family_sport_options()` reports `licensed` (paid for), `engine_ready`
(built), and `available` (both). The login tiles, the top-nav switcher and
`POST /api/sport-context` all treat a **licensed-but-engineless** family
differently from an **unlicensed** one:

| State | Login tile | Switcher | `POST /api/sport-context` |
| --- | --- | --- | --- |
| licensed + engine (football) | selectable, green on pick | enabled | 200 |
| licensed, no engine (e.g. basketball if paid) | `SOON` badge, "engine ships in a future update" | disabled "(soon)" | `400 SPORT_ENGINE_NOT_READY` |
| not licensed, no engine | lock badge, "get licensed" | omitted | `400 SPORT_COMING_SOON` |
| engine-ready, not licensed (football unpaid) | lock badge | omitted | `403 SPORT_NOT_LICENSED` |
| `sport_context` | Flask session | The value the operator is in: a family, or `canadian_football`, or `""`. Set at login from the sport picked, changeable via the top-nav switcher with **no re-PIN**. |
| `sport_scope` | derived | `base_family(sport_context)` — the roster/sponsor pool + license key. `canadian_football` → `football`. |

### Canadian football

`canadian_football` is its own context. It is **not** a second engine and
**not** a separate license. It resolves to the football base family for
licensing and scoping; the intent is that entering it loads the same
Round 26 football module pre-scoped toward Canadian rulesets. See open
item 2 — the module-dispatch half of that is not built in Round 27.

## Invariants (from the owner's Round 27 correction)

1. **Licensing is merged.** One `football` license entry entitles both
   `football` and `canadian_football`. Enforced by `base_family()`:
   `context_is_licensed()` and `resolve_licensed_families()` both collapse
   `canadian_football` → `football`. Tests:
   `test_one_football_license_covers_both_football_contexts`,
   `test_canadian_football_context_is_covered_by_the_football_license`,
   `test_login_accepts_canadian_football_under_the_football_license`.
2. **Roster / sponsor scoping is shared.** Rosters and sponsors are tagged
   `football` regardless of American vs Canadian (the ruleset is a
   per-broadcast choice — Round 26). `sport_scope` for a `canadian_football`
   context is `football`, so `RosterService.list_rosters("canadian_football")`
   and `SponsorService.list_payload("canadian_football")` return the
   football pool, never empty. Tests:
   `test_list_rosters_canadian_football_scope_shows_football_rosters`,
   `test_list_payload_canadian_football_scope_matches_football_sponsors`,
   plus the `/api/rosters` + `/api/sponsors` route tests.

## Byte-identical single-sport path

A football-only install with no sport picked sends no usable `sport` at
login, so `session["sport_context"]` is unset, `sport_scope` is `""`, and
every list route is unfiltered — exactly as before Round 27. Every
`sport`-aware service method has an `""` default that is a no-op.

## Commit map

| # | Scope |
| --- | --- |
| 1 | `sport_families.py` vocabulary + `EntitlementService.licensed_sport_families()` |
| 2 | `/api/session-context` + `/api/sport-context`; `/api/security-status` extras; login/setup-pin stamp the context |
| 3 | Login-screen sport picker |
| 4 | **Design correction 1/2** — All Others is a gateway; `canadian_football` context; `base_family` |
| 5 | **Design correction 2/2** — All Others gateway secondary-list UI |
| 6 | Top-nav sport-context switcher (`#sportSwitcher`) |
| 7 | `/api/rosters` scoped by `sport_scope` |
| 8 | Sponsor records carry a `sport` family (`clean_record`) |
| 9 | `_normalize_sponsors` — backfill legacy sponsors |
| 10 | `/api/sponsors` scoped by `sport_scope`; sponsor-editor `Sport` field |
| 11 | This document |
| 12 | Gate `basketball / baseball / softball / soccer` as coming-soon (no engine yet); licensed-vs-unlicensed messaging split; `SPORT_ENGINE_NOT_READY` |

Full suite through commit 10: **2582 passed, 2 failed**. The 2 failures
(`tests/test_state_mirror_throttle.py`) require a Google-Drive-backed
checkout path and fail identically in the Round 22 / Round 26 worktree —
they pre-date Round 27 and are not a regression.

## Tracked TODO — trunk, post-Friday — DONE (Post-Friday Merge Weekend, Phase 2 item 1)

**Jurisdiction-picker CA/US filter (deferred follow-up 1).** Landed once
Round 26, Round 27 and Phase C were all merged to production: scopes the
Round 26 country/region/association picker (`#rulesetJurisdiction` /
`loadRulesetOptions()` / `available_rulesets()`) by the active
`sport_context`, exactly as specified below. See
`tests/test_jurisdiction_picker_sport_scoped.py`.

Original spec, for the record:

* `sport_context == "canadian_football"` → CA jurisdictions only
  (`country == "CA"`); operator still picks the association
  (`ca-cjfl-ofc` vs generic `ca-base`), just from a CA-only list.
* `sport_context == "football"` → US jurisdictions only.
* unset / other → unfiltered (today's behaviour).

This is a filter on the existing Round 26 picker, **not** a new picker or a
second engine. It could not be done inside Round 27 because Round 27
branched off `64ed45a`, which predates the Round 26 picker; the owner
chose to defer rather than rebase/entangle the branches. `is_engine_ready`
already treats `canadian_football` as loading the football module — this
TODO is only the jurisdiction pre-scoping half.

## Open items / assumptions — needs owner confirmation

1. **Coming-soon sport list is a placeholder.** `hockey, lacrosse,
   tennis, swimming` behind the gateway are a guess at what CSRN will
   build next. Adjust `OTHER_CONTEXTS` / `LABELS` in `sport_families.py`
   and `OTHER_GLYPH` in `index.html` freely — the login list and the
   top-nav switcher are both API-driven from `other_sport_options()`.

2. **`canadian_football` jurisdiction pre-scoping — DONE** (see "Tracked
   TODO" above). Round 27 makes `canadian_football` a valid context whose
   scope is `football` and whose licence is the football entry, and
   `is_engine_ready` treats it as the football module. It now also filters
   the Round 26 jurisdiction picker to CA-only. Being in `canadian_football`
   context behaves like `football` apart from the
   label.

3. **Scoping applies to every `/api/rosters` and `/api/sponsors`
   consumer**, not just the management screens — play entry, automation,
   and player-graphics fetches get the scoped list too. With no
   `sport_context` set this is identical to today. A multi-sport operator
   who sets the wrong context (e.g. `basketball` while running a football
   broadcast) would see a short roster list on the live-entry path. The
   default (unset) is safe; flag if you want the live paths to always
   bypass scoping.

4. **Sponsor migration on a multi-sport install.** `_normalize_sponsors`
   backfills *every* untagged legacy sponsor with the one install-default
   family (`identity broadcast_defaults.sport`, else `football`). On the
   current single-sport deployment that is correct. A hypothetical
   multi-sport install with untagged sponsors would need the odd ones
   re-tagged by hand. This matches "default to the install's current/only
   sport."

5. **New-sponsor default.** The sponsor editor's `Sport` field defaults to
   the operator's current context scope, not "All sports". Assumption: a
   sponsor added while working football is a football sponsor. The
   operator can pick "All sports" for a cross-sport sponsor.

6. **`localStorage["csrn_last_sport"]`** remembers the last sport picked
   on the login screen (per browser). On a shared operator machine the
   next person sees the previous person's sport pre-highlighted; they can
   change it before unlocking. Session `sport_context` is the source of
   truth once logged in.

7. ~~Licensed non-football families have no runtime yet.~~ **Resolved
   (commit 12).** `basketball / baseball / softball / soccer` are gated
   "coming soon" — not selectable — because there's no engine, with copy
   that distinguishes licensed-but-not-ready from unlicensed. When an
   engine ships for one, add it to `ENGINE_READY` in `sport_families.py`
   and it becomes selectable automatically.

8. **Icon glyphs** (`🏈 🏀 ⚾ 🥎 ⚽ 🏅` and `🍁 🏒 🥍 🎾 🏊`) are
   cosmetic placeholders — swap for real icons from the CSRN icon library
   when convenient.
