"""
ML Intent Classifier — TF-IDF + Logistic Regression
====================================================
Drop-in replacement for the old zero-shot BART classifier.

Trained on debt-collection utterances to classify into 5 production-ready
intents: PTP, Partial Payment, Refusal, Already Paid, Ambiguous.

Loads the .pkl produced by `scripts/train_intent_model.py`. If the file is
missing, falls back to a rule-based classifier so the pipeline never crashes.
"""

import os
import re
from typing import Dict, Any, List, Tuple

from src.utils import get_logger

logger = get_logger(__name__)

# Default location of the trained model (project root / models / *.pkl)
DEFAULT_MODEL_PATH = os.path.join("models", "intent_classifier.pkl")

# Canonical class labels (must match training data)
INTENT_LABELS: List[str] = [
    "PTP",
    "Partial Payment",
    "Refusal",
    "Already Paid",
    "Ambiguous",
]


# ---------------------------------------------------------------------------
# Rule-based fallback (used if .pkl is missing or fails to load)
# ---------------------------------------------------------------------------
_FALLBACK_RULES: List[Tuple[str, List[str]]] = [
    ("Already Paid", [
        r"\balready paid\b", r"\bpaid (?:it|the|last|yesterday|already|on|via)\b",
        r"\bpayment (?:was|is) (?:done|made|complete)\b",
        r"\bsettled\b", r"\bcleared (?:the )?dues?\b",
        r"\bauto[- ]?debit", r"\bhave (?:the )?receipt\b",
    ]),
    ("Refusal", [
        r"\bnot (?:going to )?pay(?:ing)?\b", r"\bwon't pay\b",
        r"\bcan(?:not|'t) pay\b", r"\bno money\b", r"\brefuse\b",
        r"\bstop (?:calling|harassing)\b", r"\bnever pay\b",
        r"\bnot interested\b", r"\bdon'?t bother\b",
    ]),
    ("Partial Payment", [
        r"\bhalf (?:now|amount|payment)\b", r"\bpart payment\b",
        r"\bpartial (?:payment|settlement)\b", r"\b(?:two|2) installments?\b",
        r"\b(?:only|just) (?:pay|manage)\b", r"\bsplit it\b",
        r"\bminimum due\b", r"\b(?:rest|remaining) (?:later|after|next)\b",
        r"\b(?:and|then) (?:remaining|rest|balance)\b",
    ]),
    ("PTP", [
        r"\bi will (?:pay|transfer|deposit|clear|settle)\b",
        r"\bi promise\b", r"\bi commit\b", r"\bdefinitely (?:pay|by)\b",
        r"\bfull (?:payment|amount)\b", r"\bentire (?:amount|outstanding|bill)\b",
        r"\bwithout fail\b", r"\btomorrow (?:by|morning|definitely)\b",
        r"\bby (?:tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|next week|salary)\b",
    ]),
]


def _rule_based(text: str) -> Dict[str, Any]:
    """Lightweight backup classifier."""
    text_lower = (text or "").lower()
    if not text_lower.strip():
        return {"intent": "Ambiguous", "confidence": 0.0, "source": "rules"}

    for label, patterns in _FALLBACK_RULES:
        for pat in patterns:
            if re.search(pat, text_lower):
                return {"intent": label, "confidence": 0.6, "source": "rules"}

    return {"intent": "Ambiguous", "confidence": 0.4, "source": "rules"}


# ---------------------------------------------------------------------------
# ML classifier
# ---------------------------------------------------------------------------
class IntentClassifier:
    """
    ML intent classifier with confidence output.

    .classify(text) returns:
        {
            "intent": str,
            "confidence": float (0-1),
            "all_scores": {label: prob, ...},
            "source": "ml" | "rules"
        }
    """

    def __init__(self, model_path: str = DEFAULT_MODEL_PATH):
        self.model_path = model_path
        self.pipeline = None
        self.labels: List[str] = INTENT_LABELS
        self._loaded = False

    # ----- Interface kept compatible with old code -----
    def load(self):
        """Lazy-load the trained pipeline. Falls back silently if missing."""
        if self._loaded:
            return

        if not os.path.exists(self.model_path):
            logger.warning(
                f"[INTENT] No trained model at {self.model_path}. "
                "Run: python scripts/train_intent_model.py  "
                "— rule-based fallback will be used."
            )
            self._loaded = True
            return

        try:
            import joblib
            self.pipeline = joblib.load(self.model_path)
            # Recover label order if available
            try:
                self.labels = list(self.pipeline.named_steps["clf"].classes_)
            except Exception:
                self.labels = INTENT_LABELS
            logger.info(
                f"[INTENT] Loaded ML model from {self.model_path}  "
                f"(classes: {self.labels})"
            )
        except Exception as e:
            logger.error(f"[INTENT] Failed to load {self.model_path}: {e}")
            self.pipeline = None

        self._loaded = True

    def classify(self, text: str) -> Dict[str, Any]:
        """
        Predict the call's overall intent.

        Backwards compat: the old code expected a STRING back. We now return a
        dict, but the pipeline / exporter / dashboard have been updated to
        accept both.
        """
        if not self._loaded:
            self.load()

        text = (text or "").strip()
        if not text:
            return {
                "intent": "Ambiguous",
                "confidence": 0.0,
                "all_scores": {lbl: 0.0 for lbl in self.labels},
                "source": "rules",
            }

        # ML path
        if self.pipeline is not None:
            try:
                probs = self.pipeline.predict_proba([text])[0]
                classes = list(self.pipeline.named_steps["clf"].classes_)
                scores = {c: float(p) for c, p in zip(classes, probs)}
                best_label = max(scores, key=scores.get)
                best_conf = scores[best_label]
                return {
                    "intent": best_label,
                    "confidence": round(float(best_conf), 3),
                    "all_scores": {k: round(float(v), 3) for k, v in scores.items()},
                    "source": "ml",
                }
            except Exception as e:
                logger.warning(f"[INTENT] ML inference failed ({e}), using rules.")

        # Rule-based fallback
        rb = _rule_based(text)
        rb["all_scores"] = {lbl: (1.0 if lbl == rb["intent"] else 0.0)
                            for lbl in self.labels}
        return rb

    def classify_turns(self, turns: List[Dict]) -> Dict[str, Any]:
        """
        Classify intent per debtor turn and return the call-level summary.
        Useful for dashboards that want turn-level intent.
        """
        if not self._loaded:
            self.load()

        per_turn = []
        all_scores_agg: Dict[str, float] = {lbl: 0.0 for lbl in self.labels}
        for t in turns or []:
            speaker_role = (t.get("role") or "").upper()
            # Only score debtor turns for "call outcome" intent
            if speaker_role and speaker_role != "DEBTOR":
                continue
            text = (t.get("text") or "").strip()
            if not text:
                continue
            result = self.classify(text)
            per_turn.append({
                "start": t.get("start"),
                "end": t.get("end"),
                "text": text,
                "intent": result["intent"],
                "confidence": result["confidence"],
            })
            # Aggregate per-class scores across debtor turns
            for lbl, sc in (result.get("all_scores") or {}).items():
                if lbl in all_scores_agg:
                    all_scores_agg[lbl] += float(sc)

        # Aggregate: pick the highest-confidence non-Ambiguous turn,
        # otherwise highest-confidence overall
        if per_turn:
            # Normalise aggregated scores to sum to 1
            total = sum(all_scores_agg.values()) or 1.0
            all_scores_norm = {k: round(v / total, 3) for k, v in all_scores_agg.items()}

            non_amb = [p for p in per_turn if p["intent"] != "Ambiguous"]
            pool = non_amb if non_amb else per_turn
            best = max(pool, key=lambda p: p["confidence"])
            return {
                "intent": best["intent"],
                "confidence": best["confidence"],
                "all_scores": all_scores_norm,
                "per_turn": per_turn,
                "source": "ml" if self.pipeline else "rules",
            }

        # No debtor turns -> fall back to whole transcript
        whole = " ".join((t.get("text") or "") for t in (turns or []))
        result = self.classify(whole)
        result["per_turn"] = []
        return result
