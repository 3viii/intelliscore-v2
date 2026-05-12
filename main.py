"""
INTELLISCORE — Command-line entry point
========================================
Usage:
    python main.py                       # mock mode (if configured)
    python main.py path/to/audio.wav     # real ASR
    python main.py call1.wav call2.wav   # batch
"""

import sys
import os
import json

from src.pipeline import AudioPipeline
from src.config import CONFIG
from src.utils import setup_logging, get_intent_label, get_intent_confidence


def _pretty(d):
    return json.dumps(d, indent=2, ensure_ascii=False, default=str)


def main():
    setup_logging()

    audio_files = sys.argv[1:]

    if not audio_files:
        print("[MAIN] No audio provided. Usage: python main.py <file.wav>")
        if CONFIG.use_api == "mock":
            print("[MAIN] Running mock demo with dummy path...")
            pipeline = AudioPipeline()
            res = pipeline.process_file("dummy.wav")
            _print_summary(res)
        return

    pipeline = AudioPipeline()  # lazy-loads resources

    for audio_file in audio_files:
        print("\n" + "=" * 60)
        print(f" Processing: {audio_file}")
        print("=" * 60)
        try:
            res = pipeline.process_file(audio_file)
            _print_summary(res)
        except Exception as e:
            print(f"[ERROR] {audio_file}: {e}")
            import traceback
            traceback.print_exc()


def _print_summary(res):
    intent_label = get_intent_label(res.get("intent"))
    intent_conf = get_intent_confidence(res.get("intent"))
    scores = res.get("scores", {})

    print("\n--- Summary ---")
    print(f"  Intent:           {intent_label}  (confidence {intent_conf*100:.0f}%)")
    print(f"  Sentiment:        {(res.get('sentiment') or {}).get('label', '—')}")
    print(f"  Speech Emotion:   {(res.get('speech_emotion') or {}).get('label_pretty', '—')}")
    print(f"  Scores:           L:{scores.get('Listening')}  "
          f"C:{scores.get('Communication')}  "
          f"P:{scores.get('Persuasion')}  "
          f"O:{scores.get('Outcome')}")
    print(f"  Entities:         {_pretty(res.get('entities', {}))}")
    print(f"  Transcript head:  {(res.get('transcript') or '')[:120]}...")
    print(f"  Outputs:          outputs/ (transcript.txt, analysis.json, report.csv, report.html)")
    print(f"  DB record:        outputs/calls.db")


if __name__ == "__main__":
    main()
