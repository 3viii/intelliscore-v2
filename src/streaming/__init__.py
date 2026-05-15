"""
INTELLISCORE Streaming Analysis Module
======================================
Near-real-time audio streaming with chunk-based processing.

Components:
- recorder.py: Continuous microphone recording with threading
- chunk_processor.py: Incremental analysis of audio chunks
- aggregator.py: Merge chunks and final diarization
- state.py: Streamlit session state management
"""

__all__ = ["StreamingRecorder", "ChunkProcessor", "ChunkAggregator", "StreamingState"]
