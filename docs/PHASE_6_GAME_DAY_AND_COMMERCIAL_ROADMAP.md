# Phase 6 Game-Day and Commercial Roadmap

Phase 6 converts the validated CSRN application foundation into a dependable game-day product and then into a commercially distributable platform.

## Game-day release gate

### 6.1 Game-Day Safety Foundation

- authenticated game-day preflight reporting;
- automatic startup safety snapshots;
- manual safety snapshots;
- cryptographic snapshot verification;
- bounded retention for automatic snapshots;
- launcher-level startup blocking when required storage or JSON state is unhealthy.

### 6.2 Recovery and Rollback

- operator-guided restore workflow;
- pre-restore snapshot creation;
- live-broadcast restore lockout;
- known-good release rollback;
- crash marker and unclean-shutdown reporting;
- recovery rehearsal documentation.

### 6.3 Hardware and OBS Commissioning

- Zoom PodTrak P4next multichannel USB profile;
- channel assignments and gain verification;
- local multitrack backup recording;
- OBS scene/source contract verification;
- phone control and network validation;
- stream and recording health checks.

### 6.4 Channel-Based Captioning

Captions are a required game-day feature. Speaker identity comes from the physical P4next input channel rather than voice diarization.

- assignable speaker name per audio channel;
- isolated real-time speech recognition per channel;
- combined time-ordered caption stream;
- confidence filtering, profanity policy, and adjustable delay;
- school, player, sponsor, and football vocabulary;
- operator show/hide/clear/correct controls;
- transcript persistence with SRT and WebVTT export;
- OBS browser-source caption fallback;
- closed-caption output adapters for destinations that support a switchable caption track.

### 6.5 Operational Rehearsal and Release Freeze

- two complete simulated football games;
- forced OBS, network, mixer, and application recovery drills;
- final defect correction;
- frozen game-day release candidate;
- pregame, halftime, postgame, and emergency checklists.

## Commercial release gate

### 6.6 Installer, Updates, and Licensing Foundation

- Windows installer and uninstaller;
- stable user-data location outside the application binaries;
- signed release artifacts when available;
- upgrade and rollback workflow;
- licensing and entitlement boundaries;
- customer-safe diagnostics and support bundle.

### 6.7 Graphics Theme Engine

The commercial release includes one theme engine and at least eight original presets rather than duplicated graphics implementations.

Initial preset directions:

1. Classic 1980s Broadcast
2. Early Cable Sports
3. Modern Network
4. Minimal Radio
5. Heritage Press Box
6. Friday Night Stadium
7. Digital Neon
8. Collegiate Traditional

Theme tokens control scorebugs, lower thirds, player/personnel cards, sponsor panels, captions, social graphics, typography, borders, textures, transitions, and school-color adaptation. Presets must be original genre-inspired designs and must not copy a television network package.

### 6.8 Social Publishing Engine

- preview-first one-click publishing to supported Facebook and X account types;
- event posts for touchdowns, turnovers, field goals, safeties, lead changes, halftime, final score, milestones, and player of the game;
- player headshots, school branding, score context, broadcast links, and approved sponsor assets;
- platform-specific copy and image dimensions;
- draft queue, retry handling, audit history, and correction/replacement workflow;
- configurable sponsor rotation and event sponsorship;
- no automatic publication without an explicit account-level operator setting.

### 6.9 Grounded Game Recap Engine

The recap generator may use only recorded game events and available statistics.

Without a statistician it can summarize final score, scoring sequence, lead changes, turnovers, halftime score, and recorded major events. With sufficient statistics it can add team totals, passing/rushing/receiving leaders, first downs, penalties, turnover margin, scoring drives, defensive leaders, and player-of-the-game candidates.

Missing data is omitted. The engine must not invent yardage, player attribution, or scoring events. Every recap remains previewable and editable before publication.
