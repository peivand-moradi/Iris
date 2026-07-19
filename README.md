# Iris

Iris is a small assistive device that helps a user consider possible meanings
of an ambiguous sentence they have just heard. One button press turns a
recent audio window and the immediate scene into a careful, brief possible
interpretation — never a claim about what the speaker "really" meant, and
never a diagnosis of emotion, disability, or intent.

This is a local Tkinter application, no browser, no web server. The laptop
workflow (Tasks 1–12) is the first milestone; Raspberry Pi 5 / Picamera2 /
GPIO integration (Task 13) builds on it without changing the AI pipeline —
see "Raspberry Pi deployment" below.

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
  entry point every trigger (software button, and the GPIO button on the
  Pi) must call.
- `desktop_ui.py` — the one Tkinter window (`DesktopUI`). The controller never
  touches individual widgets directly.
- `audio.py` — the rolling microphone buffer (`RollingAudioBuffer`) and
  `get_recent_audio()`.
- `camera.py` — replaceable `CameraProvider`s: `LaptopCameraProvider`,
  `SampleImageProvider`, and `PiCameraProvider` (Task 13, Picamera2-backed).
- `trigger.py` — `GPIOButtonTrigger` (Task 13): calls the same
  `run_interpretation()` path the software button uses.
- `services/elevenlabs_client.py` — Scribe v2 transcription and TTS, isolated
  behind `transcribe_audio()` / `synthesize_result()`.
- `services/backboard_client.py` — all Backboard-specific REST calls
  (thread creation, message + image attachment, response parsing).
- `services/interpretation.py` — the model-independent `interpret_context()`
  interface; routes to a mock when credentials are absent.
- `services/output_validator.py` — validates/normalizes model output and
  produces a safe fallback on anything malformed.
- `services/conversation.py` / `services/conversation_validator.py` — the
  "Let's talk about it" spoken follow-up conversation (see "Conversation
  mode" below): a separate Backboard assistant/prompt, same
  mock-when-unconfigured and validate-or-fallback philosophy as interpretation.
- `tempfiles.py` / `logging_setup.py` / `playback.py` — small shared
  utilities for temp-file cleanup, sanitized event logging, and local audio
  playback (WAV, so it also works via `winsound` on Windows).
- `scripts/` — one-off setup and smoke-test scripts (see below).
- `tests/` — pytest suite (no network/hardware required).

## Installation

**Windows (PowerShell):**
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

**macOS / Linux:**
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
| `BACKBOARD_CONVERSATION_ASSISTANT_ID` | real conversation mode | see "Conversation mode" |
| `BACKBOARD_PROVIDER` | optional | e.g. `openai`; left blank uses Backboard's default (vision-capable) model |
| `BACKBOARD_MODEL` | optional | e.g. `gpt-4o`; left blank uses Backboard's default |
| `ELEVENLABS_API_KEY` | real transcription/TTS | see "ElevenLabs setup" |
| `ELEVENLABS_STT_MODEL` | — | default `scribe_v2` |
| `ELEVENLABS_TTS_MODEL` | — | default `eleven_flash_v2_5` |
| `ELEVENLABS_VOICE_ID` | spoken output | required only if `TTS_ENABLED=true` |
| `AUDIO_BUFFER_SECONDS` | — | rolling buffer length, default `10` |
| `CAPTURE_SECONDS` | — | reserved for future capture-window tuning |
| `CONVERSATION_ANSWER_WAIT_SECONDS` | — | reply/voice-trigger listen wait, default `4` |
| `CAMERA_MODE` | — | `laptop` \| `sample` \| `pi` (Task 13, requires Raspberry Pi OS) |
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

## Conversation mode

When `TTS_ENABLED=true`, Iris speaks the result summary aloud as soon as it's
ready (not just shown on screen), then listens once for the user saying a
trigger phrase — "let's talk", "lets talk" (STT often drops the apostrophe),
or "let us talk" — anywhere in what they say next. If it hears one, it starts
a brief, entirely spoken back-and-forth about that interpretation, driven by
a **second** Backboard assistant (`BACKBOARD_CONVERSATION_ASSISTANT_ID`, its
own prompt at `prompts/conversation_system_prompt.txt`) — ElevenLabs stays
STT+TTS only, never the model doing the conversing. The **"Let's talk about
it"** button next to the result does the same thing on demand, so both a
voice cue and a manual click work.

Set it up the same way as the interpretation assistant:
```bash
python scripts/setup_conversation_assistant.py
```
It prints an `assistant_id` — copy it into `BACKBOARD_CONVERSATION_ASSISTANT_ID`.

Unlike the one-shot interpretation flow (a brand-new Backboard thread with
`memory=off` per button press), a conversation reuses **one** thread for all
of its turns so the model has context of what was already asked/answered —
each message also restates the full conversation-so-far, so this works
regardless of what `memory=off` does server-side. This is a deliberate,
scoped exception to the interpretation flow's privacy design; the thread is
discarded — never revisited — once the conversation ends.

Each turn: Iris speaks the model's message via TTS, waits
`CONVERSATION_ANSWER_WAIT_SECONDS`, then captures+transcribes the reply from
the same rolling mic buffer used everywhere else (no new capture primitive,
no on-screen multiple-choice options — everything is spoken and answered by
voice) and sends it back on the same thread. The conversation ends when the
model sets `conversation_over: true`, or the user presses **Dismiss** at any
point (ends after the current turn finishes, not instantly — the same as any
other busy state in this app). While a conversation is active, pressing
"Interpret recent sentence" (including the GPIO button) is ignored rather
than raced against the shared mic/camera.

## Raspberry Pi deployment (Task 13)

The laptop MVP is the first milestone; this stage replaces the laptop camera
and software button with a Raspberry Pi 5 + Pi Camera + physical button,
**without changing any AI pipeline code** (`controller.py`,
`services/*.py`, `models.py`, `desktop_ui.py` are untouched — only the
camera provider and trigger are swapped, exactly as the plan requires).

These steps must be run **on the Pi itself** — `picamera2` and `gpiozero`
are Raspberry Pi–specific and cannot be installed or tested on a laptop.

1. Flash Raspberry Pi OS Bookworm, 64-bit, and confirm the Pi has network access.
2. Test the Pi Camera and display independently (e.g. `libcamera-hello`)
   before involving this app at all.
3. Clone the repository onto the Pi.
4. Install the system Picamera2 package, then create a venv that can see it:
   ```bash
   sudo apt install -y python3-picamera2 python3-libcamera
   python3 -m venv --system-site-packages .venv
   source .venv/bin/activate
   pip install -r requirements-pi.txt
   cp .env.example .env
   ```
   (`requirements-pi.txt` installs everything in `requirements.txt` plus
   `gpiozero`; `picamera2` comes from the apt package above, not pip.)
5. First run with `CAMERA_MODE=sample` in `.env` to confirm the app itself
   starts correctly on the Pi before involving the camera.
6. Run `python scripts/smoke_test_pi_camera.py` to confirm the Pi Camera
   captures and decodes a frame, then set `CAMERA_MODE=pi` in `.env`.
7. Wire a push-button between a GPIO pin (BCM numbering, default pin 17 —
   physical pin 11) and a **GND** pin. No external resistor is needed;
   `gpiozero.Button` uses the Pi's internal pull-up by default.
8. Run `python scripts/smoke_test_gpio_button.py` and press the button to
   confirm it's detected, then set `TRIGGER_MODE=gpio` in `.env`.
9. Run `python app.py` — the physical button now calls the exact same
   `run_interpretation()` the software button always called.

Keep the laptop microphone or another externally available USB microphone
until a Pi-compatible microphone is set up — `audio.py` is unchanged and
still just opens the default input device via `sounddevice`.

## Running Iris

**Live mode** (real microphone + camera):
```bash
python app.py
```

**Demo mode** (prerecorded sample audio + sample image, real APIs when
configured, same controller/UI/validation/TTS path):

macOS/Linux: `DEMO_MODE=true python app.py`

PowerShell: `$env:DEMO_MODE="true"; python app.py`

(Or just set `DEMO_MODE=true` in `.env` and run `python app.py` normally on
any platform.)

## Smoke tests (Task 2)

Each checks one external dependency in isolation:

```bash
python scripts/smoke_test_microphone.py        # records, then ask a human to confirm speech is understandable
python scripts/smoke_test_camera.py             # captures one frame, ask a human to confirm it looks right
python scripts/smoke_test_elevenlabs_stt.py     # requires ELEVENLABS_API_KEY
python scripts/smoke_test_backboard.py          # requires BACKBOARD_API_KEY + BACKBOARD_ASSISTANT_ID
python scripts/smoke_test_playback.py           # plays a local audio file (or synthesizes one if TTS is configured)
python scripts/smoke_test_end_to_end.py         # runs the real controller pipeline once, headlessly
```

Task 13 (Raspberry Pi only — see "Raspberry Pi deployment" above):

```bash
python scripts/smoke_test_pi_camera.py          # captures one frame via Picamera2
python scripts/smoke_test_gpio_button.py        # confirms a physical button press is detected
```

## Tests

```bash
python -m pytest tests/ -v
```

The suite (91 tests) covers output validation, image MIME-type detection and
graceful text-only fallback when an image can't be attached, config loading,
camera fallback/provider-selection — including the
Windows DirectShow backend selection, the capture retry loop, and a mocked
Picamera2 for `PiCameraProvider` — the GPIO trigger (mocked `gpiozero`),
controller locking and repeated-press rejection (including conversation
mode's shared lock), temp-file cleanup, demo-mode audio selection, and
mock/real routing in both the interpretation and conversation services — all
without needing hardware, network access, or API keys.

## Expected failure behavior

- **No camera / capture fails** → continues with speech-only interpretation
  (`image_captured=false`, `visual_context_used=false`), and the UI shows
  "Camera unavailable — interpretation used speech only." Never crashes. The
  laptop camera capture itself retries briefly (up to ~1s) before giving up,
  and uses the DirectShow backend on Windows for more reliable `cv2` opens.
- **Image captured but not relevant** → distinct from a camera failure: the
  photo was taken and inspected, but the model determined it didn't
  contribute to the interpretation (`image_captured=true`,
  `visual_context_used=false`). The UI shows "Image captured and inspected,
  but it did not contribute to this interpretation" instead of the
  camera-unavailable message.
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
- **Malformed conversation-turn output, or a failed turn** (bad transcription,
  Backboard error) → the conversation ends immediately with a safe spoken
  closing line rather than retrying; never silent, never raw model output.
- **"Interpret recent sentence" pressed while a conversation is active**
  (including the GPIO button) → ignored rather than raced against the shared
  mic/camera; logged, not shown as an error.
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
  memory is kept off (`memory=off` on every request). Conversation mode is
  the one deliberate, time-boxed exception: one thread persists for the
  life of a single conversation, then is discarded and never revisited.
- The output is only ever presented as a **possible** interpretation, never
  a claim of certainty about what someone meant.

## Current limitations

- `PiCameraProvider` and `GPIOButtonTrigger` (Task 13) are implemented and
  unit-tested with a mocked `picamera2`/`gpiozero`, but have **not been
  exercised against real Raspberry Pi hardware** — that verification can
  only happen on the Pi itself, via `scripts/smoke_test_pi_camera.py` and
  `scripts/smoke_test_gpio_button.py`. See "Raspberry Pi deployment" above.
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
- No streaming TTS or second-model verification — out of scope for this MVP.
- Conversation mode's listening window is a fixed wait
  (`CONVERSATION_ANSWER_WAIT_SECONDS`), not real voice-activity detection —
  it doesn't know when the user has actually finished answering. A failed
  turn (bad transcription, Backboard error) ends the conversation immediately
  rather than retrying once locally; a bounded retry would likely feel
  better but isn't built yet. There's also a theoretical mic/speaker-bleed
  edge case: TTS played over speakers could faintly leak into the start of
  the next capture window on some hardware.

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
