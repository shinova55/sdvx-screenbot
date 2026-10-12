# SOUND VOLTEX screen-reading lab

A runnable Python project for **local/offline experiments** with a Spice-compatible setup. Screen capture drives input; chart files never drive gameplay. It includes OpenCV calibration, color/shape detection, frame association, velocity prediction, BT/FX taps and holds, experimental laser motion, a TCP input controller, and an asset-free synthetic demo.

**Status:** tested against synthetic images and a local mock TCP server, not a running SOUND VOLTEX, kspice, or Spice2x installation. This is an experimental configurable vision baseline, not a verified full-game autoplay solution. No real playfield screenshots were supplied. Actual skins, perspective animation, effects, display latency, and knob response require local calibration. Protocol details were checked against upstream source; see [SOURCES.md](SOURCES.md).

## Install and run the offline demo

Windows PowerShell, Python 3.10 or newer:

```powershell
cd path\to\sdvx-screenbot
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m sdvxbot demo --output demo-output
.\.venv\Scripts\python.exe -m sdvxbot demo --show
```

The headless demo processes 720 generated frames at simulated 120 FPS. It covers four BT lanes, both FX lanes, holds, a chord and a repeated lane. `demo-output/events.json` records decisions; `summary.json` compares press counts; `demo-frame.png` shows a generated frame. No game, network connection, screen capture, or global keyboard hook is used in demo mode. Simulation runs faster than wall time and does not measure capture performance.

Optional editable installation: `python -m pip install -e .` exposes the `sdvxbot` command. Run from this folder or pass an absolute `--config` path. OpenCV's regular package is required for calibration and preview; do not install its headless variant.

## Configure and calibrate the screen

1. Copy `config.example.json` to `config.local.json`. Keep the game window fixed on an **offline practice playfield**. The project does not detect or disconnect online services: isolate the game yourself before enabling input. Loopback API access alone does not make the game offline.
2. Run the calibration command below. Select a ROI on the primary monitor. Then click the four playfield corners in order: top-left, top-right, bottom-right, bottom-left. Include some space below the judgment line so note tails remain observable. Right-click removes a mistaken point. Enter confirms; Escape cancels.
3. OpenCV proposes a horizontal judgment line using Canny edges and Hough segments. Adjust the judgment slider and five BT lane boundaries. The outer boundaries and center boundary define FX-L/FX-R spans. Confirm against the visible playfield before pressing Enter. Geometry is saved with a verification image beside the config.
4. For another monitor, set `roi` explicitly and use `calibrate --image roi.png` with a matching already-cropped screenshot. That mode preserves the configured desktop ROI origin. Image coordinates and ROI dimensions must match actual physical capture pixels. Keep Windows scaling, game resolution and window position unchanged after calibration.

```powershell
.\.venv\Scripts\python.exe -m sdvxbot --config config.local.json calibrate --output config.local.json
.\.venv\Scripts\python.exe -m sdvxbot --config config.local.json run --seconds 30
```

The second command is **dry-run**. It captures the ROI and logs proposed controls to `run-events.json`; it never opens an API connection. Move its preview outside the capture region to prevent feedback. Green marks the judgment line; red rectangles show detections. F12 is the global panic key; Escape works in the preview; Ctrl+C also stops. Verify the global hook during dry-run before live testing. Elevation differences, remote desktop and protected/fullscreen capture may interfere; these are not bypassed.

### Tune detection before input

`vision.colors` contains OpenCV HSV intervals: hue 0–179, saturation/value 0–255. Defaults assume pale BT, orange FX, cyan left laser and magenta right laser. These are hypotheses for a skin, not certified game constants. Edit intervals from your actual images. Multiple intervals allow hue wraparound. `vision.lanes` are normalized horizontal sampling intervals in the rectified image; narrow them to avoid rails.

`occupancy` is the minimum colored fraction of a lane row, `min_height` filters specks, and `hold_height` separates tall bodies from chips. The detector does not identify sprites semantically. Effects, overlapping colors and masks that fragment holds can produce false positives. The tracker requires at least three associated frames and downward motion before firing; a static judgment line alone cannot trigger taps. Rapid scrolling, dense merged notes, occlusion, track rotation and camera motion can defeat this baseline.

## Verify Spice and enable local input

Use your build's configuration to enable its API TCP port, for example `-api 1337`; `-apipass` configures the optional password. Upstream also documents `-apidebug` for a headless API, but a headless instance might not expose SDVX game controls. Set the password only in an environment variable:

```powershell
$env:SPICE_API_PASSWORD = 'your-local-api-password'
.\.venv\Scripts\python.exe -m sdvxbot --config config.local.json discover
```

Discovery prints actual `[name, value, override_active]` rows. Expected upstream names are `BT-A` through `BT-D`, `FX-L`, `FX-R`, `VOL-L`, `VOL-R`. Change the config to match discovered names. Missing controls or pre-existing overrides block live startup. The client only accepts numeric loopback addresses, applies a per-request deadline, checks response IDs/errors, and never retries an uncertain write. A wrong password usually results in a timeout or protocol error.

After confirming your game is offline, verifying the dry-run, and selecting the playfield:

```powershell
.\.venv\Scripts\python.exe -m sdvxbot --config config.local.json run --live --offline-confirmed --seconds 15
```

There is a three-second countdown. Start with a short, easy local fixture and lasers disabled. The tool does not select songs, navigate menus, operate accounts, submit scores, control networking, or implement anti-cheat evasion. There is no automatic song-state classifier: end the run before leaving the playfield. A moving menu could resemble notes.

On normal stop, panic, capture failure, frame stall, or frozen capture, the program removes overrides it has touched. A background watchdog stops processing when the frame heartbeat exceeds `max_frame_gap`; repeated identical images stop after 0.5 seconds. A valid static scene can therefore stop the experiment. API requests are serialized, so cleanup may wait for an outstanding request's deadline. This is a best-effort software stop, not a hard real-time guarantee.

**If the API connection breaks, override release cannot be confirmed.** Do not assume disconnect clears a held button. Stop/restart Spice, or restore the API and explicitly reset the configured controls:

```powershell
.\.venv\Scripts\python.exe -m sdvxbot --config config.local.json reset
```

`reset` only names controls in this config. It can clear another local tool's overrides on those controls, so do not share them. No reconnect or automatic resumption occurs after a fault.

### Timing, holds and lasers

Tracks use greedy one-to-one matching within each lane and a smoothed velocity estimate. The head's predicted crossing triggers a pulse; the tail's crossing releases a hold. The loop runs up to `fps`, so timing is quantized by frame/processing/API cadence. `pulse_ms` defaults to 25; target a value observable by the game's input polling. `latency_ms` advances decisions to compensate for measured display/capture/input delay. It cannot recover an event that first becomes visible too late. Positive values fire earlier. Measure and tune in small steps; do not infer accuracy from frame rate alone.

Holds have a maximum duration and are released if tracking disappears beyond `tracking_ttl`. This favors bounded failure over maintaining an uncertain hold. Long holds beyond `max_hold_seconds` intentionally release. Prediction assumes mostly constant downward speed over a short interval; stops and sudden speed changes may miss notes. Persistent screen shake and changing perspective need a more advanced detector/recalibration.

Laser tracking samples a narrow strip above judgment. It accepts one compact colored component per side, ignores the first sample, and turns small screen-position changes into incremental normalized knob values. It releases the analog override on missing/ambiguous detections or large jumps and does not guess slams. Absolute knob phase starts from discovery and wraps within [0,1]. The **API analog write is verified; screen-to-knob gain, direction, wrapping behavior in your build, and effective laser accuracy are unverified**. There is no cursor feedback controller. Default gains are placeholders, not a calibration result.

To experiment after dry-run inspection, set `laser.enabled=true`, measure/tune the two signed `laser.gain` values on your isolated build, then explicitly add `--experimental-lasers` to the live command. Leave lasers disabled if the interpretation is uncertain. Movement and tiny reacquisition jumps remain possible even with conservative filtering.

## Optional chart comparison and synchronization

```powershell
.\.venv\Scripts\python.exe -m sdvxbot chart fixtures/example.ksh
.\.venv\Scripts\python.exe -m sdvxbot chart fixtures/structural.vox
.\.venv\Scripts\python.exe -m sdvxbot sync fixtures/sync.csv
```

The KSH subset decodes BT/FX chips and continuous holds, measure row spacing, numeric BPM changes, measure-start time signatures, and the audio offset. It handles the opposite BT/FX chip/hold digit conventions. It reads UTF-8 with optional BOM; convert legacy encodings first. Stops, scroll-speed directives and rotation directives are rejected. Mid-measure time-signature changes are rejected rather than interpreted. Lasers, spin suffixes and effects are not simulated and produce warnings. This parser is for comparison, not complete KSM emulation. The source specification is linked in `SOURCES.md`.

VOX support is deliberately **structural only**: section names, tokens, version text and raw three-part positions are preserved. No tick unit, lane mapping, duration, tempo integration, or laser flag meaning is claimed. The supplied VOX is an invented syntax fixture, not a validated game chart. Do not use its output for time alignment without a separately verified version adapter. Binary MagicaVoxel/audio VOX files are unsupported.

For synchronization, create a CSV with `chart_seconds,observed_seconds` for at least three manually matched landmarks spanning a second or more. The affine fit reports `observed = clock_scale * chart + offset`, RMS/max residual and pair count. Observed times may come from the dry-run event log or frame annotations, with a consistent time origin. It does not automatically match notes or reject mismatches. Inspect residuals and chart warnings first. This measures clock alignment, **not** physical input latency. Use a separate measured latency value in the config; the live loop never consumes chart times.

## Files and verification

- `sdvxbot/api.py`: serialized TCP/JSON/RC4 client and control ownership.
- `vision.py`, `calibrate.py`: perspective transform, geometry UI, HSV detection.
- `tracking.py`, `runtime.py`: association, scheduling, capture, panic and watchdog.
- `charts.py`: optional offline parsing and clock fit.
- `demo.py`, `fixtures/`, `tests/`: asset-free repeatable checks.
- `VERIFICATION.md`: what was actually exercised and what remains unverified.

No proprietary game data is included. Requirements specify compatible ranges; `requirements-tested.txt` records the environment used for this delivery.
