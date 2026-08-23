# Phase 6.3 Hardware and OBS Commissioning

Phase 6.3 creates a persistent commissioning record for the physical game-day system. It does not attempt to infer microphone quality or power reliability from software alone. The operator records those observations after testing the actual equipment, while OBS structure is checked through the existing read-only WebSocket client.

## Required P4next profile

- Device: ZOOM P4next
- Windows USB device: `ZOOM P4next`
- USB audio interface mode: `Multi Track`
- Recorder mode: `Multi Track`
- Sample rate: 48 kHz
- Bit depth: 24-bit
- microSD card installed and formatted in the P4next
- ZOOM Windows driver installed for multichannel ASIO use
- USB data cable verified
- primary USB power verified
- backup battery or portable-power path verified

The default channel map is:

1. Announcer 1 — Play-by-Play placeholder
2. Announcer 2 — Analyst placeholder
3. Announcer 3 — disabled until assigned
4. Announcer 4 — disabled until assigned

These labels are neutral installation placeholders, not fixed identities. Each customer assigns its own broadcasters, roles, microphones, and enabled channels during commissioning. Channel assignments are persistent and become the speaker-identity source for Phase 6.4 captioning. At least two enabled channels must have unique, non-empty speaker names.

## Operator audio checks

The commissioning report requires explicit confirmation of:

- microphone input gain;
- independent headphone mixes;
- no clipping;
- no unacceptable hum or noise;
- channel isolation;
- local multitrack recording;
- master stereo recording;
- OBS audio routing.

These checks should be repeated whenever the mixer profile, USB driver, microphones, adapters, or laptop audio configuration changes.

## OBS contract

The commissioning service invokes the existing read-only OBS validation and requires:

- WebSocket reachability and authentication;
- expected OBS profile;
- expected scene collection;
- football scorebug scene;
- scorebug browser source in that scene;
- program visual scene;
- graphic source in the program visual scene.

The configured camera source is reported but is not a game-day gate for the audio-first CSRN release.

## Network and output checks

Required:

- phone control on the production network;
- primary internet path;
- private stream test;
- local OBS recording test.

Recommended but not required for the first readiness pass:

- backup internet path.

## API

All endpoints require operator authentication.

- `GET /api/game-day/commissioning`
- `PUT /api/game-day/commissioning`
- `POST /api/game-day/commissioning/check`
- `POST /api/game-day/commissioning/obs-test`
- `GET /api/game-day/commissioning/report`

The profile is stored at `Data/Settings/hardware_commissioning.json` and is included in normal game-day safety snapshots because the complete `Data` directory is captured.

## Command-line report

Run:

```cmd
python tools\commissioning_report.py --obs-test
```

The command optionally refreshes the read-only OBS check, prints every required and recommended item, and exits with a nonzero status while commissioning is incomplete.

## Handoff to Phase 6.4

Phase 6.4 uses these physical channel assignments for speaker-separated captions. It must not fall back to voice diarization when isolated P4next channels are available.

The commercial roadmap remains unchanged: the graphics theme engine is Phase 6.8, Social Publishing Engine is Phase 6.9, and grounded postgame recaps are Phase 6.10.
