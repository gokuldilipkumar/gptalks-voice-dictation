# GPTalks

Offline, system-wide push-to-talk dictation for Windows. Hold a hotkey, speak,
release — your words appear at the cursor in whatever app has focus. All
speech recognition runs locally on your CPU via
[faster-whisper](https://github.com/SYSTRAN/faster-whisper); nothing ever
leaves your machine. No accounts, no cloud, no telemetry.

**Flow:** hold `Right Ctrl` → speak → release → transcribed, tidied text is
pasted at your cursor, and your clipboard is restored to whatever it held
before.

## Architecture

The app is a small pipeline glued together in `main.py`: a global hotkey hook
starts/stops microphone capture; on stop, the recorded audio is handed to a
worker thread over a queue (so the hotkey hooks and tray UI never block),
where it is transcribed by a Whisper model loaded once at startup, passed
through a fast rule-based cleanup layer (regex only — no LLM, no network),
and finally injected into the focused window as a single paste. A system tray
icon reflects state (gray = idle, red = recording, amber = transcribing) and
hosts the runtime controls.

| Module | Responsibility |
|---|---|
| `main.py` | Entry point; wires everything together, owns the worker thread and app state |
| `gptalks/config.py` | Typed config (dataclasses) loaded from `config.yaml`, with full defaults |
| `gptalks/audio_capture.py` | Mic capture via `sounddevice` (16 kHz mono float32), RMS/duration helpers |
| `gptalks/transcriber.py` | faster-whisper wrapper (CPU, int8), model loaded once |
| `gptalks/cleanup.py` | Rule-based tidy-up: fillers, stutters, whitespace, casing, end punctuation |
| `gptalks/injector.py` | Clipboard-paste injection with clipboard save/restore; typing fallback |
| `gptalks/hotkey_listener.py` | Global hotkey hooks (`keyboard`), hold and toggle modes |
| `gptalks/tray_app.py` | `pystray` tray icon, state visuals (Pillow-drawn), menu |

## Requirements

- Windows 10/11
- Python 3.11+
- A microphone
- No GPU needed — tuned for CPU-only inference (`int8` quantization)

## Setup

```powershell
cd GPTalks
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### First run — model download

The first time you run GPTalks, faster-whisper downloads the Whisper model
(~75 MB for `base.en`) from Hugging Face. This happens once; the model is
cached under `C:\Users\<you>\.cache\huggingface\hub` and every later start is
fully offline. Expect the first launch to take a minute or two depending on
your connection; watch the console for progress.

## Run

```powershell
python main.py
```

The console prints a "ready" line once the model is loaded and a gray mic
icon appears in the system tray. Then, from any app:

1. **Hold `Right Ctrl`** — high beep, tray icon turns red: it's listening.
2. **Speak.**
3. **Release** — lower beep, icon turns amber while transcribing, then the
   text is pasted at your cursor and the icon returns to gray.

Taps shorter than ~0.3 s or recordings with no detectable speech are silently
discarded, so accidentally brushing the key does nothing.

### Tray menu

- **Enabled** — master switch. When unchecked, the keyboard hooks are removed
  entirely (the hotkey does nothing at all).
- **Cleanup transcripts** — toggle the tidy-up layer live. Off = raw Whisper
  output is pasted verbatim.
- **Open settings** — opens `config.yaml` in your default editor (creates it
  from `config.example.yaml` if it doesn't exist yet). Restart GPTalks to
  apply changes.
- **Quit**

## Configuration

GPTalks looks for `config.yaml` first in the current working directory, then
next to `main.py`. If neither exists it runs on built-in defaults (identical
to `config.example.yaml`). To customize:

```powershell
copy config.example.yaml config.yaml
```

| Key | Default | Meaning |
|---|---|---|
| `hotkey.key` | `right ctrl` | Dictation key (any `keyboard`-library key name: `f9`, `caps lock`, ...) |
| `hotkey.mode` | `hold` | `hold` = push-to-talk; `toggle` = tap to start, tap to stop |
| `whisper.model` | `base.en` | Model size; `small.en` for better accuracy (slower) |
| `whisper.language` | `en` | Language code or `auto` (ignored by `*.en` models) |
| `whisper.device` | `cpu` | Inference device |
| `whisper.compute_type` | `int8` | Quantization; `int8` is fastest on CPU |
| `whisper.cpu_threads` | `8` | Inference threads |
| `audio.min_duration_sec` | `0.3` | Discard recordings shorter than this |
| `audio.silence_rms_threshold` | `0.005` | Discard recordings quieter than this |
| `feedback.beeps` | `true` | Start/stop beeps |
| `injection.method` | `clipboard` | `clipboard` (paste) or `type` (keystrokes) |
| `injection.restore_clipboard` | `true` | Put the old clipboard back after pasting |
| `injection.paste_settle_sec` | `0.3` | Delay before clipboard restore |
| `cleanup.enabled` | `true` | Master cleanup switch |
| `cleanup.filler_words` | um, uh, ... | Fillers removed anywhere they stand alone |
| `cleanup.cautious_filler_words` | like, ... | Fillers removed only when comma-bounded |
| `cleanup.rules.*` | all `true` | Per-rule toggles (fillers, repeats, whitespace, capitalization, end punctuation) |

Changing the hotkey: set `hotkey.key` to any key name the
[`keyboard` library](https://github.com/boppreh/keyboard) understands and
restart. Changing the model: set `whisper.model` (e.g. `small.en`) and
restart — the new model downloads on that first restart if not already cached.

## Cleanup layer

After transcription, a sub-millisecond regex pass tidies the text: filler
words (`um`, `uh`, ...) are stripped, stutter repeats (`the the`) collapsed,
whitespace normalized, the first letter capitalized, and a period appended if
the text ends mid-word. Ambiguous words like "like" are only removed when
comma-bounded ("it was, like, huge"), so "I like pizza" is never touched. It
never rewrites or invents words — Whisper already produces punctuation and
casing; this is a polish, not a rewrite. Every rule and both word lists are
configurable in YAML, and the whole layer toggles live from the tray menu.

## Tests

```powershell
pip install pytest
python -m pytest tests/
```

## Troubleshooting

**The mic never picks anything up / "could not open microphone"**
Windows privacy settings may be blocking desktop apps from the microphone.
Open *Settings → Privacy & security → Microphone* and enable both *Microphone
access* and *Let desktop apps access your microphone*. Also check the correct
input device is the Windows default — GPTalks uses the system default input.

**Paste does nothing in certain windows (admin terminals, regedit, installers)**
This is Windows User Interface Privilege Isolation (UIPI): a process cannot
send synthesized input to a window running at a higher integrity level.
GPTalks does not need to run elevated for normal use, but it cannot inject
text into a window that *is* elevated (e.g. an "Run as administrator"
PowerShell) unless GPTalks itself is also run as administrator. If you
regularly dictate into elevated windows, launch GPTalks from an elevated
prompt.

**First run is very slow / seems stuck**
The Whisper model is being downloaded from Hugging Face (one-time, ~75 MB for
`base.en`, ~250 MB for `small.en`). Check the console. After the download,
model load takes a few seconds and everything runs offline. The cache lives
in `C:\Users\<you>\.cache\huggingface\hub` — delete it to force a re-download.

**Transcription quality is poor**
Switch to the larger model: set `whisper.model: small.en` in `config.yaml`
and restart. It is noticeably more accurate and still comfortably fast on a
modern CPU for short dictation. Avoid `medium`/`large` variants on CPU-only
machines — latency becomes impractical. Also try speaking a little closer to
the mic; the silence gate (`audio.silence_rms_threshold`) can be lowered if
quiet speech is being discarded.

**My old clipboard contents got pasted instead of the dictation**
A slow target app read the clipboard after GPTalks had already restored it.
Increase `injection.paste_settle_sec` (e.g. to `0.6`).
