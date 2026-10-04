# MaxPreps Stat Export (Football)

Branch `maxpreps-export-20261004`, off `main` at `d240082`. Scoped to football
only this round. **Not merged** -- report for review, per the usual
convention.

## Why

Jason wants an easy way to get CSRN's game stats onto MaxPreps.com. MaxPreps
has no public API for stat partners. The only real mechanism is a human
uploading a file through MaxPreps **Team Admin -> Import Stats**, in a format
MaxPreps documents itself. This round builds the file; it does not touch
MaxPreps' site, register CSRN as anything, or create any MaxPreps account.

## Step 1: the actual schema (confirmed live, not guessed)

Fetched directly from `https://www.maxpreps.com/utility/stat_import/field_specs.aspx`
via a real browser session (WebFetch's static HTML fetch does not execute the
page's sport/gender dropdown-and-postback, so the football field list has to
be read after actually selecting Sport=Football, Gender=Boys, and submitting
the page's own GO button -- a one-time documentation lookup, not scraping at
scale).

### Partner registration is NOT required

The page documents two sample files side by side. The **accredited** sample
begins with a 32-character Stat Supplier ID line:

```
12345678-1234-1234-123456789012
Jersey|AtBats|BaseOnBalls|Doubles|HitByPitch|Hits
```

The page's own **"Sample Unaccredited Import File"** has no ID line at all --
it starts directly with the field-declaration line:

```
Jersey|AtBats|BaseOnBalls|Doubles|HitByPitch|Hits
12|3|2|1|0|2
10|2|0|1|0|2
15|2|0|0|0|0
```

This directly confirms the user's own pre-research: a team does **not** need
to be a registered "Stat Import Partner" to produce a valid, importable file.
CSRN's exporter below writes the unaccredited form -- no ID line, ever.

### File format, quoted verbatim

> "All data fields are PIPE ( | ) delimited."

> "Do not include zeros unless the stat is actually zero (i.e., interceptions,
> turnovers, errors)."

> "Note: Imports will not overwrite existing values if the field is not
> declared in the second line of the import (allows multiple imports for the
> same game; i.e., offensive & defensive imports)."

> "*NOTE: Jersey is a required stat field" -- this is the **only** field the
> page documents as required, for any sport.

> "Jersey numbers must match exactly (i.e., '02' is not the same as '2')."

> "Field names must match MaxPreps field names exactly."

File must be saved with a `.txt` extension; the filename itself cannot contain
quotes or parentheses.

### Why one file per team, not one per game

MaxPreps' only upload path is each team's own **Team Admin** login clicking
**Import Stats** -- there is no multi-team upload and no "Team" column
anywhere in the documented schema. The receiving account is what scopes a
file to one side of the game. So CSRN exports **one file per team**, not a
combined file; the Game Manager card below gets two buttons, one per side.

### `partners.aspx` cross-check

Checked the partner directory (`https://www.maxpreps.com/utility/stat_import/partners.aspx`)
specifically to see whether the format above is genuinely universal or has
partner-specific sub-variants. It is just a per-sport directory of
third-party apps (Circle W Sports, DakStats Football, Hudl, StatBroadcast's
"GameDay Preps", TurboStats, etc.), each linking out to its own vendor
support site. There is **one universal format per sport** -- registration/
listing in that directory is a separate, optional visibility step, unrelated
to the file format itself. (It does not change the "no registration needed to
produce a valid file" finding above.)

### Football field list (Boys Football -- the only gender option for football)

Quoted from the live page, grouped exactly as MaxPreps groups them:

- **Offensive** -- Rushing: `RushingNum`, `RushingYards`, `RushingLong`.
  Receiving: `ReceivingNum`, `ReceivingYards`, `ReceivingLong`. Passing:
  `PassingComp`, `PassingAtt`, `PassingInt`, `PassingYards`, `PassingTD`,
  `PassingLong`. Fumbles: `OffensiveFumbles`, `OffensiveFumblesLost`. O Line:
  `PancakeBlocks`.
- **Defensive** -- Tackles: `Tackles`, `Assists`, `TotalTackles`,
  `TacklesForLoss`. Sacks: `Sacks`, `SacksYardsLost`, `QBHurries`. Pass
  Defense: `INTs`, `INTYards`, `PassesDefensed`. Blocks: `BlockedPunts`,
  `BlockedFG`. Fumbles: `FumbleRecoveries`, `FumbleRecoveryYards`,
  `CausedFumbles`.
- **Special Teams** -- Punt Returns: `PuntReturnNum`, `PuntReturnYards`,
  `PuntReturnLong`, `PuntReturnFairCatches`. Kickoff Returns:
  `KickoffReturnNum`, `KickoffReturnYards`, `KickoffReturnLong`. Total
  Returns: `TotalReturnYards`. Punts: `PuntNum`, `PuntYards`, `PuntLong`,
  `PuntInside20`. Kickoffs: `KickoffNum`, `KickoffYards`, `KickoffLong`,
  `KickoffTouchbacks`.
- **Scoring** -- Touchdowns: `RushingTDNum`, `ReceivingTDNum`,
  `FumbleReturnedTDNum`, `IntReturnedTDNum`, `PuntReturnedTDNum`,
  `KickoffReturnedTDNum`, `TotalTDNum`. PAT Kicks: `PATKickingMade`,
  `PATKickingAtt`, `PATKickingPoints`. Conversions: `PATRushingNum`,
  `PATReceivingNum`, `TotalConversionPoints`. Field Goals: `FGMade`,
  `FGAttempted`, `FGLong`. Sfts: `Safeties`. Pts: `TotalPoints`.

There is **no name field anywhere in the schema** -- MaxPreps identifies a
player by jersey number alone and matches it against the roster the team
already maintains on MaxPreps.

## Step 2: field-by-field mapping

Source of truth: `statistics_service.py`'s `StatisticsService.report()`, the
sole owner of CSRN's derived game statistics (confirmed by grepping for
"Individual Production"/"Team Summary"/"Play Register"/"Scoring Plays" --
only one hit in the codebase). Its `_player_row()` is the exact per-athlete
shape read below. No new stat computation was added anywhere -- the exporter
only reads and reshapes values `report()` already produces.

### Exported (CSRN tracks the exact stat MaxPreps asks for)

| MaxPreps field | CSRN source | Notes |
|---|---|---|
| `Jersey` | `number` | The only MaxPreps-required field. |
| `RushingNum` | `rushing_attempts` | |
| `RushingYards` | `rushing_yards` | |
| `ReceivingNum` | `receptions` | |
| `ReceivingYards` | `receiving_yards` | |
| `PassingComp` | `completions` | |
| `PassingAtt` | `pass_attempts` | |
| `PassingInt` | `interceptions_thrown` | |
| `PassingYards` | `passing_yards` | |
| `PassingTD` | `passing_touchdowns` | |
| `OffensiveFumbles` | `fumbles` | |
| `OffensiveFumblesLost` | `fumbles_lost` | |
| `Sacks` | `sacks` | Defensive sacks made. |
| `INTs` | `defensive_interceptions` | |
| `FumbleRecoveries` | `fumble_recoveries` | Opponent-fumble recoveries only -- confirmed this field excludes a team's own-fumble recoveries (that's the separate `own_fumble_recoveries`, which MaxPreps has no field for anyway). |
| `PuntReturnNum` | `punt_returns` | |
| `PuntReturnYards` | `punt_return_yards` | |
| `KickoffReturnNum` | `kickoff_returns` | |
| `KickoffReturnYards` | `kickoff_return_yards` | |
| `TotalReturnYards` | `kickoff_return_yards + punt_return_yards` | Computed; MaxPreps documents this as one combined column. |
| `PuntNum` | `punts` | |
| `KickoffNum` | `kickoffs` | |
| `RushingTDNum` | `rushing_touchdowns` | |
| `ReceivingTDNum` | `receiving_touchdowns` | |
| `TotalTDNum` | `touchdowns` | Verified against `report()`'s own increment logic: this field is bumped for a rushing, receiving, or return touchdown the player actually scored, and deliberately *not* for a TD pass thrown (`passing_touchdowns` is separate) -- matches MaxPreps' "total touchdowns scored" semantics. |
| `PATKickingMade` | `extra_points` | |
| `PATKickingAtt` | `extra_point_attempts` | |
| `PATKickingPoints` | `extra_points` | Computed; every made PAT kick is worth exactly 1 point. |
| `TotalConversionPoints` | `two_point_conversions * 2` | Computed; every successful 2-point try is worth exactly 2 points. |
| `FGMade` | `field_goals` | |
| `FGAttempted` | `field_goal_attempts` | |
| `TotalPoints` | `points` | |

That is 28 of MaxPreps' documented football fields (27 direct + 3 computed,
minus overlap), plus `Jersey`.

### Not tracked by CSRN -- flagged, never guessed or placeholder-filled

Per instruction, no MaxPreps field below is invented a value. These columns
are simply never declared in the exported file, which per MaxPreps' own
"Imports will not overwrite existing values if the field is not declared"
rule means CSRN's export is silent on them rather than zeroing them out.

- **No tackle tracking exists at all.** `Tackles`, `Assists`, `TotalTackles`,
  `TacklesForLoss` -- confirmed by grepping the whole codebase for "tackle"
  outside tests/.venv: the only hit is a caption-trigger string
  (`caption_worker.py`), not a stat field. CSRN has zero infrastructure for
  this.
- **`SacksYardsLost`, `QBHurries`** -- sacks are tracked as a count only
  (`sacks`), never with yardage lost or a separate hurry stat.
- **`INTYards`, `FumbleRecoveryYards`** -- CSRN has a single
  `turnover_return_yards` field that commingles interception-return yards
  *and* fumble-recovery-return yards on the same defender with no way to
  split them back out. Exporting either MaxPreps column from it would silently
  misattribute yardage between the two stat types, so neither is exported.
- **`PassesDefensed`** -- no distinct "broken up, not intercepted" stat
  exists; CSRN only records an interception as a defensive event.
- **`BlockedPunts`, `BlockedFG`** -- `blocked` exists only as free-text inside
  a play's `result`/`description` string. It is never aggregated into any
  per-player counter, never attributed to the blocking player, and never
  split punt-vs-field-goal.
- **`CausedFumbles`** -- CSRN tracks who lost a fumble (`fumbles_lost`, on the
  offensive player) and who recovered it (`fumble_recoveries`, on the
  defender), but not who *forced* it, which can be a third player entirely.
- **`PancakeBlocks`** -- no offensive-line blocking stats of any kind exist.
- **`FumbleReturnedTDNum`, `IntReturnedTDNum`, `PuntReturnedTDNum`,
  `KickoffReturnedTDNum`** -- confirmed by reading `report()`'s scoring loop
  directly: a turnover-return touchdown (interception or fumble return) only
  ever increments the generic `touchdowns` field on the defender, with no
  subtype breakdown; and `return_touchdowns` (used for kickoff/punt returns)
  itself commingles kickoff-return and punt-return touchdowns into one
  field. Only the clean aggregate (`TotalTDNum`, above) is exportable; none
  of these four subtypes can be split back out without guessing.
- **`PATRushingNum`, `PATReceivingNum`** -- `two_point_conversions` is a
  single counter; CSRN does not record whether a given 2-point try was
  converted by a run or a catch.
- **`PuntYards`, `PuntLong`, `PuntInside20`, `KickoffYards`, `KickoffLong`,
  `KickoffTouchbacks`** -- CSRN tracks punt/kickoff *counts* per kicker
  (`punts`, `kickoffs`) but never the kick's own distance, inside-the-20
  placement, or touchback outcome as a per-kicker aggregate. (A touchback is
  recorded as a play outcome in `rules_service.py`, but never rolled up into
  a per-kicker stat.)
- **`RushingLong`, `ReceivingLong`, `PassingLong`, `PuntReturnLong`,
  `KickoffReturnLong`, `FGLong`** -- CSRN's aggregates have no "longest single
  play" tracking in any category. These are theoretically derivable later by
  scanning the per-play `play_register` data for each player's single best
  play, but that is new derivation logic this round deliberately does not
  build (scope: "No new stat computation -- this is a serializer"; the brief
  also said to flag rather than invent, and none of these are MaxPreps-
  required fields).
- **`PuntReturnFairCatches`** -- fair catches are detected per-play
  (`"fair catch" in result`) to decide whether a return stat applies at all,
  but never counted as their own per-player stat.
- **`Safeties`** -- no safety tracking exists anywhere in
  `statistics_service.py` (grepped directly; zero hits).

None of the omitted fields above are MaxPreps-required -- `Jersey` is the
only required column, and it is always populated.

## Step 3: the exporter

- `maxpreps_export_service.py` (new) -- `MaxPrepsExportService.generate(broadcast_id, team)`.
  Reads a broadcast's game state the same way `social_media_preview_service.py`
  already does (`_resolve_game_state`: live state if it matches this
  broadcast, else the broadcast's own `live_state` mirror, else
  `final_state_archive` -- so this works for the currently-live game *and*
  for an older completed/archived one), runs it through the existing
  `StatisticsService.report()`, and writes the mapping above as pipe-delimited
  text. No new stat computation anywhere in this file -- every value is
  either a direct field read or one of the three documented sums/products
  above.
- `routes/broadcast_routes.py` -- new `GET /api/broadcasts/<id>/maxpreps-export.txt?team=home|visitor`,
  same `@require_auth` + `Content-Disposition: attachment` pattern as the
  existing broadcaster-print-sheet/social-preview/-- routes in this file.
  Missing/invalid `team` returns `400 INVALID_TEAM` with a message explaining
  why (one file per team, not per game); an unknown broadcast returns `404`.
- `app.py` -- `get_maxpreps_export_service()` singleton, wired into
  `BroadcastRoutesDependencies` next to the existing broadcaster-print and
  social-preview service getters.
- `templates/index.html` -- two new Game Manager card buttons, **"MaxPreps
  Export (Home)"** and **"MaxPreps Export (Visitor)"**, shown only when
  `sport === 'Football'` (this round is football-only). Each triggers a real
  browser download of the generated `.txt` file via a plain anchor click
  (`downloadMaxPrepsExport(id, team)`) -- no new overlay UI, since this is a
  file download, not something OBS or a viewer ever sees.

## Verification

There is no MaxPreps account to test-upload against, so the bar for this
round is a manual field-by-field cross-check against the documented schema
above, done against a real generated file:

- `tests/test_maxpreps_export_service.py` builds a realistic seeded game
  (rushing/receiving/passing touchdowns, an interception, a sack, a punt
  return, a kickoff return, a field goal, an extra point, a two-point
  conversion) through the real `StatisticsService` + `MaxPrepsExportService`,
  and asserts the generated file's header line matches MaxPreps' field names
  exactly, every hand-computed stat value is correct, the unaccredited format
  (no ID line) is used, filenames carry no quotes/parentheses and end in
  `.txt`, and the `final_state_archive` fallback path works for an archived
  (not currently live) broadcast.
- `tests/test_maxpreps_export_route.py` hits the real Flask route (through
  `app.app.test_client()`, not a stub) with that same seeded game, proving
  the route/DI wiring in `app.py` and `routes/broadcast_routes.py` actually
  works end-to-end: a 200 with the exact pipe-delimited body and a real
  `Content-Disposition: attachment` header, a 400 for a missing/invalid
  `team` param, a 404 for an unknown broadcast, and a 401 when unauthenticated.
- The generated output for both teams was printed and read by hand against
  the quoted schema above -- header line, column order, and the "no ID line"
  unaccredited format all match. Example (home team, from the test fixture):

  ```
  Jersey|RushingNum|RushingYards|ReceivingNum|ReceivingYards|PassingComp|PassingAtt|PassingInt|PassingYards|PassingTD|OffensiveFumbles|OffensiveFumblesLost|Sacks|INTs|FumbleRecoveries|PuntReturnNum|PuntReturnYards|KickoffReturnNum|KickoffReturnYards|TotalReturnYards|PuntNum|KickoffNum|RushingTDNum|ReceivingTDNum|TotalTDNum|PATKickingMade|PATKickingAtt|PATKickingPoints|TotalConversionPoints|FGMade|FGAttempted|TotalPoints
  22|2|10|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|0|1|0|1|0|0|0|2|0|0|8
  ```

  I'm confident in every exported column's mapping per the table above. The
  one thing I can't independently verify without a real MaxPreps account is
  whether MaxPreps' importer is strict about column order within the
  declared header (the spec says only "Field names must match... exactly"
  and that Jersey must be first; it does not say the other columns must
  follow MaxPreps' own display order) -- if the import ever rejects this
  file, column order, not field names or values, would be the first thing to
  check.

### Real-upload findings (2026-10-04, post-merge)

Jason test-uploaded a real generated file (Itawamba AHS vs Caledonia,
`FB-2026-4A-W01-001`) through MaxPreps Team Admin's actual Import Stats
screen -- something this round's own verification explicitly couldn't do,
with no MaxPreps account to test against. It was rejected twice, for two
different reasons found in sequence:

**1. Line endings (secondary, fixed first, didn't fully explain the symptom).**
The exporter originally joined rows with a bare `\n`. MaxPreps' import
parser is a classic Windows/ASP.NET upload tool and most likely splits rows
on `\r\n` -- confirmed by pulling a real, independently-produced sample file
from a third-party MaxPreps-compatible stat program (Statman,
`myweb.fsu.edu/abrady/Statman/Sample/`), whose actual output uses `\r\n`
throughout. Fixed by writing `\r\n` between rows. Good practice regardless
of the finding below, but re-uploading after only this fix still failed.

**2. The real root cause: a stale "live" state masked the real play data.**
Jason reported the re-exported file still had no stats in it. Reading the
actual production data directly (`Data/Broadcasts/FB-2026-4A-W01-001.json`
and the live authority `state.json`) showed why: `GameOperationsService.
end_game()` clears `events`/`plays` from the live authority state once it
has confirmed a full `final_state_archive` was written, but leaves
`broadcast_id` and `status` (`"completed"`) in place. `_resolve_game_state`
(copied from `social_media_preview_service.py`'s own helper) matched the
live state purely by `broadcast_id`, so it kept returning that now-empty
live state for this finished game instead of falling through to the
archive that actually has all 117 real plays -- producing a technically
valid file with a correct header and **zero data rows**, which is exactly
what MaxPreps' "Insufficient data... needs at least header and one data
row" message was honestly describing. `StatisticsService.report()` itself
was never the problem -- run directly against the real archived state for
this game it produces 24 players with correct, real stats.

Fixed by only trusting the live state when it is both this broadcast *and*
still actually carries events/plays; a `broadcast_id` match on an otherwise
empty live state now falls through to the richer `live_state` mirror, then
the archive, exactly as it should for a completed game. Added a regression
test (`test_falls_back_to_archive_when_the_live_state_matches_by_id_but_was_cleared_post_game`)
reproducing this exact shape. Re-verified directly against the real
Itawamba broadcast data (not a synthetic fixture): both the home and
visitor exports now produce a correct header plus real player rows (12 and
13 players respectively, both with real jersey numbers and stats).

`social_media_preview_service.py`'s own `_resolve_game_state` has the same
`broadcast_id`-only matching logic. It likely doesn't manifest the same way
there (its score fields mostly come from frozen `final_*_score` broadcast
fields, not from `events`/`plays`), but it's the same latent pattern and
worth a look in a future round rather than assuming it's fine by inspection
alone.

**3. Caledonia vs Amory (`FB-2026-OPEN-W00-001`) -- genuine data gap, not a
bug.** Jason reported the same "no stats" symptom for a second game. This
one is different: its `final_state_archive`'s own `history` shows the
broadcast was created with `broadcast_created: True`, `quarter: 4`, and the
final score (27-7) already set -- it was entered as a final-score-only
record and was never live-tracked play-by-play. `events`/`plays` are
genuinely `[]` everywhere (live state, `live_state` mirror, and the
archive), so `StatisticsService.report()` correctly returns 0 players and
all-zero team stats (only `score` is populated). There is no bug to fix
here -- CSRN never recorded individual plays for this game, so there is
nothing for any exporter to serialize.

What *was* fixable: the exporter silently produced the same MaxPreps-
rejected header-only file for this case as for the real bug above, with no
way to tell the two apart. Added a dedicated `NO_PLAYER_DATA` result
(`generate()` now checks for an empty player list before writing any
content) with a message naming the team and explaining a final score alone
isn't enough; the route returns `422` with that message instead of a `200`
download, and the Game Manager button now fetches first and shows an alert
with the real message rather than blindly downloading whatever the
response body is.

Football only, per the brief ("CSRN's most mature stats engine and Jason's
actual priority"). The `partners.aspx` check confirms MaxPreps' format is
cleanly one-schema-per-sport, and the mapping pattern here (lean on
`StatisticsService.report()`'s existing per-player rows, flag anything not
tracked) should carry over easily to baseball/basketball later -- not built
this round.

Partner registration (`stat_import/register.aspx`) remains explicitly out of
scope, as instructed -- this exporter only ever produces the unaccredited
file format and never touches MaxPreps' site.
