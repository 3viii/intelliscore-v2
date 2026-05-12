import re
from typing import List, Dict, Any, Union
from src.utils import get_intent_label

class ScoringEngine:
    @staticmethod
    def score(turns: List[Dict], intent: Union[str, Dict], sentiment: Dict, speech_emotion: Dict) -> Dict[str, int]:
        """
        Compute 1-5 scores for Listening, Communication, Persuasion, Outcome.
        `intent` may be a string (legacy) or a dict {"intent": ...}.
        """
        intent_label = get_intent_label(intent)
        s_label = (sentiment or {}).get("label", "UNKNOWN").upper()
        s_score = float((sentiment or {}).get("score", 0.0))
        e_label = (speech_emotion or {}).get("label_pretty", (speech_emotion or {}).get("label", "UNKNOWN")).upper()
        e_score = float((speech_emotion or {}).get("score", 0.0) or 0.0)

        all_text = " ".join(t.get("text", "") for t in turns)
        all_text_lower = all_text.lower()

        # Base scores
        listening = 3
        communication = 3
        persuasion = 3
        outcome = 3

        # Listening
        if any(ph in all_text_lower for ph in ["i understand", "okay", "sure", "let me check", "please"]):
            listening += 1
        if "sorry" in all_text_lower or "apologize" in all_text_lower:
            listening += 1

        # Communication
        num_words = len(all_text.split())
        if num_words > 80:
            communication += 1
        if s_label == "POSITIVE":
            communication += 1
        elif s_label == "NEGATIVE":
            communication -= 1

        # Persuasion
        if s_label == "POSITIVE" and s_score > 0.6:
            persuasion += 1
        if e_label in ["HAPPY", "EXCITED"] and e_score > 0.5:
            persuasion += 1
        if e_label in ["ANGRY", "SAD", "FEAR"] and e_score > 0.5:
            persuasion -= 1

        # Outcome — handle BOTH legacy labels and new ML labels
        intent_lower = intent_label.lower()
        positive_intents = (
            "full promise", "arrangement", "confirmation",  # legacy
            "ptp", "already paid",                          # new ML labels
        )
        partial_intents = ("partial promise", "partial payment")
        refusal_intents = ("refusal",)

        if any(p in intent_lower for p in positive_intents):
            outcome += 1
        if any(p in intent_lower for p in partial_intents):
            outcome += 0  # neutral; partial is neither great nor bad
        if any(p in intent_lower for p in refusal_intents):
            outcome -= 1
        if s_label == "NEGATIVE":
            outcome -= 1
        
        # If any amounts present in text -> slightly better outcome
        if any(re.search(r"\d", t.get("text", "")) for t in turns):
            outcome += 1

        def clamp(x): return max(1, min(5, int(round(x))))
        
        return {
            "Listening": clamp(listening),
            "Communication": clamp(communication),
            "Persuasion": clamp(persuasion),
            "Outcome": clamp(outcome),
        }
