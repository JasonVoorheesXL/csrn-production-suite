# CSRN Production Suite — Project Bible

Document role: Living source of truth, continuity record, and new-chat handoff  
Product: CSRN Production Suite  
Primary release target: Finished Windows-hosted football broadcasting product  
Owner: Jason Chrest  
Last audited: 2026-07-30  
Current status: **BLOCKED — PR #88 CI remediation must pass on Windows and Ubuntu before the recovery branch can merge**

---

## 1. How every new chat must use this document

At the beginning of any new ChatGPT or Codex conversation concerning CSRN:

1. Read this entire file before recommending or changing anything.
2. Treat the paths, Git state, scope, decisions, blockers, and release gates here as authoritative unless Jason explicitly changes them.
3. Inspect the current Git branch, commit, and worktree before editing code.
4. Verify the exact active file and runtime route before preparing a patch.
5. Report discrepancies between this document and the repository before proceeding.
6. Update this document whenever a decision, branch, version, blocker, or release-gate status materially changes.
7. Never claim that background or overnight work is continuing unless an actual task or automation was created and can be verified.

This file governs continuity. Chat memory does not.

---

## 2. Authoritative locations

### Current synchronized development folder

```text
C:\Users\Darth\My Drive\CSRN\Development\CSRN-Production-Suite
```

Jason currently launches the suite from this folder using:

```text
RUN_CSRN_COMMAND_CENTER.bat
```

### GitHub repository

```text
https://github.com/JasonVoorheesXL/csrn-production-suite
```

### Intended source-of-truth policy

Once recovery is complete:

- **GitHub** is authoritative for application source, tests, documentation, and release history.
- **A local Git checkout** is used for development and testing.
- **Google Drive** stores backups, exported reports, approved release packages, screenshots, operator material, and customer/runtime data. It must not remain a parallel live source tree.
- **Regular ChatGPT** is used for product decisions, workflow reasoning, visual review, and release priorities.
- **Codex** is used for repository inspection, implementation, testing, and controlled Git changes.

No chat is itself a source of truth.

---

## 3. Verified launch and entrypoint behavior

`RUN_CSRN_COMMAND_CENTER.bat`:

1. Changes into its own project directory.
2. Uses `.venv\Scripts\python.exe`.
3. Installs packages from `requirements.txt`.
4. Runs game-day storage preflight and recovery startup tracking.
5. launches `app.py`.
6. Serves the suite with Waitress on port 5050.
7. Records clean shutdown when the application exits normally.

The current Flask page route uses:

```python
render_template("index.html")
```

Therefore, the active Command Center interface is:

```text
templates\index.html
```

The root-level `index.html` is currently a redundant, untracked duplicate. It must not be treated as the active Flask entrypoint.

Production launcher correction still required:

- do not upgrade `pip`, setuptools, or wheel on every normal startup;
- do not reinstall or modify production dependencies on every normal startup;
- provide a separate explicit setup/update command;
- launch from a verified locked environment.

---

## 4. Current audited Git and version state

The synchronized development folder was audited directly after Gate 1.

### Active branch

```text
recovery/alpha-8f-source-alignment
```

### Active committed HEAD

```text
0d16f17f23b7b60c5ea4720cdc695b55fbc4216a — ci: support canonical version metadata
```

### Tracking branch

```text
origin/recovery/alpha-8f-source-alignment
```

### Canonical version identity

```text
1.13.0-alpha.8f — Player Identity Repair and Source Alignment
```

### Canonical build identity

```text
V1.13A8F-SOURCE-ALIGNMENT
```

### Worktree state during PR #88 remediation

```text
Local committed HEAD is `0d16f17f23b7b60c5ea4720cdc695b55fbc4216a`.
The worktree contains the bounded fixes for the 16 failures reported by PR #88
and must be committed and pushed only after focused validation.
```

### Branch lineage

The recovery branch was created from the verified Phase 6.9 lineage, captured
the later operational worktree, completed source-hygiene cleanup, and was
independently verified locally and through GitHub at `9f37189c`. The
previously uncommitted `alpha.8f` application is now represented by a remote
Git commit.

---

## 5. GitHub state and PR warning

GitHub `main` remains the historical:

```text
v1.5.0-alpha
```

Closed PRs:

```text
PR #86 — stale documentation-only branch; closed without merge
PR #87 — superseded after a remote-ref race prevented a trustworthy PR snapshot
```

Active PR:

```text
https://github.com/JasonVoorheesXL/csrn-production-suite/pull/88
```

PR #88 targets `develop-1.13` from
`recovery/alpha-8f-source-alignment`. Its first full Windows and Ubuntu CI run
reached the complete test suite and reported `16 failed, 1197 passed`. The
identity-rendering checks fixed at `0d16f17f` passed. The remaining failures
were classified as a bounded mixture of OAuth callback defects, recap prose
regressions, and stale architecture/documentation assertions.

**PR #88 must not merge until both CI jobs pass.**

The active recovery branch is:

```text
recovery/alpha-8f-source-alignment
```

It was based on:

```text
origin/phase/6.9-social-publishing-engine
```

It did not start from `main`.

---

## 6. Current product stage

The correct stage is:

```text
Source recovery, release-candidate integration audit, and controlled operational testing
```

The product is not in ordinary feature-development mode.

The product is not ready for:

- another installer patch;
- a formal full-game rehearsal;
- a release freeze;
- a merge to `main`;
- a customer installer;
- production deployment.

The next engineering action is to complete the bounded PR #88 CI repair,
push one guarded checkpoint, and require green Windows and Ubuntu jobs.

---

## 7. Confirmed strengths

The audit confirmed substantial working product architecture:

- 193 unique Flask routes register.
- 139 Python test files exist.
- All Python source compiles.
- Embedded JavaScript in all eight HTML pages passes syntax validation.
- No missing static API route reference was found in the UI scan.
- `/`, `/overlay`, `/captions`, `/weather-overlay`, and `/api/security-status` pass basic smoke tests.
- Protected pages reject unauthenticated access.
- Root and template `index.html` copies are currently identical, although only the template is the Flask entrypoint.
- The active lineage contains the game-day, repository, service, route, OBS, recovery, weather, caption, theme, social, and recap foundations.

The project is recoverable. The current problem is integration discipline and release evidence.

---

## 8. Confirmed blocking defects

### 8.1 Source and release identity

- No Git commit represents the running `alpha.8f` build.
- GitHub `main`, the active branch, Drive documents, `VERSION.txt`, and PR #86 describe different product states.
- A clean checkout cannot reproduce the running suite.

### 8.2 Player and school identity rendering

- The overlay still uses `/static/csrn-logo.png` as a final automatic fallback for player portraits and team watermarks.
- The Command Center player preview also falls back to the CSRN logo.
- Unrelated CSRN branding must not automatically replace a missing player or school identity.

Required fallback order:

Player portrait area:

1. Player headshot
2. Selected player’s team logo
3. Team monogram
4. Neutral player silhouette

Team watermark area:

1. Selected player’s team/school logo
2. School monogram
3. Neutral blank treatment

### 8.3 Roster headshot visibility

The roster list currently displays:

- jersey number;
- player name;
- position;
- class;
- active/inactive status.

It does not display:

- headshot thumbnail;
- team-logo fallback;
- explicit missing-headshot indicator.

This must be corrected so operators can verify player media without opening each record.

### 8.4 Obsolete headshot utility

These remain in the active folder:

```text
MANAGE_PLAYER_HEADSHOTS.cmd
tools\manage_player_headshots.py
```

The tool requires the player’s internal stored ID. It was added even though Edit Player already provides Upload Headshot.

The utility is obsolete and must be removed after the integrated upload path is verified.

### 8.5 Player-event visual defects

- Event-label color is derived from team accent color and can become unreadable on dark treatments.
- Event label, player name, and supporting details require explicit independent spacing.
- Long player names need shrink/wrap containment.
- `pg-onair-play-detail` is populated but has no CSS rule.
- Missing and invalid media states require visual regression coverage.

### 8.6 Duplicate HTML IDs

The active Command Center contains duplicate IDs for the school-import interface:

```text
schoolImportPanel
importState
importClassification
importCreateVenues
runSchoolImport
runSchoolEnrichment
runBrandingEnrichment
schoolImportSummary
schoolImportResults
```

These must be made unique.

### 8.7 Test reproducibility

- 139 tests exist.
- `pytest` is not installed in the active virtual environment.
- `pytest` is not declared in `requirements.txt`.
- No dedicated development/test dependency declaration exists.
- The synchronized virtual environment points to an external Python installation and an older original creation path.

The tests therefore cannot currently be reproduced from the declared project setup.

### 8.8 Runtime data in source control

Twenty-three `Data` files are already tracked, including:

- pre-upgrade backups;
- social state;
- weather state;
- caption state;
- venue state;
- theme state;
- package state;
- rehearsal state.

Runtime/customer data must be separated from source. A sampled tracked backup contained an OBS password field, but its value was empty at audit time.

---

## 9. Frozen football product scope

The initial finished product is a Windows-hosted football broadcasting suite with browser-based control from phones, tablets, Chromebooks, and secondary computers.

Explicitly removed from scope:

- dedicated Chromebook/PWA product;
- automated X posting;
- X OAuth/API integration;
- hosted AI;
- local AI;
- other sports before football release evidence;
- macOS host before Windows stability.

X remains assisted-manual only.

Postgame articles remain deterministic and grounded in recorded data.

### Required existing workflow

- Configuration
- School Database
- Venue association
- Staff/personnel directory
- Rosters and player media
- New Broadcast
- Command Center
- OBS/scorebug
- clock, quarter, down/distance, possession, scoring, corrections, and undo
- event history
- statistics
- sponsors
- captions
- weather and alerts
- Social Publishing
- manual X package
- Facebook workflow where configured
- Player of the Game
- grounded recap
- deterministic article
- archive and recovery
- release readiness

### Remaining approved pre-freeze football features

These may be implemented only after source recovery and baseline repair:

1. Regional classification and region assignment.
2. Region-game flag.
3. Overall and regional record tracking.
4. Scrimmage/exhibition rules that do not alter official records.
5. Special-game designations such as Homecoming, Senior Night, rivalry, playoff, and championship.
6. Player Highlight using the existing Player Identification Card.
7. Team-filtered player selection for Player Highlight.
8. Manual show, hide, and clear controls.
9. Verified statistics only.

No additional pre-release features are to be added without an explicit scope decision recorded here.

---

## 10. Recovery and completion plan

### Gate 0 — Preserve and freeze

- Stop installer-based changes.
- Stop feature development.
- Do not merge PR #86.
- Preserve the current Drive tree.
- Record file hashes.

Exit condition: today’s state is recoverable.

### Gate 1 — Recover `alpha.8f` into Git

- Create `recovery/alpha-8f-source-alignment` from `origin/phase/6.9-social-publishing-engine`.
- Apply the 26 tracked changes.
- Review the 21 untracked paths individually.
- Add valid source, tests, documentation, and fixture assets.
- Exclude live data, secrets, caches, virtual environments, generated output, obsolete utilities, and temporary tunnel artifacts.
- Move fictional data into a dedicated versioned fixture tree.

Exit condition: one clean Git commit reproduces the operational application.

### Gate 2 — Repair governance

- Choose one version/build identity.
- Synchronize `VERSION.txt`, README, roadmap, changelog, build journal, UI identity, and this Bible.
- Close PR #86 as superseded.
- Review and merge the recovery branch into `develop-1.13`.

Exit condition: documents and application identify the same commit and version.

### Gate 3 — Reproducible environment and tests

- Add `pytest` to a development dependency declaration.
- Pin or lock production dependencies.
- Build a clean virtual environment.
- Run all 139 tests.
- Add GitHub CI.
- Add a deterministic build command.
- Separate setup/update from normal application startup.

Exit condition: a clean clone can install, test, build, and launch.

### Gate 4 — Repair blocking product defects

- neutral identity fallbacks;
- roster thumbnails/missing indicators;
- integrated headshot persistence;
- obsolete headshot utility removal;
- event-label contrast;
- event/name/detail spacing;
- play-detail styling;
- long-name containment;
- home/visitor logo validation;
- duplicate ID repair;
- regression tests.

Exit condition: no open blocking identity or interface defect.

### Gate 5 — Complete frozen football scope

- regional data and record rules;
- special-game designations;
- Player Highlight;
- tests and documentation.

Exit condition: approved football scope is complete.

### Gate 6 — Visual regression

Render and approve:

- home and visitor teams;
- headshot present/missing;
- school logo present/missing;
- short and long names;
- touchdown, turnover, field goal, player highlight, and Player of the Game;
- scorebug, ticker, lower third, sponsor, caption, weather, and social states;
- desktop, phone, and production-resolution views.

Exit condition: approved screenshots exist for all material states.

### Gate 7 — Software-only rehearsals

Run two complete games from one exact commit, including:

- New Broadcast and venue population;
- full football workflow;
- statistics;
- sponsors;
- social drafts without unintended publication;
- recap/article;
- archive and reopen;
- application termination and state recovery;
- wrong-team and stale-draft prevention.

Exit condition: two software rehearsals pass with no blocking defects.

### Gate 8 — P4next and OBS commissioning

- isolated P4next channels;
- gain and headphone mixes;
- multitrack backup;
- OBS audio and recording;
- browser sources;
- phone/Chromebook control;
- network-loss response;
- caption-channel assignments.

Exit condition: commissioning report passes.

### Gate 9 — Formal Phase 6.6 rehearsals

Complete two operator-recorded rehearsals and required recovery drills:

- OBS loss;
- network loss;
- application termination;
- caption-worker loss;
- weather-service loss;
- mixer/USB loss;
- safety-snapshot restore;
- weather delay and resumption.

Exit condition: all drills pass and no blocking defect remains.

### Gate 10 — Freeze release candidate

- record exact commit SHA;
- record version/build;
- preserve tests and rehearsal evidence;
- preserve approved screenshots;
- generate rollback artifact;
- write release manifest;
- tag the commit.

Suggested first tag:

```text
v1.13.0-football-rc1
```

### Gate 11 — Customer-ready product

- Windows installer/uninstaller;
- stable external customer-data location;
- upgrade preservation;
- clean default data;
- rollback;
- customer-safe support bundle;
- licensing/entitlement completion;
- signed artifacts where available;
- operator and installation manuals.

### Gate 12 — Pilot and final release

1. Private/unlisted broadcast.
2. Supervised live game.
3. Correct pilot defects.
4. Second live game.
5. Final 1.0 approval.

---

## 11. Definition of done

CSRN football is finished only when:

- a clean Git commit is authoritative;
- a clean machine can install and launch it;
- all automated tests pass;
- all blocking visual and functional defects are closed;
- frozen football scope is complete;
- two software-only rehearsals pass;
- P4next/OBS commissioning passes;
- two formal Phase 6.6 rehearsals and all recovery drills pass;
- the release candidate is tagged and reproducible;
- installer, upgrade, rollback, documentation, and clean customer data are ready;
- at least two controlled live pilots succeed.

“Works on the current Drive folder” is not the definition of done.

---

## 12. Change-control rules

Every code change must:

1. Start from a named Git branch and recorded commit.
2. State the defect or approved requirement.
3. Identify the exact active files and routes.
4. Add or update tests.
5. Avoid live customer/runtime data.
6. Pass focused tests before broad tests.
7. Receive visual verification when presentation changes.
8. Update changelog and this Bible when material.
9. Produce a commit before packaging.
10. Package only from the tested commit.

Never:

- patch duplicated Drive search results without grounding the active folder;
- build a release from chat-generated files that are not committed;
- overwrite the running project using an unverified installer;
- claim testing passed when only compilation or static review ran;
- advance rehearsals with an open blocking identity, score, persistence, or recovery defect;
- use unrelated CSRN branding as an automatic player/team fallback;
- allow a new chat to infer project state from its title or memory.

---

## 13. Project Bible update protocol

Update this file whenever any of these changes:

- authoritative folder;
- Git branch;
- commit SHA;
- version/build;
- product scope;
- approved or removed feature;
- current gate;
- open blocker;
- resolved blocker;
- test count or result;
- rehearsal result;
- release tag;
- source-of-truth policy.

Each update should add an entry to the decision/status log below.

---

## 14. Decision and status log

### 2026-07-30 — Continuity and source audit

- Confirmed the synchronized development folder as the operational folder.
- Confirmed `RUN_CSRN_COMMAND_CENTER.bat` launches `app.py`.
- Confirmed Flask serves `templates/index.html`.
- Confirmed active branch `phase/6.9-social-publishing-engine`.
- Confirmed committed version `alpha.6i` and worktree version `alpha.8f`.
- Confirmed 26 modified and 21 untracked paths.
- Confirmed PR #86 is documentation-only and based on stale `main`.
- Confirmed source recovery is the immediate next action.
- Confirmed release status is blocked.

### 2026-07-30 — Gate 0/1 preservation checkpoint

- Reverified the operational checkout at commit `838708b047e7` on `phase/6.9-social-publishing-engine`.
- Reverified 26 modified tracked paths and 68 actual untracked files (shown by Git as 22 summarized untracked paths after this Bible was added).
- Created remote branch `recovery/alpha-8f-source-alignment` from `phase/6.9-social-publishing-engine`.
- Captured all 94 changed and untracked files in verified commit `8ad61cdd3e07ee4f3f01ec25aba0a87ccc6b11a4`.
- Verified recovery tree `7dc09dbf213d5656365175ce3896100fddcc2c4c` and a clean worktree against the captured commit.
- Packaged the complete commit and history in `CSRN_GATE_1_RECOVERY.bundle`; the guarded completion script verifies its SHA-256 before importing it.
- Local installation and remote push remain pending because the Codex runtime cannot write the operational checkout's hidden `.git` metadata or provide network access to spawned Git.
- Prepared `COMPLETE_CSRN_GATE_1.ps1` to make a safety stash, import the verified bundle, switch to the recovery branch, verify the exact commit and clean status, and push it to `origin`.
- Gate 0 is complete. Gate 1 is preserved and reproducible, but it is not complete until the guarded script succeeds.

### 2026-07-30 — Gate 1 source-hygiene checkpoint

- Verified recovery commit `ce432e4aadc6024b868ec5a717e892f4517fb6fb` locally and on GitHub with zero divergence.
- Retained safety stash `fb862149215d23eebbf4e5b714ca54079963ee08`.
- Confirmed local recap, social-card, Facebook connection, and encrypted credential files are ignored and not tracked.
- Removed the duplicate root `index.html`; Flask continues to serve `templates/index.html`.
- Removed the obsolete standalone player-headshot utility.
- Removed the temporary Facebook tunnel launcher and retained direct manual tunnel instructions.
- Consolidated fictional headshots, school logos, and sponsor logos into the Northwood–Pine Valley fixture tree.
- Removed fictional fixture venues from operational venue data.
- Removed `Data/Social/social_state.json` from Git tracking without deleting the local runtime file.
- Added source-hygiene regression coverage.
- Committed and pushed `9f37189c5b4fed6c76b8e6228fe8c3086f7c5290`.
- Independently verified the local worktree is clean, local/origin divergence is
  `0/0`, and the connected GitHub branch resolves to the same commit.
- Gate 1 is complete. Gate 2 governance repair is active.

### 2026-07-30 — Gate 2 canonical identity decision

- Selected `1.13.0-alpha.8f — Player Identity Repair and Source Alignment`.
- Selected build `V1.13A8F-SOURCE-ALIGNMENT`.
- Rejected `1.0/1.2 Alpha`, `v1.5.0-alpha`, runtime `alpha.8e`, and build
  `V1.13A8A-FOOTBALL-RC-READINESS` as stale current-state identities.
- Synchronized the runtime fallback, `VERSION.txt`, README files, roadmap,
  changelogs, build journal, and this Bible.
- Added regression coverage that fails when the canonical version or build
  identity drifts across authoritative files.
- Closed draft PR #86 without merge as superseded by the verified recovery
  branch.
- Compared the recovery branch with `develop-1.13` on GitHub. Before the Gate 2
  commit, recovery is three commits ahead and one ancestry-only commit behind;
  the develop-only comparison contains no file changes, so no source payload
  must be imported from `develop-1.13`.

### 2026-07-30 — PR #88 CI remediation checkpoint

- Completed the Gate 2 governance checkpoint at
  `d40467e5b2ab9128493ad82bfec0b6b6e514f547`.
- Added canonical multiline `VERSION.txt` support to the development workflow
  and committed it at `0d16f17f23b7b60c5ea4720cdc695b55fbc4216a`.
- Closed PR #87 without merge after a remote-ref race made its snapshot
  unreliable, then opened PR #88 from the verified branch head.
- Verified that PR #88 passes Python compilation, clean-diff validation, and
  canonical version/build identity checks on both CI platforms.
- Classified the full-suite result of `16 failed, 1197 passed`.
- Corrected the Facebook callback to return to `/social`, use one single-use
  server-side OAuth state store, and remain the only intentional public social
  endpoint.
- Restored editable HTTPS callback configuration and removed the obsolete HTTP
  loopback fallback from the Social Publishing interface.
- Restored grounded lead-change, turnover, and weather descriptions to recap
  prose.
- Aligned route, navigation, social-policy, and documentation regression tests
  with the current Facebook/assisted-manual-X architecture.
- Local dependency-free validation passes all 12 recap-service tests and nine
  focused architecture/grounding checks. Full Flask integration remains
  delegated to GitHub CI because the synchronized `.venv` points to a missing
  Python 3.14 installation.
- This repair remains uncommitted until the guarded checkpoint script is run.

---

## 15. Copy-ready prompt for a new chat

Use this prompt when starting any new ChatGPT or Codex conversation:

```text
Continue the CSRN Production Suite using the living project Bible located at:

C:\Users\Darth\My Drive\CSRN\Development\CSRN-Production-Suite\CSRN_PROJECT_BIBLE.md

Read the entire Bible before recommending or changing anything. Treat it as the authoritative continuity and release-control document unless I explicitly change a decision.

Gate 1 source recovery and the Gate 2 governance checkpoint are complete.
The committed branch head is
`0d16f17f23b7b60c5ea4720cdc695b55fbc4216a` on
`recovery/alpha-8f-source-alignment`, with canonical identity
`1.13.0-alpha.8f` / `V1.13A8F-SOURCE-ALIGNMENT`.

PR #88 targets `develop-1.13`. Its first full CI run reported
`16 failed, 1197 passed`; a bounded repair is in the worktree and requires a
guarded commit/push followed by green Windows and Ubuntu CI. PRs #86 and #87
are closed without merge. Do not add features, apply installer ZIPs, modify
live runtime data, or merge PR #88 while checks are failing.

Before acting, report:
1. the development folder you inspected;
2. the current Git branch and commit;
3. the worktree status;
4. the current release gate;
5. any discrepancy between the Bible and the repository.

Then proceed only within the next incomplete gate documented in the Bible.
```

---

## 16. Immediate next action

The next action is:

```text
Commit and push the bounded PR #88 CI repair, monitor both Windows and Ubuntu
jobs, correct only evidenced failures, and merge into develop-1.13 only after
all required checks pass.
```

Do not begin visual fixes or new features until the recovery branch is merged
and the next release gate is active.
