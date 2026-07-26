# Phase 6.4 — Channel-Based Captioning

Phase 6.4 establishes the live caption data, presentation, transcript, and local recognition boundaries required for CSRN game-day broadcasts.

## Speaker identity

Speaker identity comes from the commissioned physical P4next input channel rather than voice diarization.

Default assignments:

- Channel 1 — Jason
- Channel 2 — Jordan
- Channel 3 — Guest 1, disabled until assigned
- Channel 4 — Guest 2, disabled until assigned

The profile supports channels 1–12 so later hardware can add sideline reporters, studio talent, or remote guests without changing the caption data model.

## Caption service

`CaptionService` owns:

- channel-to-speaker mapping;
- confidence filtering;
- profanity policy;
- display delay and duration;
- caption length and line limits;
- live overlay state;
- transcript persistence by broadcast;
- operator correction;
- SRT and WebVTT export.

The service stores:

- `Data/Settings/caption_profile.json`
- `Data/Captions/caption_state.json`
- `Data/Captions/Transcripts/<broadcast-id>.json`

Writes use temporary-file replacement so a partial process failure does not leave malformed caption JSON.

## OBS overlay

Add an OBS browser source pointing to:

```text
http://127.0.0.1:5050/captions
```

Recommended browser-source size:

```text
1920 × 1080
```

The page uses a transparent background and polls the public read-only overlay-state endpoint. It never exposes transcript-management or profile-control operations publicly.

## Operator API

Public:

- `GET /captions`
- `GET /api/captions/overlay-state`

Authenticated:

- `GET /api/captions/status`
- `PUT /api/captions/profile`
- `POST /api/captions/segments`
- `POST /api/captions/visibility`
- `POST /api/captions/clear`
- `PATCH /api/captions/segments/<segment-id>`
- `GET /api/captions/transcripts/<broadcast-id>`
- `GET /api/captions/transcripts/<broadcast-id>.srt`
- `GET /api/captions/transcripts/<broadcast-id>.vtt`

## Local recognition worker

The optional local worker reads the commissioned P4next multichannel USB input, keeps each enabled microphone channel isolated, resamples the commissioned 48 kHz signal to 16 kHz, and sends recognized segments to `CaptionService`.

Optional packages:

```cmd
python -m pip install numpy sounddevice faster-whisper
```

Start the worker after selecting the correct multichannel input device:

```cmd
python tools\run_caption_worker.py --device "ZOOM P4next" --model small.en
```

The base CSRN application does not import these heavy optional packages. A missing speech-recognition dependency cannot prevent Command Center from starting.

## Game-day policy

- Caption visibility defaults off until the operator enables it.
- Low-confidence segments are withheld rather than displayed.
- The operator can clear or correct the current text without deleting the original transcript history.
- The transcript keeps raw and displayed text for later auditing.
- Captions must be rehearsed with the actual P4next device and Windows audio driver before the release freeze.
- Platform-specific switchable closed-caption adapters remain destination-dependent. The OBS browser source is the dependable universal fallback.

## Following stage

Phase 6.5 adds venue weather monitoring and alert overlays. Weather-delay and resumption events remain reserved for the later Social Publishing Engine, now Phase 6.9.
