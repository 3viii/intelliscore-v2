"""
Chunk processor for incremental analysis of streaming audio.
Processes each chunk through lightweight ASR and extracts preliminary results.
"""

import numpy as np
import tempfile
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from src.utils import get_logger
from src.audio.processing import load_audio
from src.asr.whisper_asr import WhisperASR
from src.analysis.sentiment import SentimentAnalyzer
from src.analysis.intent_classifier import IntentClassifier
from src.analysis.tone import ToneAnalyzer
from src.config import CONFIG

logger = get_logger(__name__)


class ChunkProcessor:
    """
    Processes individual audio chunks incrementally.
    Runs lightweight ASR + sentiment/intent analysis on each chunk.
    
    Does NOT run diarization (saved for final merged audio).
    """
    
    def __init__(self):
        self.asr: Optional[WhisperASR] = None
        self.sentiment: Optional[SentimentAnalyzer] = None
        self.intent: Optional[IntentClassifier] = None
        self.tone: Optional[ToneAnalyzer] = None
        self._loaded = False
    
    def load_resources(self) -> None:
        """Lazy-load lightweight models."""
        if self._loaded:
            return
        
        logger.info("[ChunkProcessor] Loading resources...")
        
        # ASR
        if CONFIG.use_api == "whisper_local":
            self.asr = WhisperASR()
        elif CONFIG.use_api == "mock":
            from src.asr.mock_asr import MockASR
            self.asr = MockASR()
        else:
            logger.warning(f"ASR method '{CONFIG.use_api}' not supported for streaming, using mock")
            from src.asr.mock_asr import MockASR
            self.asr = MockASR()
        
        # Text-based analysis
        self.sentiment = SentimentAnalyzer(CONFIG.sentiment_model)
        self.sentiment.load()
        
        self.intent = IntentClassifier()
        self.intent.load()
        
        self.tone = ToneAnalyzer(CONFIG.speech_emotion_model)
        self.tone.load()
        
        self._loaded = True
        logger.info("[ChunkProcessor] Resources loaded")
    
    def process_chunk(self,
                      audio: np.ndarray,
                      sr: int,
                      chunk_id: int,
                      start_time: float,
                      end_time: float) -> Dict[str, Any]:
        """
        Process a single audio chunk.
        
        Args:
            audio: Audio waveform (numpy array, float32)
            sr: Sample rate
            chunk_id: Sequence ID of this chunk
            start_time: Absolute start time in merged audio (seconds)
            end_time: Absolute end time in merged audio (seconds)
        
        Returns:
            Dict with keys:
                - chunk_id: Sequence ID
                - timestamp: Processing timestamp
                - text: Transcribed text
                - duration: Chunk duration in seconds
                - start_time, end_time: Absolute times
                - intent_scores: Dict of intent probabilities
                - sentiment: Sentiment label and score
                - tone: Speech emotion label and score
                - speakers: Preliminary speaker labels (empty for individual chunks)
                - audio_tone: None (for final merged analysis)
                - error: Error message if processing failed
        """
        if not self._loaded:
            self.load_resources()
        
        result = {
            "chunk_id": chunk_id,
            "timestamp": datetime.now().isoformat(),
            "text": "",
            "duration": end_time - start_time,
            "start_time": start_time,
            "end_time": end_time,
            "intent_scores": {},
            "sentiment": None,
            "tone": None,
            "speakers": [],
            "audio_tone": None,
            "error": None,
        }
        
        try:
            # Resample if needed
            if sr != 16000:
                try:
                    import librosa
                    audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                    sr = 16000
                except Exception as e:
                    logger.warning(f"[Chunk {chunk_id}] Resample failed: {e}")
            
            # Save chunk to temp WAV
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                import soundfile
                soundfile.write(tmp.name, audio, sr)
                temp_path = tmp.name
            
            try:
                # Transcribe
                text, _ = self.asr.transcribe(temp_path)
                result["text"] = text.strip()
                logger.info(f"[Chunk {chunk_id}] Transcribed: {text[:60]}...")
                
                # Lightweight text analysis
                if result["text"]:
                    # Intent
                    intent_result = self.intent.classify(result["text"])
                    if intent_result:
                        result["intent_scores"] = intent_result.get("all_scores", {})
                    
                    # Sentiment
                    sentiment_result = self.sentiment.analyze(result["text"])
                    if sentiment_result:
                        result["sentiment"] = sentiment_result
                    
                    # Tone
                    tone_result = self.tone.analyze(result["text"])
                    if tone_result:
                        result["tone"] = tone_result
            
            finally:
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        except Exception as e:
            logger.error(f"[Chunk {chunk_id}] Processing error: {e}")
            result["error"] = str(e)
        
        return result
    
    def process_audio_array(self,
                           audio: np.ndarray,
                           sr: int = 16000) -> Tuple[str, Dict[str, float], Optional[Dict], Optional[Dict]]:
        """
        Helper: Process any audio array and return transcription + metrics.
        Used during final aggregation for the merged audio.
        """
        result = {
            "text": "",
            "intent_scores": {},
            "sentiment": None,
            "tone": None,
        }
        
        try:
            # Resample if needed
            if sr != 16000:
                try:
                    import librosa
                    audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
                    sr = 16000
                except Exception as e:
                    logger.warning(f"Resample failed: {e}")
            
            # Transcribe
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                import soundfile
                soundfile.write(tmp.name, audio, sr)
                temp_path = tmp.name
            
            try:
                text, _ = self.asr.transcribe(temp_path)
                result["text"] = text.strip()
                
                if result["text"]:
                    intent_result = self.intent.classify(result["text"])
                    if intent_result:
                        result["intent_scores"] = intent_result.get("all_scores", {})
                    
                    sentiment_result = self.sentiment.analyze(result["text"])
                    if sentiment_result:
                        result["sentiment"] = sentiment_result
                    
                    tone_result = self.tone.analyze(result["text"])
                    if tone_result:
                        result["tone"] = tone_result
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        except Exception as e:
            logger.error(f"Audio array processing error: {e}")
            result["error"] = str(e)
        
        return result
