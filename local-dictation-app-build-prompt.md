# Build Prompt — Local Voice-to-Text Dictation App (a "Wispr Flow" clone)

## Role & goal
You are building a **system-wide, offline-first dictation app for Windows**, similar to Wispr Flow. I hold a hotkey, speak, release, and the transcribed (and lightly cleaned-up) text is inserted **at my cursor in whatever app is currently focused**. All speech processing runs **locally** for privacy and low latency — no cloud STT, no account.

## Target environment
- OS: Windows 10/11
- Language: Python 3.11+
- CPU: 12th Gen Intel Core i7-1255U (10 cores / 12 logical). **No NVIDIA GPU** — this is a **CPU-only** build. Use faster-whisper with `device="cpu"` and `compute_type="int8"`. Set `cpu_threads` to a sensible value for this chip (e.g. 8) and expose it in config.
- App name: **GPTalks**

## Core requirements (MVP — build this first, end to end)
1. **Global push-to-talk hotkey** (default: hold `Right Ctrl`, configurable). While held, capture mic audio; on release, stop and transcribe. Also support a **toggle mode** (tap to start / tap to stop).
2. **Local speech-to-text** using **faster-whisper** (CTranslate2). **Default model `base.en`** (best latency/quality on this CPU); `small.en` as the optional quality-up. Do **not** default to `medium`/`large` — they're too slow for real-time feel on a U-series CPU. Configurable in config. Load the model **once at startup**, never per utterance.
3. **Text injection**: insert the final text at the current cursor position in the active window. Prefer the **clipboard-paste method** (reliable + full Unicode); keep a keystroke-typing fallback. Preserve the user's existing clipboard.
4. **System tray icon** showing status (idle / recording / transcribing) with menu items: enable/disable, open settings, quit.
5. **Config file** (YAML) for: hotkey, whisper model size, language, device, compute_type, cpu_threads, and cleanup on/off.
6. **Audio/visual feedback** so I know when it's actually listening (subtle start/stop sound or a distinct tray state).

## Cleanup layer — fast, rule-based, zero added latency (no LLM)
- **No LLM, no Ollama, no network calls.** Cleanup must be pure local string processing that runs in well under a millisecond so it adds no perceptible latency to the paste.
- After raw transcription, apply a lightweight rule-based pass that: strips filler words and disfluencies ("um", "uh", "er", stray "like"/"you know"), collapses repeated words from stutters/false starts, trims leading/trailing whitespace, capitalizes the first letter, and ensures sensible end punctuation. faster-whisper already produces punctuation and casing, so this is a light tidy-up, not a rewrite.
- Make the filler-word list and each rule **configurable / individually toggleable**, and keep the whole cleanup step toggleable at runtime (tray menu + config). When off, paste the raw transcription verbatim.
- Never change meaning, never add or invent words. When in doubt, leave the text as-is.
- Pipeline stays single-paste: transcribe → tidy → paste once.

## Architecture
- Modular files: `audio_capture`, `transcriber`, `cleanup`, `injector`, `hotkey_listener`, `tray_app`, `config`, `main`.
- Run transcription **off the hotkey/UI thread** so the app stays responsive.
- Gracefully ignore empty or very-short audio (accidental taps).
- No busy-wait; release the mic cleanly on stop.

## Suggested libraries (pick the most reliable Windows combo and justify briefly)
`faster-whisper` (STT) · `sounddevice` + `numpy` (mic) · `pynput` or `keyboard` (global hotkey) · `pyperclip` + `keyboard`/`pynput` (paste) · `pystray` + `Pillow` (tray) · `pyyaml` (config). Flag anything needing admin rights.

## Non-goals (keep the MVP tight)
No cloud STT, no login/accounts, no always-on continuous listening, no mobile, no heavy GUI beyond the tray + a simple settings window.

## Deliverables
1. Working code in a clean repo structure with the modules above.
2. `requirements.txt`, `config.example.yaml`, and a **README** covering: setup, model/config options, first-run model download, default hotkey, and troubleshooting (mic permissions; paste failing in elevated/admin windows).
3. Comments only where logic is non-obvious.
4. Structure the repo and README to portfolio quality (clear module boundaries, a short architecture note) so it can double as a showcase project.

## Acceptance criteria
- One command to run. Hold hotkey → speak a sentence → release → text appears at cursor in **Notepad, a browser text box, and VS Code**. Rough latency target on this CPU: raw transcription (`base.en`) in ~1–3s, with the rule-based cleanup adding no perceptible delay.
- Cleanup **on** removes fillers and tidies punctuation without altering meaning or adding words; **off** pastes the raw transcription verbatim.
- Changing the whisper model in config and restarting works.
- Disabling from the tray stops the hotkey from triggering.

## Working style
- First, propose the **repo structure** and confirm the library choices, then implement.
- Assume CPU-only (no CUDA). Implement the MVP end to end before any stretch features.
- Call out Windows-specific gotchas explicitly (e.g. pasting into apps running as administrator).

## Stretch (only after MVP is solid)
- Context-aware formatting (email vs. chat vs. code), custom vocabulary / replacements, per-app profiles, streaming/partial transcription, and a global "undo last insert."
