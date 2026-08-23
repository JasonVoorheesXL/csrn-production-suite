# Gate 6 Final Visual Acceptance Checklist

Branch: `gate6/final-visual-matrix`  
Base commit: `a97bef4fd72211c66b6899256cb0051cf8a3f796`

Do not commit or push until every operator-accessible material state is marked
Pass or a discovered defect has been repaired, validated, and retested.

## Global acceptance rules

For every state:

- correct school/player/sponsor identity;
- readable at normal production viewing size;
- no clipping, overflow, collision, or blank reserved region;
- scorebug and ticker remain in the intended layer order;
- show/hide/clear controls respond promptly;
- no unexpected connection banner;
- no repeated media-load errors or Waitress task-queue warnings;
- screenshot contains no credentials, tokens, or private customer data.

## A. Player graphic states

### A1 — Valid headshot
- [ ] Correct player, number, team, and headshot.
- [ ] Name and detail remain contained.
- [ ] Team watermark is correct.
- [ ] Screenshot: `01-player-valid-headshot.png`

### A2 — Missing headshot
- [ ] Player portrait falls back to selected player's team logo.
- [ ] No unrelated CSRN identity is used.
- [ ] Screenshot: `02-player-missing-headshot.png`

### A3 — Touchdown
- [ ] Touchdown label is readable and independent of team accent color.
- [ ] Player name/detail spacing is correct.
- [ ] Screenshot: `03-player-touchdown.png`

### A4 — Turnover
- [ ] Turnover treatment renders the selected player/team correctly.
- [ ] Long text remains contained.
- [ ] Screenshot: `04-player-turnover.png`

### A5 — Field goal
- [ ] Field-goal treatment renders selected player/team correctly.
- [ ] Long text remains contained.
- [ ] Screenshot: `05-player-field-goal.png`

### A6 — Player Spotlight
- [ ] Prepared card shows the selected roster/player.
- [ ] Manual Show, Hide, and Clear work.
- [ ] Screenshot: `06-player-spotlight.png`

### A7 — Player Highlight video
- [ ] Correct video loads and plays within its stage.
- [ ] Video is not distorted or clipped outside the approved region.
- [ ] Hide/Clear stops and resets playback.
- [ ] Screenshot: `07-player-highlight-video.png`

### A8 — Player of the Game
- [ ] Correct player identity and title.
- [ ] Headshot/team-logo fallback remains correct.
- [ ] Screenshot: `08-player-of-game.png`

## B. Lower third

### B1 — Short copy
- [ ] Eyebrow, headline, secondary line, and optional footer align correctly.
- [ ] Screenshot: `09-lower-third-short.png`

### B2 — Long copy
- [ ] Long name/title remains readable and contained.
- [ ] No overlap with logo or screen edge.
- [ ] Screenshot: `10-lower-third-long.png`

## C. Sponsor Spotlight

### C1 — Still image
- [ ] Approved still/logo is letterboxed rather than stretched or cropped.
- [ ] Sponsor name and caption are readable.
- [ ] Scorebug/ticker layering is correct.
- [ ] Screenshot: `11-sponsor-still.png`

### C2 — Video
- [ ] Valid video plays inside the feature stage.
- [ ] Hide/Clear stops playback.
- [ ] Mark N/A only when no valid fixture video is available.
- [ ] Screenshot: `12-sponsor-video.png`

### C3 — Missing or invalid creative
- [ ] No broken-image icon or uncontrolled blank block.
- [ ] Text treatment remains contained.
- [ ] Screenshot: `13-sponsor-invalid-creative.png`

## D. Captions

### D1 — Short caption
- [ ] Caption appears promptly and is readable.
- [ ] Screenshot: `14-caption-short.png`

### D2 — Long caption
- [ ] Long caption wraps/contains correctly.
- [ ] No overlap with scorebug or ticker.
- [ ] Screenshot: `15-caption-long.png`

### D3 — Hidden
- [ ] Caption clears without leaving a visible backing panel.
- [ ] Screenshot: `16-caption-hidden.png`

## E. Weather

### E1 — Normal
- [ ] Venue and weather values are readable and correctly associated.
- [ ] Screenshot: `17-weather-normal.png`

### E2 — Alert
- [ ] Alert is visually distinct and remains contained.
- [ ] Screenshot: `18-weather-alert.png`

### E3 — Hidden
- [ ] Weather treatment clears cleanly.
- [ ] Screenshot: `19-weather-hidden.png`

## F. Social preview

### F1 — Draft/card preview
- [ ] Correct teams, score/context, branding, and sponsor treatment.
- [ ] Preview does not publish.
- [ ] No stale prior-game team or copy remains.
- [ ] Screenshot: `20-social-preview.png`

## G. Responsive and production views

### G1 — Phone-width Command Center
- [ ] Primary game controls are reachable without horizontal page overflow.
- [ ] Buttons remain legible and usable.
- [ ] No duplicated or overlapping panels.
- [ ] Screenshot: `21-phone-command-center.png`

### G2 — Production-resolution overlay
- [ ] Review all approved graphics at the actual OBS browser-source resolution.
- [ ] No scaling blur, edge clipping, or unexpected safe-area violation.
- [ ] Screenshot: `22-production-overlay.png`

## Deferred, not failed

- Compact scorebug: automated geometry only; no operator-accessible Compact mode.
- Camera mode: not implemented.
- Sponsor video: may be N/A only when no valid fixture video exists.

## Runtime observation

- Waitress task-queue warnings: Yes / No
- Request failures: Yes / No
- Unexpected connection banner: Yes / No
- Repeated media-load errors: Yes / No
- Highest observed `/api/state` response time:
- Problems:

## Final result

- [ ] All operator-accessible states pass.
- [ ] Every required screenshot exists.
- [ ] Deferred/N/A states include a written reason.
- [ ] No blocking visual defect remains.
- [ ] Focused and full tests pass from the final exact commit.