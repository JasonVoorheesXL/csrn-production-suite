# CSRN Project Audit — 2026-07-29

## Executive finding

The Google Drive working tree is the operational source of truth at version `1.13.0-alpha.8e`. The GitHub default branch remains the original `v1.5.0-alpha` frozen baseline and contains only the initial commit. GitHub is therefore not currently a trustworthy recovery, review, or release source.

## Current product stage

The correct stage is integration audit and controlled operational testing.

The software has progressed beyond the planned order by implementing commercial-facing Phase 6.8, 6.9, and 6.10 work before completing the Phase 6.6 operational rehearsal and release-freeze gate. That does not invalidate the later work, but it means the next work must return to release evidence, defect discovery, and repository alignment rather than adding broad features.

## Confirmed current capabilities from Drive

- theme engine foundation;
- social publishing with manual-only X workflow;
- grounded recap and deterministic article generation;
- grouped cross-page navigation;
- football release-readiness export;
- active OBS/overlay checks;
- fictional full-game fixture.

## Confirmed roadmap removals

- no dedicated Chromebook/PWA product track;
- no automated X publishing;
- no hosted AI;
- no local AI.

Chromebooks remain ordinary browser clients, like phones and tablets.

## Governance defects

1. GitHub is stale and cannot reproduce the installed Drive build.
2. `ROADMAP.md` and both GitHub changelogs are materially obsolete.
3. Drive contains repeated copies of `BUILD_JOURNAL.md`, roadmap files, package payloads, and installer artifacts.
4. Version identity is split between application version, build ID, and roadmap phase labels.
5. The formal Phase 6.6 process requires a tested Git commit, but the current installed build is not represented by one.

## Required correction path

1. Preserve the current Drive working tree.
2. Create a full Git working copy from the exact installed `alpha.8e` files.
3. Commit that tree to a release-candidate alignment branch.
4. Run automated tests from that commit.
5. Run software-only integration rehearsal.
6. Correct blocking defects and repeat.
7. Configure P4next and perform hardware/OBS rehearsal.
8. Complete two operator-recorded full rehearsals and recovery drills.
9. Freeze the exact tested commit.
10. Only then proceed to commercial installer/licensing hardening.
