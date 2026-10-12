# Verification record

Date: 2026-10-12. Environment: Windows, Python 3.12, dependencies recorded in `requirements-tested.txt`.

## Executed

- `python -m pytest -q`: 20 tests passed.
- `python -m sdvxbot demo --output demo-output`: 11 expected / 11 detected presses over 720 synthetic frames, no input API connected.
- Demo assertions check each lane/time, chord, repeated-lane hit, chip release duration, and both hold releases (35 ms tolerance for hold ends).
- TCP tests run actual loopback sockets against a mock server: fragmented messages, plaintext/password RC4, discovery, batched button/analog write shapes, scoped reset, duplicate-write suppression, mismatch IDs, server errors, EOF and timeout.
- Known RC4 test vector validates the cipher independently of the mock. No session refresh is implemented.
- Vision tests check judgment-line proposal, identity perspective transform, HSV laser centroid, stationary-note rejection, association ordering, temporary occlusion, expired tracks, stale-frame reset, processing-age extrapolation, laser jump/loss abstention.
- Runtime lifecycle tests inject capture failure, panic-key callback and a blocked capture to exercise watchdog stop and cleanup. They use fake keyboard/capture providers and do not operate the desktop.
- KSH fixture checks BPM change, chip conventions and hold durations across a measure boundary. Unsupported stop directives reject explicitly.
- VOX test checks raw position preservation and the explicit unverified-semantics warning.
- Synchronization fixture gives scale 1.0002 and offset 1.25 s, with negligible numerical residual.
- The generated demo frame was visually inspected.

## Not exercised / not claimed

- No running Spice or kspice instance was available. Real server compatibility, in-game input acceptance, button polling and actual timing accuracy remain unverified.
- No real gameplay screenshot/video was provided. HSV defaults and real note/hold/laser classification are not validated against any game skin.
- The interactive calibration UI, real MSS capture and physical global panic key were not tested on a game desktop. Check them in dry-run locally.
- Mock round trips are not evidence of secure authentication or production reliability. RC4 is used solely to match the documented protocol.
- Laser gain/direction and the game's interpretation of analog phase are unverified and require explicit experimental opt-in.
- VOX has no semantic note/time conversion; it is a structural inspection utility only.
- Timing guarantees, full chart coverage, online isolation detection and perfect scores are not claimed.

The first test run found a row-delimiter parsing defect and an OpenCV 5 Hough-output shape difference. Both were corrected before the final passing run.
