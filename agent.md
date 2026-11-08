# Agent notes: HandsFreeGPT (Hi GPT)

This file orients a new coding agent to the repo. Product overview lives in `README.md`. Prefer this file for how the code actually works today.

## What this project is

A hands-free assistant for bakery staff. It answers from the business's own Markdown files and should say it does not know instead of guessing.

Demo domain is **Sunrise Bakes**, a fictional home bakery in Tampines, Singapore. Everything under `data/` is sample data, not real allergen or food-safety advice.

## Layout

| Path | Role |
| --- | --- |
| `src/ask.py` | Q&A, STT, TTS, Tkinter window, wake-word loop |
| `src/wake_word.py` | Local OpenWakeWord detection for "yo pikachu" or "hi gpt" |
| `data/*.md` | Reference documents stuffed into the system prompt |
| `tests/test_questions.md` | Manual expected answers (not pytest) |
| `models/` | ONNX wake-word files (not in git listing; required at runtime) |
| `.env` | Secrets and overrides (gitignored; copy from `.env.example`) |

There is no package layout, no `src/__init__.py`, and no automated test runner.

## How to run

```text
python src/ask.py "What is the price of a sourdough loaf?"
python src/ask.py
```

- With a question argument: print the answer and speak it with the **local** Windows voice (`speak()` default).
- With no argument: open the Tkinter window (wake word, start/stop, settings).

Setup: venv, `pip install -r requirements.txt`, `.env` with a real `OPENAI_API_KEY`.

Dependencies: `openai`, `python-dotenv`, `pyttsx3`, `sounddevice`, `soundfile`, `numpy`, `openwakeword`. The UI is stdlib `tkinter`. Audio playback of cloud TTS uses Windows `winsound`.

## How Q&A works

`load_documents()` concatenates every `data/*.md` file (sorted by filename) into one string, each prefixed with `--- filename ---`.

`ask(question, mode="work")` sends that blob in the **system** prompt plus the user question. `mode="personal"` skips `load_documents()` and uses a general-knowledge prompt. Defaults:

- model: `OPENAI_MODEL` or `gpt-4o-mini`
- `temperature=0`

Prompt rules that must stay intact unless the user asks to change them:

- Answer using **only** the provided documents
- Add helpful extras from the docs (size, quantity, ingredients, availability, ordering rules)
- Do not guess; if missing, say you do not know
- Answer directly; do not echo the question
- Example: ingredients for garlic herb focaccia should be a list, not a restated question

There is **no retrieval**. The whole corpus is inlined. Fine for the current tiny `data/` set. README M10 is proper retrieval for larger sets.

## Voice and wake word

**Local TTS:** `pyttsx3` via `speak_local()`.

**Cloud TTS:** implemented in `speak_cloud()`. OpenAI speech API (`OPENAI_TTS_MODEL` default `gpt-4o-mini-tts`, voice `OPENAI_TTS_VOICE` default `coral`), PCM written to a temp WAV (24 kHz, mono, 16-bit) and played with `winsound`. Extra API cost.

Settings radio buttons **do** persist `settings_state["voice_type"]` for the wake-word loop. CLI path does **not** read that setting; it always uses local.

**STT:** after wake word, `listen()` records 16 kHz int16 audio, stops on trailing silence (`QUESTION_SILENCE_THRESHOLD` default `0.005`, `QUESTION_END_SILENCE_SECONDS` default `0.8`), max length `RECORD_SECONDS` default `6`. Transcription uses `OPENAI_TRANSCRIBE_MODEL` default `gpt-4o-mini-transcribe`. Waiting audio for the wake word is local only and must not be sent to OpenAI.

**Wake word:** `wait_for_wake_word()` in `src/wake_word.py`. Settings chooses the phrase. Default is **"yo pikachu"**. **"hi gpt"** uses `models/hi_G_P_T.onnx`. Changing the choice while listening reloads that model. Shared feature models:

- `models/yo_pee_kah_choo.onnx` — yo pikachu
- `models/hi_G_P_T.onnx` — hi gpt
- `models/melspectrogram.onnx`
- `models/embedding_model.onnx`

Sample rate 16 kHz, chunk 1280 samples, score threshold `0.5`. Missing files raise `FileNotFoundError`. README notes ONNX was chosen over TFLite for Windows/Python; keep a TFLite copy only as a future Pi/embedded backup.

## Settings UI vs real behavior

`show_settings()` stores voice type and mode for the wake-word session. Document attach is still a placeholder.

| Control | Wired? |
| --- | --- |
| Voice: Local / Cloud | Yes, for the wake-word session |
| Wake word: yo pikachu / hi gpt | Yes. Read while listening; the detector reloads when it changes. |
| Mode: Personal / Work | Yes. Read at answer time. Personal does not load `data/`. Work uses the document prompt. Default is work. CLI typed questions stay in work mode. |
| Work: "+ Attach documents" | Button has no `command` |

Do not treat document attach or CLI cloud voice as finished features. Personal mode is finished for the wake-word window only.

## Environment variables

`.env.example` only documents `OPENAI_API_KEY` and `OPENAI_MODEL`. Code also reads:

| Variable | Default | Used for |
| --- | --- | --- |
| `OPENAI_API_KEY` | required | Chat, STT, cloud TTS |
| `OPENAI_MODEL` | `gpt-4o-mini` | Chat completions |
| `OPENAI_TTS_MODEL` | `gpt-4o-mini-tts` | Cloud TTS |
| `OPENAI_TTS_VOICE` | `coral` | Cloud TTS voice |
| `OPENAI_TRANSCRIBE_MODEL` | `gpt-4o-mini-transcribe` | Question STT |
| `RECORD_SECONDS` | `6` | Max question recording |
| `QUESTION_SILENCE_THRESHOLD` | `0.005` | End-of-speech RMS |
| `QUESTION_END_SILENCE_SECONDS` | `0.8` | Silence before stop |

Never commit `.env`. Do not put real keys in docs or sample files.

## Sample documents (`data/`)

Fictional Sunrise Bakes content. Load order is filesystem sort of `*.md`.

- `allergens.md` — per-item allergens; shared kitchen; no allergen-free guarantee
- `checklist.md` — opening/closing kitchen checklist
- `faqs.md` — location, lead times, delivery, cancellations
- `menu.md` — prices in SGD, everyday and seasonal items
- `policies.md` — deposits, pickup, delivery windows, refunds
- `recipes.md` — main ingredients, not full recipes

Facts agents often need when changing prompts or tests:

- Country sourdough boule: $12 SGD, 700 g, 24 h dough, 48 h order lead time still applies
- Custom cakes: at least 7 days, quote + deposit
- Minimum order: $30 SGD before delivery
- Cancel: 72 h full refund; 48–72 h 60-day credit; under 48 h / missed / dispatched not refundable
- Kitchen handles wheat, milk, eggs, soy, peanuts, tree nuts, sesame
- No blueberry muffin (used as a must-not-invent test)

## Tests

`tests/test_questions.md` is a **manual** checklist of 7 questions with a "correct" answer and a recorded "ai answer". There is no pytest suite.

When changing the prompt or documents, re-check at least:

1. Sourdough price (include $12 SGD and 700 g)
2. Cinnamon rolls contain wheat
3. Cannot guarantee allergen-free
4. Custom cake lead time (7 days)
5. Focaccia ingredients (direct list)
6. Blueberry muffin → do not know
7. Unlimited availability → no; small batches / while stocks last

Do not invent pytest or CI unless asked.

## Roadmap vs code (as of this catch-up)

From `README.md` New Roadmap:

- Done: M1 typed Q&A, M2 manual test set, M3 local spoken answers, M4 voice + wake word, M5 settings UI, M6 cloud voice, M7 personal mode
- Listed not done: M8 attach document sets, M9 Raspberry Pi, M10 retrieval

Code already has cloud TTS and a working voice-type toggle in the window. README M6 is still unchecked. If you implement or mark M6, update the README to match.

Still planned: work-mode document attachments (M8). Personal mode and cloud voice are implemented in the window.

## Conventions for future changes

- Keep answers grounded in `data/`; never train the model to invent bakery facts.
- Windows-first: `winsound`, local `pyttsx3`, Tkinter. Do not assume Linux audio without being asked (M9 is the Pi path).
- Wake-word audio stays local.
- Prefer small, direct edits in `src/ask.py` / `src/wake_word.py` over new frameworks.
- Do not treat UI labels as implemented behavior.
- Fictional bakery: do not present `data/` as real medical or allergen advice.
- User prefers working in code, iterating directly.
