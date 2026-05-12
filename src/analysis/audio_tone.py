"""
Audio Tone Analyzer (per-speaker)
==================================
Lightweight wrapper around `superb/wav2vec2-base-superb-er` to detect
speaker tone (angry / happy / sad / neutral) directly from audio.

Key features
------------
* Lighter than the existing `tone.py` (HuBERT-large 1.2 GB → wav2vec2-base 360 MB)
* Returns BOTH a call-level tone AND a per-speaker tone breakdown
  ({"COLLECTOR": {...}, "DEBTOR": {...}}), using the diarization turn list
* Graceful fallback: if the model or audio can't be loaded, returns a safe
  default and never breaks the pipeline.
* Skipped automatically in mock mode (no real audio available)

Why a new module instead of editing `tone.py`?
The existing `tone.py` is part of the stable pipeline and used elsewhere.
This new module is purely additive — it's called alongside the existing
analyzer, and the pipeline merges its per-speaker output into the results.
"""

import os
from typing import Dict, Any, List, Optional

import numpy as np

from src.utils import get_logger

logger = get_logger(__name__)

# Lightweight emotion-recognition model from the SUPERB benchmark.
# Outputs IEMOCAP-style labels: ang / hap / neu / sad
DEFAULT_MODEL = "superb/wav2vec2-base-superb-er"

# Human-friendly label mapping (also handles the larger HuBERT model's labels)
PRETTY_LABELS = {
    "ang": "Angry",
    "hap": "Happy",
    "neu": "Neutral",
    "sad": "Sad",
    "fea": "Fear",
    "dis": "Disgust",
    "sur": "Surprise",
    "exc": "Excited",
    "fru": "Frustrated",
    "cal": "Calm",
}

# Minimum number of audio samples a speaker needs before we run the model
# (avoids errors on micro-segments)
MIN_SAMPLES = 16000  # 1 second at 16 kHz

# Cap per-speaker audio at this many seconds to keep inference fast
MAX_SECONDS = 12


class AudioToneAnalyzer:
    """Per-speaker emotion recognition from raw audio."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name
        self.fe = None           # feature extractor
        self.model = None
        self.id2label = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def load(self) -> None:
        """Lazy-load the model. Silent on failure (we degrade gracefully)."""
        if self._loaded:
            return
        try:
            from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
            logger.info(f"[AUDIO_TONE] Loading model: {self.model_name}")
            self.fe = AutoFeatureExtractor.from_pretrained(self.model_name)
            self.model = AutoModelForAudioClassification.from_pretrained(self.model_name)
            self.id2label = self.model.config.id2label
            logger.info(f"[AUDIO_TONE] Loaded. Labels: {list(self.id2label.values())}")
        except Exception as e:
            logger.warning(f"[AUDIO_TONE] Failed to load {self.model_name}: {e}")
            self.fe = None
            self.model = None
        self._loaded = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def analyze(self, audio_path: str) -> Dict[str, Any]:
        """
        Call-level analysis: one tone for the whole audio.

        Returns {label, label_pretty, score} or a safe default.
        """
        if not audio_path or not os.path.exists(audio_path):
            return self._unknown("no audio file")

        if not self._loaded:
            self.load()
        if self.model is None or self.fe is None:
            return self._unknown("model unavailable")

        wav = self._load_audio(audio_path)
        if wav is None:
            return self._unknown("audio load failed")

        return self._predict(wav)

    def analyze_per_speaker(
        self,
        audio_path: str,
        turns: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Run tone analysis once per speaker role (COLLECTOR / DEBTOR), using
        the diarization turns to slice the audio.

        Returns
        -------
        {
            "overall":  {label, label_pretty, score},          # call-level
            "by_role":  {"COLLECTOR": {...}, "DEBTOR": {...}}, # per-speaker
        }

        If real audio isn't available (mock mode, missing file, model load
        failed), every entry collapses to a safe "Unknown" default — the
        pipeline NEVER crashes.
        """
        # Empty default so callers can blindly read result["by_role"]["COLLECTOR"]
        empty: Dict[str, Any] = {
            "overall": self._unknown("not analysed"),
            "by_role": {
                "COLLECTOR": self._unknown("not analysed"),
                "DEBTOR": self._unknown("not analysed"),
            },
        }

        if not audio_path or not os.path.exists(audio_path):
            logger.info("[AUDIO_TONE] Audio not available — returning defaults.")
            return empty

        if not self._loaded:
            self.load()
        if self.model is None or self.fe is None:
            logger.info("[AUDIO_TONE] Model unavailable — returning defaults.")
            return empty

        wav = self._load_audio(audio_path)
        if wav is None:
            return empty

        # Overall (whole-call) tone
        empty["overall"] = self._predict(wav)

        # Per-speaker tone: concatenate each role's turn audio
        for role in ("COLLECTOR", "DEBTOR"):
            try:
                segments = self._concat_role_audio(wav, turns, role)
                if segments is not None and len(segments) >= MIN_SAMPLES:
                    empty["by_role"][role] = self._predict(segments)
                else:
                    logger.info(
                        f"[AUDIO_TONE] {role}: insufficient audio "
                        f"({0 if segments is None else len(segments)} samples)"
                    )
            except Exception as e:
                logger.warning(f"[AUDIO_TONE] {role} prediction failed: {e}")

        return empty

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _load_audio(self, path: str) -> Optional[np.ndarray]:
        """Load mono 16 kHz audio as float32 numpy. Returns None on failure."""
        try:
            import librosa
            wav, _ = librosa.load(path, sr=16000, mono=True)
            return wav.astype(np.float32)
        except Exception as e:
            logger.warning(f"[AUDIO_TONE] librosa load failed: {e}")
            return None

    def _concat_role_audio(
        self,
        wav: np.ndarray,
        turns: List[Dict[str, Any]],
        role: str,
    ) -> Optional[np.ndarray]:
        """Concatenate the audio segments belonging to `role`."""
        sr = 16000
        clips: List[np.ndarray] = []
        for t in turns or []:
            if (t.get("role") or "").upper() != role:
                continue
            try:
                start = int(float(t.get("start", 0)) * sr)
                end = int(float(t.get("end", 0)) * sr)
                start = max(0, min(start, len(wav)))
                end = max(start, min(end, len(wav)))
                if end > start:
                    clips.append(wav[start:end])
            except (TypeError, ValueError):
                continue
        if not clips:
            return None
        out = np.concatenate(clips)
        # Cap length to MAX_SECONDS for speed
        max_len = MAX_SECONDS * sr
        if len(out) > max_len:
            out = out[:max_len]
        return out

    def _predict(self, wav: np.ndarray) -> Dict[str, Any]:
        """Run the model on a 1-D mono float32 array sampled at 16 kHz."""
        try:
            import torch
            max_len = MAX_SECONDS * 16000
            if len(wav) > max_len:
                wav = wav[:max_len]

            inputs = self.fe(wav, sampling_rate=16000, return_tensors="pt")
            with torch.no_grad():
                logits = self.model(**inputs).logits
                probs = logits.softmax(dim=-1)[0].cpu().numpy()

            best_id = int(np.argmax(probs))
            label = str(self.id2label.get(best_id, str(best_id)))
            score = float(probs[best_id])
            pretty = PRETTY_LABELS.get(label.lower(), label.title())
            return {
                "label": label,
                "label_pretty": pretty,
                "score": round(score, 3),
                "source": "ml",
            }
        except Exception as e:
            logger.warning(f"[AUDIO_TONE] Inference failed: {e}")
            return self._unknown(f"inference error: {e}")

    @staticmethod
    def _unknown(reason: str = "") -> Dict[str, Any]:
        return {
            "label": "UNKNOWN",
            "label_pretty": "Unknown",
            "score": 0.0,
            "source": "fallback",
            "reason": reason,
        }
