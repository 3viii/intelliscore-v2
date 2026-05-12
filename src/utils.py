import logging
import sys
from typing import Any, Dict, Union

def setup_logging(level=logging.INFO):
    """
    Configure logging for the application.
    """
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def get_logger(name: str):
    return logging.getLogger(name)


# ---------------------------------------------------------------------------
# Compatibility helpers: intent can be a plain string (legacy) or a dict
# {"intent": str, "confidence": float, "all_scores": {...}, "source": str}.
# These helpers let every downstream consumer stay tolerant.
# ---------------------------------------------------------------------------
def get_intent_label(intent: Union[str, Dict[str, Any], None]) -> str:
    """Return just the label string ('PTP', 'Refusal', ...)."""
    if intent is None:
        return "Ambiguous"
    if isinstance(intent, str):
        return intent
    if isinstance(intent, dict):
        return str(intent.get("intent") or intent.get("label") or "Ambiguous")
    return "Ambiguous"


def get_intent_confidence(intent: Union[str, Dict[str, Any], None]) -> float:
    """Return the confidence in [0, 1] (0 if unknown)."""
    if isinstance(intent, dict):
        try:
            return float(intent.get("confidence") or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return 0.0
