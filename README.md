# INTELLISCORE — AI Call Analysis Platform

> Production-style debt-collection call analysis: ASR + speaker diarization +
> custom-trained intent classifier + entity extraction + collector scoring +
> **🆕 LIVE STREAMING + real-time updates** + per-speaker audio tone detection,
> all surfaced through a polished Streamlit dashboard.

---

## ✨ What this project does

Given a call (uploaded, recorded live, **or streamed in real-time** 🔴), INTELLISCORE produces:

1. **Speaker-attributed transcript** (Whisper + Pyannote, with role assignment for COLLECTOR / DEBTOR)
2. **Intent classification** — *PTP · Partial Payment · Refusal · Already Paid · Ambiguous* — via a custom-trained TF-IDF + Logistic Regression model with confidence scores
3. **Entity extraction** — amounts, dates, payment modes, persons, organisations
4. **Sentiment + speech-emotion** analysis (text-based)
5. **Audio tone detection** — per-speaker emotion straight from the waveform (Collector Tone vs Debtor Tone), via `superb/wav2vec2-base-superb-er`
6. **Collector performance scores** (Listening, Communication, Persuasion, Outcome — each 1-5)
7. **Polished HTML report**, JSON, CSV and TXT exports
8. **Persistent SQLite store** of every analysed call
9. **🆕 Real-time streaming** with live dashboard updates (NEW in v2.2!)

---

## 🆕 What's new in v2.2 — Live Streaming Analysis

### 🔴 Live Streaming Mode (NEW!)
A powerful third input mode alongside **Upload** and **Record**:

- **Stream audio from microphone continuously**
- **See live updates every 4 seconds**: transcript, intent, emotion, tone
- **After stopping**: automatic final high-accuracy analysis with merged diarization
- **Same professional results** as upload/record modes

**How it works:**
1. Click **🔴 Live Analysis** tab
2. Click **▶️ Start Live Analysis**
3. Speak into microphone (watch transcript update live)
4. Click **⏹️ Stop** when done
5. Final analysis runs automatically (~1-2 min)
6. Results displayed + exported + stored

**Why this is better:**
- See analysis happening in real-time
- More responsive user experience
- Same final accuracy (merged diarization pass)
- Perfect for live call monitoring / QA

**Under the hood:**
- Chunk-based streaming (4-sec chunks)
- Incremental Whisper + intent/sentiment/tone analysis
- Final merged diarization for accuracy
- Thread-based non-blocking architecture
- Graceful error handling & fallback

**See:** [STREAMING_GUIDE.md](STREAMING_GUIDE.md) and [STREAMING_ARCHITECTURE.md](STREAMING_ARCHITECTURE.md) for full details.

---

## 🆕 What's new in v2.1 — Live mic & per-speaker audio tone

### 🎙️ Live microphone recording (Feature 1)
The Streamlit dashboard now exposes a **second tab** next to the file uploader:
"🎙️ Record from microphone". Click the mic icon, speak, click stop, then
**▶ Analyze Call** — the recording streams into the same Whisper/Pyannote
pipeline as any uploaded file.

Implementation:
- Primary path: `st.audio_input()` (built into Streamlit ≥ 1.36, **zero new dependencies**)
- Fallback: `streamlit-mic-recorder` (auto-detected if the built-in isn't available)
- Recording is saved as a temp WAV and routed through the existing pipeline — **no pipeline changes**
- Mock-mode users get a friendly warning that the recording will be ignored

### 🎚️ Per-speaker audio tone detection (Feature 2)
Tone analysis now runs **per speaker role**, not just on the whole call:

| Card                 | Source                                              |
|----------------------|-----------------------------------------------------|
| Overall Call Tone    | The full audio waveform                             |
| Collector Tone       | Audio concatenated from all COLLECTOR turns         |
| Debtor Tone          | Audio concatenated from all DEBTOR turns            |

Implementation:
- New module: `src/analysis/audio_tone.py` — `AudioToneAnalyzer` class
- Model: `superb/wav2vec2-base-superb-er` (~360 MB — much lighter than the older HuBERT-large at 1.2 GB)
- Labels: Angry · Happy · Sad · Neutral · Frustrated · Calm · …
- Returns a structured dict: `{"overall": {...}, "by_role": {"COLLECTOR": {...}, "DEBTOR": {...}}}`
- **Graceful degradation everywhere** — empty audio, missing model, inference error all return safe defaults; the pipeline never crashes
- **Auto-skipped in mock mode** (no real audio anyway)
- Per-speaker audio is sliced using the existing diarization turn timestamps — no extra ML needed
- Persisted into `analysis.json`, displayed in `report.html` and the Streamlit dashboard, stored in SQLite (`audio_tone_json` column with **idempotent migration** for older databases)

### What stayed exactly the same
The stable architecture is preserved:
- Whisper ASR · Pyannote diarization · alignment & role assignment · intent classifier · NER · sentiment · existing scoring engine · SQLite contract (backward-compatible — old rows still load)

---

## 🚀 Quick start

```bash
# 1) Install deps
pip install -r requirements.txt

# 2) (One-time) train the intent classifier  →  models/intent_classifier.pkl
python scripts/train_intent_model.py

# 3) Run the dashboard
streamlit run streamlit_app.py
# or, if `streamlit` isn't on PATH (common in Codespaces):
python -m streamlit run streamlit_app.py

# 4) For CLI use:
python main.py path/to/call.wav
```

> The pre-trained `.pkl` is shipped in `models/`, so step 2 is optional — only
> re-run it if you change `data/intent_training_data.csv`.

### Using the live microphone (new in v2.1)

1. Launch the dashboard
2. In the main panel, switch to the **🎙️ Record from microphone** tab
3. Click the mic, speak, click stop
4. Press **▶ Analyze Call**

> The browser will ask for microphone permission the first time.

---

```bash
# 1) Install deps
pip install -r requirements.txt

# 2) (One-time) train the intent classifier  →  models/intent_classifier.pkl
python scripts/train_intent_model.py

# 3) Run the dashboard
streamlit run streamlit_app.py
#    or with an auto-loaded file:
streamlit run streamlit_app.py path/to/call.wav

# Or from the CLI:
python main.py path/to/call.wav
```

> The pre-trained `.pkl` is shipped in `models/`, so step 2 is optional — only
> re-run it if you change `data/intent_training_data.csv`.

---

## 🧠 The custom intent classifier

| Metric                  | Value         |
|-------------------------|---------------|
| Model                   | TF-IDF (1-2 grams) + Logistic Regression |
| Classes                 | PTP · Partial Payment · Refusal · Already Paid · Ambiguous |
| Training samples        | 125 (25 per class, balanced) |
| Test accuracy           | **0.96** |
| Test F1 (macro)         | **0.96** |
| 5-fold CV F1 (macro)    | **0.91 ± 0.03** |
| Inference latency       | <5 ms / utterance |
| Confidence output       | ✅ yes (per-class probabilities) |

Artifacts produced by `scripts/train_intent_model.py`:

```
models/
├── intent_classifier.pkl       # the trained sklearn Pipeline
├── intent_metrics.json         # accuracy, F1, CV scores, confusion matrix
├── confusion_matrix.png        # visual confusion matrix
└── classification_report.txt   # per-class precision / recall / F1
```

At inference, the classifier returns:

```python
{
  "intent": "PTP",
  "confidence": 0.67,
  "all_scores": {
    "PTP": 0.67, "Partial Payment": 0.12, "Refusal": 0.08,
    "Already Paid": 0.07, "Ambiguous": 0.06
  },
  "source": "ml"   # or "rules" if the .pkl is missing
}
```

If `models/intent_classifier.pkl` is missing for any reason, the classifier
falls back to a hand-tuned regex layer so the pipeline never crashes.

---

## 🖥️ Dashboard tour

The Streamlit dashboard (`streamlit_app.py`) ships these sections:

| Section            | What it shows |
|--------------------|---------------|
| **Audio input** 🆕  | Two tabs: 📁 Upload audio file · 🎙️ Record from microphone |
| **Summary Cards**  | Intent + confidence · Sentiment · Collector Score · Duration · Speech Emotion |
| **Analytics**      | 4-axis radar of collector scores · Speaker talk-time donut · Intent probability bar chart |
| **Audio Tone Detection** 🆕 | Three cards: Overall Call · Collector Tone · Debtor Tone — each with detected emotion + confidence |
| **Styled Transcript** | COLLECTOR (blue) and DEBTOR (green) bubbles, with small timestamps and alignment confidence |
| **Entity Cards**   | Amount · Date · Payment Mode · Person · Organization — colour-chipped |
| **Turn Timeline**  | Tabular breakdown of every turn (start, duration, confidence) |
| **Export buttons** | TXT, JSON, CSV, HTML — one click each |
| **History panel** (sidebar) | Browse the 10 most recent calls from SQLite |
| **Loading states** | Progress bar walking through the pipeline stages |
| **Graceful errors** | Tracebacks in a collapsed expander on failure |

---

## 🗂️ Project layout

```
codereview_Call_Analysis/
├── data/
│   └── intent_training_data.csv          # 125 labelled utterances
├── models/                               # trained model + metrics
│   ├── intent_classifier.pkl
│   ├── intent_metrics.json
│   ├── confusion_matrix.png
│   └── classification_report.txt
├── scripts/
│   └── train_intent_model.py             # one-shot training script
├── src/
│   ├── analysis/
│   │   ├── intent_classifier.py          # ML intent classifier (v2.0)
│   │   ├── audio_tone.py                 # 🆕 v2.1 — per-speaker audio tone
│   │   ├── intent.py                     # legacy BART (kept for reference)
│   │   ├── sentiment.py
│   │   ├── tone.py                       # legacy whole-call HuBERT tone
│   │   └── ner.py
│   ├── asr/                              # Whisper + Mock (UNCHANGED)
│   ├── audio/                            # (UNCHANGED)
│   ├── diarization/                      # Pyannote (UNCHANGED)
│   ├── reporting/
│   │   └── exporter.py                   # v2.1 — adds tone section to HTML/JSON
│   ├── scoring/
│   │   └── engine.py                     # extended for new intent labels
│   ├── storage/
│   │   ├── __init__.py
│   │   └── db.py                         # v2.1 — added audio_tone_json column
│   ├── config.py                         # UNCHANGED
│   ├── pipeline.py                       # v2.1 — wires up audio_tone analyzer
│   └── utils.py                          # added intent-format helpers
├── outputs/                              # generated at runtime
│   ├── transcript.txt
│   ├── analysis.json
│   ├── report.csv
│   ├── report.html
│   └── calls.db                          # SQLite store
├── main.py                               # rewritten — clean CLI summary
├── streamlit_app.py                      # rewritten — pro UI
├── requirements.txt                      # updated
└── README.md                             # (this file)
```

---

## 🗄️ SQLite storage API

```python
from src.storage import db

db.init_db()                                   # idempotent
db.save_call(filename, transcript, intent, entities,
             scores, sentiment, speech_emotion,
             turns, duration_sec)               # → row id
db.get_all_calls(limit=200)                     # → List[dict]  (most-recent first)
db.get_call_by_id(call_id)                      # → dict   (with decoded JSON cols)
db.count_calls()                                # → int
db.delete_call(call_id)                         # → bool
```

The pipeline calls `save_call()` automatically on every successful run.

---

## 🔒 What was kept exactly as-is

These were stable and working — **no edits**:

- `src/asr/whisper_asr.py` — Whisper ASR
- `src/asr/mock_asr.py`
- `src/asr/interface.py`
- `src/diarization/pyannote_diarizer.py` — Pyannote pipeline
- `src/audio/processing.py` — robust audio loader
- `src/analysis/sentiment.py`, `tone.py`, `ner.py`
- `src/config.py` — env-driven config (pydantic)
- `src/pipeline._align_speakers()` — overlap-based alignment
- `src/pipeline._assign_roles()` — weighted-keyword role detection
- All tests in `tests/`

---

## 📝 Summary of changes (vs the original ZIP)

### v2.1 (this release) — Live mic + per-speaker audio tone

**New files**
- `src/analysis/audio_tone.py` — `AudioToneAnalyzer` (lightweight wav2vec2-base; per-speaker + overall; safe fallbacks)

**Modified files**
- `src/pipeline.py` — instantiates the analyzer (skipped in mock mode), runs per-speaker tone analysis after diarization, threads `audio_tone` through Exporter, SQLite, and the return dict
- `src/reporting/exporter.py` — accepts and renders an "Audio Tone Detection (per-speaker)" section in the HTML; adds `audio_tone` to `analysis.json`
- `src/storage/db.py` — added `audio_tone_json` column with **idempotent migration** for old databases; `save_call()` and `get_call_by_id()` now round-trip it
- `streamlit_app.py` — replaced the flat file uploader with tabs (📁 Upload | 🎙️ Record), uses `st.audio_input()` (with a `streamlit-mic-recorder` fallback), adds a new "🎙️ Audio Tone Detection" section with three cards (Overall / Collector / Debtor)
- `requirements.txt` — added optional `streamlit-mic-recorder` comment for older Streamlit installs

**No breaking changes**
- The pipeline contract still accepts and returns the same fields; `audio_tone` is purely additive
- Old SQLite databases auto-migrate on first run
- Mock mode still works unchanged (audio tone gracefully skipped)

---

### v2.0 — Custom ML intent classifier, polished UI, SQLite

**New files**
- `data/intent_training_data.csv` — 125-row balanced intent dataset
- `scripts/train_intent_model.py` — training pipeline (TF-IDF + LR + CV + confusion-matrix plot)
- `src/analysis/intent_classifier.py` — ML classifier with regex fallback and per-turn API
- `src/storage/__init__.py`, `src/storage/db.py` — SQLite persistence
- `models/intent_classifier.pkl`, `models/intent_metrics.json`,
  `models/confusion_matrix.png`, `models/classification_report.txt` — training artifacts

**Modified files**
- `src/pipeline.py` — swapped BART for the new ML classifier, added per-turn intent classification, duration calculation, meta-data, and SQLite persistence
- `src/scoring/engine.py` — tolerant of dict-or-string intent; added mappings for the new labels (PTP / Already Paid / Refusal / etc.)
- `src/reporting/exporter.py` — completely rewritten: rich HTML report, intent confidence in CSV, JSON enriched with intent breakdown + meta
- `src/utils.py` — added `get_intent_label()` / `get_intent_confidence()` compatibility helpers
- `streamlit_app.py` — full UI rewrite (summary cards, analytics, styled transcript, entity chips, export buttons, history panel, progress bar)
- `main.py` — cleaner CLI summary
- `requirements.txt` — added scikit-learn, joblib, pandas, plotly, matplotlib, seaborn

### Untouched
- Whisper ASR, Pyannote diarization, audio preprocessing, alignment & role assignment, config, sentiment, tone, NER, all existing tests

---

## 📸 Sample outputs & screenshots

See `samples/` for example outputs produced by the demo run:

```
samples/
├── transcript.txt    # plain-text transcript
├── analysis.json     # full structured analysis
├── report.csv        # one-row summary
├── report.html       # the polished HTML report
└── calls.db          # SQLite with one demo row
```

See `screenshots/`:

```
screenshots/
├── 01_html_report.png            # full HTML report rendering
└── 02_intent_confusion_matrix.png # classifier evaluation
```

Re-generate them any time with:

```bash
python scripts/generate_sample_outputs.py
```

---

## 🧪 Running tests

```bash
pytest tests/ -v
```

The original test suite still runs unchanged.

---

## 🛟 Troubleshooting

- **`models/intent_classifier.pkl` not found** → run `python scripts/train_intent_model.py`. Until then, the rule-based fallback kicks in automatically.
- **Pyannote auth errors** → set `INTELLISCORE_HF_TOKEN` to a valid HuggingFace token (see `src/diarization/pyannote_diarizer.py`).
- **`scikit-learn` import error** → `pip install -r requirements.txt`.
- **Mock mode** → switch the sidebar dropdown to `mock`, or `INTELLISCORE_USE_API=mock`. No real audio or models needed.

---

INTELLISCORE • AI-driven debt-collection call analysis
