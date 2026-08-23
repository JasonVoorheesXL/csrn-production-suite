# Phase 6.10 — Grounded Game Recap Engine

## Purpose

Phase 6.10 creates deterministic, reviewable game recaps from the active CSRN broadcast record. The engine is not permitted to fill gaps with likely outcomes, inferred statistics, estimated yardage, unrecorded player attribution, or assumed weather conditions.

## Grounding boundary

The generator may use only:

- the recorded final score and team identities;
- non-undone game events;
- non-undone play records;
- a recorded halftime score when present;
- statistician-enabled team and player statistics when the required fields are actually present.

Missing information is listed in the grounding report and omitted from the recap. The report retains a source hash, event IDs, play IDs, statistic paths, and operator-edited fields.

## Generated content

The foundation can generate:

- a final-score headline and lead;
- recorded scoring sequence;
- recorded lead changes derived from saved after-scores;
- recorded turnovers;
- recorded weather delays, emergencies, and resumptions;
- halftime score when present;
- available team statistics and recorded player leaders;
- a concise final-score social summary.

## Review and approval

Each recap begins in `DRAFT` status. The operator may edit the headline, lead, body, closing, and social summary. Editing resets approval and records the changed fields as operator-authored. Approval requires the exact phrase `APPROVE GROUNDED RECAP`.

A recap becomes stale when the current recorded game data no longer matches its source hash. Stale recaps cannot be approved; they must be regenerated.

## Social handoff

An approved recap may create a linked final-score social draft. That social draft remains subject to the Phase 6.9 approval and platform rules:

- Facebook Page may use approved automatic publishing when configured;
- X remains assisted-manual only, with generated text and graphic but no OAuth, API, or automatic queue.

## Persistence

Recaps and audit records are stored in `Data/Recaps/recaps.json`. Normal game-day backup and migration behavior preserves the complete `Data` directory.
