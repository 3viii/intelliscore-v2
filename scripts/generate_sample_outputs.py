"""
Generate sample outputs for demo / review without needing audio.
Runs: intent ML + scoring + exporter + SQLite — produces outputs/ artifacts.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Reuse the MockASR's transcript shape
turns = [
    {"speaker": "Speaker 1", "role": "COLLECTOR", "speaker_id": "Speaker 1",
     "start": 0.0, "end": 5.0, "confidence": 0.95,
     "text": "Hello, this is John from HDFC Bank. Am I speaking with Mr. Sharma?"},
    {"speaker": "Speaker 2", "role": "DEBTOR", "speaker_id": "Speaker 2",
     "start": 5.5, "end": 7.0, "confidence": 0.93,
     "text": "Yes, speaking."},
    {"speaker": "Speaker 1", "role": "COLLECTOR", "speaker_id": "Speaker 1",
     "start": 7.5, "end": 12.0, "confidence": 0.92,
     "text": "Sir, this call is regarding your overdue payment of 15000 rupees."},
    {"speaker": "Speaker 2", "role": "DEBTOR", "speaker_id": "Speaker 2",
     "start": 12.5, "end": 16.0, "confidence": 0.94,
     "text": "I will pay the full amount next week by UPI."},
    {"speaker": "Speaker 1", "role": "COLLECTOR", "speaker_id": "Speaker 1",
     "start": 16.5, "end": 20.0, "confidence": 0.95,
     "text": "Okay, please do so by Monday. Thank you."},
]
transcript = "\n".join(f"[{t['role']}] {t['text']}" for t in turns)
entities = {
    "Amount": ["15000"], "Date": ["Monday", "next week"],
    "Mode": ["UPI"], "PERSON": ["John", "Sharma"],
    "ORG": ["HDFC Bank"], "LOC": [],
}
sentiment = {"label": "POSITIVE", "score": 0.78}
speech_emotion = {"label": "neu", "label_pretty": "Neutral", "score": 0.61}

# Synthesised audio_tone for the demo (matches the shape returned by
# AudioToneAnalyzer.analyze_per_speaker — included so report.html and the DB
# show the new "Audio Tone Detection" section even in mock/demo mode).
audio_tone = {
    "overall":  {"label": "neu", "label_pretty": "Neutral",  "score": 0.72, "source": "ml"},
    "by_role": {
        "COLLECTOR": {"label": "neu", "label_pretty": "Neutral", "score": 0.81, "source": "ml"},
        "DEBTOR":    {"label": "hap", "label_pretty": "Happy",   "score": 0.55, "source": "ml"},
    },
}

from src.analysis.intent_classifier import IntentClassifier
from src.scoring.engine import ScoringEngine
from src.reporting.exporter import Exporter
from src.storage import db as dbmod

# Step 1: intent
clf = IntentClassifier()
clf.load()
intent_res = clf.classify_turns(turns)
print("Intent:", intent_res["intent"], "  Confidence:", f"{intent_res['confidence']:.2f}")

# Step 2: scores
scores = ScoringEngine.score(turns, intent_res, sentiment, speech_emotion)
print("Scores:", scores)

# Step 3: export
Exporter.save(
    transcript=transcript, turns=turns, diarized=[],
    intent=intent_res, entities=entities, scores=scores,
    sentiment=sentiment, speech_emotion=speech_emotion,
    audio_tone=audio_tone,
    out_dir="outputs",
    meta={"filename": "demo_call.wav", "duration_sec": 20.0, "call_id": "demo_001"},
)

# Step 4: SQLite
call_id = dbmod.save_call(
    filename="demo_call.wav",
    transcript=transcript, intent=intent_res, entities=entities,
    scores=scores, sentiment=sentiment, speech_emotion=speech_emotion,
    turns=turns, duration_sec=20.0, audio_tone=audio_tone,
)
print(f"\nSaved to outputs/, DB row id={call_id}")
print("Files:")
for f in sorted(os.listdir("outputs")):
    p = os.path.join("outputs", f)
    if os.path.isfile(p):
        print(f"  outputs/{f}  ({os.path.getsize(p)} bytes)")
