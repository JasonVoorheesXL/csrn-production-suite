# Football Release-Candidate Test Process

## Gate A — Source and data integrity

- Confirm running version and exact Git commit.
- Confirm Drive and Git working tree match.
- Back up `Data` and export a support bundle.
- Verify fictional records are marked `CSRN-FICTIONAL-TEST`.
- Verify each fictional team has 22 active players and illustrated avatars.
- Verify school identity, colors, logo, address, and attached venue.
- Verify **New Broadcast** auto-populates the home school's venue.
- Verify both fictional sponsors and their status.

Exit: no missing identity data, duplicate jersey warnings, broken image paths, or wrong venue linkage.

## Gate B — Static application audit

- Run all automated tests.
- Compile all Python modules.
- Syntax-check all page JavaScript.
- Run route inventory and broken-link scan.
- Verify navigation from every standalone page.
- Verify data writes are atomic and snapshots are created.
- Verify startup, clean shutdown, and unclean-shutdown detection.

Exit: automated suite passes; no severity-1 or severity-2 defects.

## Gate C — Software-only full-game rehearsal 1

- Check OBS in Command Center, then run Release Readiness.
- Select **New Broadcast**.
- Verify venue auto-population.
- Load Northwood vs. Pine Valley.
- Exercise clock, quarter, possession, down/distance, scoring, conversions, turnover, undo, corrections, and halftime.
- Enter team and player statistics.
- Create and discard social drafts; prepare X package; do not publish.
- Select Player of the Game and article sponsor.
- Mark final; generate, edit, approve, and export recap/article.
- Archive and reopen the completed broadcast.
- Terminate/restart during Q3 and verify full recovery.

Exit: game completes with correct score and preserved state.

## Gate D — Defect correction and regression

- Classify each defect as blocking or advisory.
- Correct blocking defects.
- Add regression tests for every corrected defect.
- Reset the fictional broadcast while preserving fixture data.
- Repeat affected workflows.

Exit: no open blocking software defects.

## Gate E — Software-only full-game rehearsal 2

Repeat Gate C with operator roles exchanged or alternate workflow choices. Include wrong-team prevention, stale-draft handling, restart, and archive review.

Exit: two software rehearsals complete without score corruption or data loss.

## Gate F — Hardware and OBS commissioning

Deferred until software-only gates pass:

- configure P4next;
- verify isolated channels and multitrack recording;
- verify OBS audio and local recording;
- verify phone/browser control;
- test network loss and local-recording response.

## Gate G — Formal Phase 6.6 rehearsals

Run two full operator-recorded rehearsals satisfying `PHASE_6_6_OPERATIONAL_REHEARSAL_AND_RELEASE_FREEZE.md`, including all required recovery drills. Freeze only the exact tested Git commit.
