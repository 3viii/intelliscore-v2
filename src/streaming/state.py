"""
Streamlit session state management for live streaming analysis.
Provides a stateful container for the streaming session that persists across reruns.
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class ChunkResult:
    """Result from processing a single chunk."""
    chunk_id: int
    timestamp: datetime
    duration: float  # seconds
    text: str
    start_time: float  # absolute position in merged audio
    end_time: float
    speakers: List[str] = field(default_factory=list)
    intent_scores: Dict[str, float] = field(default_factory=dict)
    sentiment: Optional[Dict[str, Any]] = None
    audio_tone: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "timestamp": self.timestamp.isoformat(),
            "duration": self.duration,
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "speakers": self.speakers,
            "intent_scores": self.intent_scores,
            "sentiment": self.sentiment,
            "audio_tone": self.audio_tone,
            "error": self.error,
        }


class StreamingState:
    """
    Manages session-level state for live streaming analysis.
    Integrates with Streamlit's st.session_state for persistence across reruns.
    """
    
    STATE_KEY = "intelliscore_live_streaming"
    
    def __init__(self):
        self.is_active = False
        self.is_recording = False
        self.start_time: Optional[datetime] = None
        self.chunks: List[ChunkResult] = []
        self.merged_audio_path: Optional[str] = None
        self.final_result: Optional[Dict[str, Any]] = None
        self.total_duration: float = 0.0
        self.error_log: List[str] = []
        
    @staticmethod
    def get_from_session() -> "StreamingState":
        """Get or create state from Streamlit session."""
        import streamlit as st
        if StreamingState.STATE_KEY not in st.session_state:
            st.session_state[StreamingState.STATE_KEY] = StreamingState()
        return st.session_state[StreamingState.STATE_KEY]
    
    @staticmethod
    def save_to_session(state: "StreamingState") -> None:
        """Save state to Streamlit session."""
        import streamlit as st
        st.session_state[StreamingState.STATE_KEY] = state
    
    def start_session(self) -> None:
        """Start a new streaming session."""
        self.is_active = True
        self.is_recording = True
        self.start_time = datetime.now()
        self.chunks = []
        self.error_log = []
        self.total_duration = 0.0
        self.final_result = None
    
    def stop_session(self) -> None:
        """Stop the streaming session."""
        self.is_recording = False
    
    def finalize_session(self) -> None:
        """Mark session as finalized (after final processing)."""
        self.is_active = False
    
    def add_chunk(self, chunk: ChunkResult) -> None:
        """Add a processed chunk to the session."""
        self.chunks.append(chunk)
        self.total_duration = chunk.end_time
    
    def add_error(self, error: str) -> None:
        """Log an error."""
        self.error_log.append(error)
    
    def reset(self) -> None:
        """Reset to initial state."""
        self.__init__()
    
    def get_live_transcript(self) -> str:
        """Build current transcript from all chunks."""
        lines = []
        for chunk in self.chunks:
            if chunk.text.strip():
                speakers_str = ", ".join(set(chunk.speakers)) if chunk.speakers else "SPEAKER"
                lines.append(f"[{speakers_str}] {chunk.text}")
        return "\n".join(lines)
    
    def get_chunk_count(self) -> int:
        """Return number of processed chunks."""
        return len(self.chunks)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize state to dict."""
        return {
            "is_active": self.is_active,
            "is_recording": self.is_recording,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "chunk_count": len(self.chunks),
            "total_duration": self.total_duration,
            "merged_audio_path": self.merged_audio_path,
            "final_result": self.final_result,
            "error_count": len(self.error_log),
            "errors": self.error_log[-5:],  # Last 5 errors
        }
