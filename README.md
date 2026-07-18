# Iris

Iris is a small assistive device that helps a user consider possible meanings
of an ambiguous sentence they have just heard. One button press turns a
recent audio window and the immediate scene into a careful, brief possible
interpretation — never a claim about what the speaker "really" meant, and
never a diagnosis of emotion, disability, or intent.

This is the laptop-first MVP: a local Tkinter application, no browser, no web
server. Raspberry Pi / Picamera2 / GPIO integration is the next stage and has
**not** been started in this repository.

## Architecture overview

```
Laptop microphone → rolling 10s buffer (RAM only) ─┐
                                                    ├─ button press ─► ElevenLabs Scribe v2 (transcript)
Laptop camera / sample image ──────────────────────┘                         │
                                                                              ▼
                                                          Backboard event thread (transcript + image)
                                                                              │
                                                                              ▼
                                                     structured JSON, validated locally
                                                                              │
                                                                              ▼
                                                Tkinter result screen  +  optional ElevenLabs TTS
```

- `app.py` — Tkinter entry point and lifecycle (`App` class).
- `controller.py` — the state machine and the single `run_interpretation()`
  entry point every trigger (software button today, GPIO later) must call.
- `desktop_ui.py` — the one Tkinter window (`DesktopUI`). The controller never
  touches individual widgets directly.
- `audio.py` — the rolling microphone buffer (`RollingAudioBuffer`) and
  `get_recent_audio()`.
- `camera.py` — replaceable `CameraProvider`s: `LaptopCameraProvider`,
  `SampleImageProvider`, and a `PiCameraProvider` stub (not implemented).
- `services/elevenlabs_client.py` — Scribe v2 transcription and TTS, isolated
  behind `transcribe_audio()` / `synthesize_result()`.
- `services/backboard_client.py` — all Backboard-specific REST calls
  (thread creation, message + image attachment, response parsing).
- `services/interpretation.py` — the model-independent `interpret_context()`
  interface; routes to a mock when credentials are absent.
- `services/output_validator.py` — validates/normalizes model output and
  produces a safe fallback on anything malformed.
- `tempfiles.py` / `logging_setup.py` / `playback.py` — small shared
  utilities for temp-file cleanup, sanitized event logging, and local MP3
  playback.
- `scripts/` — one-off setup and smoke-test scripts (see below).
- `tests/` — pytest suite (no network/hardware required).

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then fill in `.env` (see "Environment variables" below).

## Environment variables

| Variable | Required for | Notes |
|---|---|---|
| `BACKBOARD_API_KEY` | real interpretation | see "Backboard setup" |
| `BACKBOARD_ASSISTANT_ID` | real interpretation | see "Backboard setup" |
| `BACKBOARD_PROVIDER` | optional | e.g. `openai`; left blank uses Backboard's default (vision-capable) model |
| `BACKBOARD_MODEL` | optional | e.g. `gpt-4o`; left blank uses Backboard's default |
| `ELEVENLABS_API_KEY` | real transcription/TTS | see "ElevenLabs setup" |
| `ELEVENLABS_STT_MODEL` | — | default `scribe_v2` |
| `ELEVENLABS_TTS_MODEL` | — | default `eleven_flash_v2_5` |
| `ELEVENLABS_VOICE_ID` | spoken output | required only if `TTS_ENABLED=true` |
| `AUDIO_BUFFER_SECONDS` | — | rolling buffer length, default `10` |
| `CAPTURE_SECONDS` | — | reserved for future capture-window tuning |
| `CAMERA_MODE` | — | `laptop` \| `sample` \| `pi` (stub only) |
| `CAMERA_INDEX` | — | OpenCV camera index, default `0` |
| `TTS_ENABLED` | — | `true`/`false`, default `false` |
| `DEMO_MODE` | — | `true`/`false`, default `false` — see "Demo mode" |
| `SAMPLE_AUDIO_PATH` | — | default `samples/audio/sample.wav` |
| `SAMPLE_IMAGE_PATH` | — | default `samples/images/sample.jpg` |
| `MIC_SAMPLE_RATE` | — | default `16000` |
| `BACKBOARD_BASE_URL` | — | default `https://app.backboard.io/api` |
| `REQUEST_TIMEOUT_SECONDS` | — | default `30` |

Without `BACKBOARD_API_KEY`/`BACKBOARD_ASSISTANT_ID` or `ELEVENLABS_API_KEY`,
the corresponding service runs on a clearly-labeled mock behind the same
interface, so the app, tests, and demo mode all work before any credentials
exist.

## ElevenLabs setup

1. Get an API key at https://elevenlabs.io (Profile → API Keys) and set
   `ELEVENLABS_API_KEY`.
2. Run `python scripts/smoke_test_elevenlabs_stt.py` to confirm transcription
   works.
3. For spoken output, pick a voice in the ElevenLabs dashboard, copy its
   Voice ID into `ELEVENLABS_VOICE_ID`, and set `TTS_ENABLED=true`.

## Backboard setup

1. Get an API key at https://app.backboard.io (Settings → API Keys) and set
   `BACKBOARD_API_KEY`.
2. Create the saved "Iris" assistant (this loads `prompts/system_prompt.txt`
   as its system prompt) by running:
   ```bash
   python scripts/setup_backboard_assistant.py
   ```
   It prints an `assistant_id` — copy it into `BACKBOARD_ASSISTANT_ID`.
3. Run `python scripts/smoke_test_backboard.py` to confirm end-to-end.

## Running Iris

**Live mode** (real microphone + camera):
```bash
python app.py
```

**Demo mode** (prerecorded sample audio + sample image, real APIs when
configured, same controller/UI/validation/TTS path):
```bash
DEMO_MODE=true python app.py
```

## Smoke tests (Task 2)

Each checks one external dependency in isolation:

```bash
python scripts/smoke_test_microphone.py        # records, then ask a human to confirm speech is understandable
python scripts/smoke_test_camera.py             # captures one frame, ask a human to confirm it looks right
python scripts/smoke_test_elevenlabs_stt.py     # requires ELEVENLABS_API_KEY
python scripts/smoke_test_backboard.py          # requires BACKBOARD_API_KEY + BACKBOARD_ASSISTANT_ID
python scripts/smoke_test_playback.py           # plays a local MP3 (or synthesizes one if TTS is configured)
python scripts/smoke_test_end_to_end.py         # runs the real controller pipeline once, headlessly
```

## Tests

```bash
python -m pytest tests/ -v
```

The suite (41 tests) covers output validation, config loading, camera
fallback/provider-selection, controller locking and repeated-press
rejection, temp-file cleanup, demo-mode audio selection, and mock/real
routing in the interpretation service — all without needing hardware,
network access, or API keys.

## Expected failure behavior

- **No camera / capture fails** → continues with speech-only interpretation,
  `visual_context_used=false`, and the UI shows "Camera unavailable —
  interpretation used speech only." Never crashes.
- **No recent speech / silence** → a clear retry message; nothing is sent to
  ElevenLabs or Backboard.
- **Network/API failure** (auth, timeout, rate limit, connection) → a safe
  retry message on screen; sanitized details in the logs; the app keeps
  running.
- **Repeated button presses** → only one request runs at a time; the
  controller's lock rejects a second concurrent press, and the button is
  also disabled in the UI while busy.
- **Malformed Backboard output** (missing fields, bad certainty, percentage
  confidence, non-JSON, excessive length) → the local validator falls back
  to "The meaning is unclear from the available context..." at `low`
  certainty. Raw model output is never shown.
- **TTS unavailable or fails** → the visual result stays fully usable; no
  blocking error.
- **Missing sample file in demo mode** → a clear configuration error, logged
  with the missing path; the app does not crash.
- **Shutdown** → the microphone stream is stopped, the camera is always
  released after each capture, and temporary audio/image/TTS files are
  deleted.

## Privacy

- Audio is buffered **locally, in RAM only** — nothing is written to disk or
  uploaded while Iris is simply listening.
- Audio is uploaded to ElevenLabs **only** after the user presses "Interpret
  recent sentence," and only the most recent ~10-second window.
- Camera failure falls back to speech-only interpretation; no image is
  fabricated or substituted silently without saying so on screen.
- Raw microphone audio, images, transcript text, and secrets are never
  written to the logs by default (`logging_setup.py` strips these fields
  defensively even if a caller passes them).
- Every interpretation event uses a **new** Backboard thread; long-term
  memory is kept off (`memory=off` on every request).
- The output is only ever presented as a **possible** interpretation, never
  a claim of certainty about what someone meant.

## Current limitations

- Raspberry Pi, Picamera2, GPIO, and physical-button support are **not
  implemented** — `PiCameraProvider` is an interface-compatible stub that
  raises `NotImplementedError`. This is the next stage of the project.
- `samples/audio/sample.wav` and `samples/images/sample.jpg` are
  placeholders (a synthesized tone and a synthetic rainy-window image, not a
  real recording/photo). Regenerate them with
  `python scripts/generate_sample_assets.py` — once `ELEVENLABS_API_KEY` and
  `ELEVENLABS_VOICE_ID` are set it will synthesize a real spoken sample line
  instead of the placeholder tone.
- Backboard's documented API attaches images via the same multipart `files`
  field used for message-time uploads; there's no vendor documentation
  confirming a stronger same-turn "vision" guarantee beyond that, so image
  relevance can depend on the assistant choosing to use it. This is a
  documented-API limitation, not a placeholder in this codebase.
- No voice follow-up, streaming TTS, or second-model verification — all
  explicitly out of scope for this MVP.

## Troubleshooting

- **"OpenCV: not authorized to capture video"** → grant camera access to
  your terminal/Python under System Settings → Privacy & Security → Camera
  (macOS), then re-run.
- **Microphone silently produces no audio** → check System Settings →
  Privacy & Security → Microphone, and confirm no other app has an
  exclusive lock on the input device.
- **`BackboardError: ... 401 ...`** → `BACKBOARD_API_KEY` is missing/invalid.
- **`BackboardError: Backboard content was not valid JSON`** → the model
  didn't follow the JSON-only instruction; this is caught and shown as the
  safe fallback result, not a crash. If it happens often, tighten
  `prompts/system_prompt.txt` further.
- **No sound on "Hear result"** → confirm `TTS_ENABLED=true`,
  `ELEVENLABS_VOICE_ID` is set, and `afplay`/`aplay`/`winsound` is available
  on your platform.
- **Demo mode shows a configuration error** → `samples/audio/sample.wav` or
  `samples/images/sample.jpg` is missing; run
  `python scripts/generate_sample_assets.py`.
