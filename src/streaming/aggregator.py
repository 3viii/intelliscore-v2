"""
Chunk aggregator for post-streaming final analysis.
Merges audio chunks, runs final diarization, aligns speakers, aggregates results.
"""

import numpy as np
import tempfile
import os
from typing import Dict, List, Any, Optional, Tuple
import logging

import soundfile as sf
from src.utils import get_logger
from src.audio.processing import load_audio
from src.asr.whisper_asr import WhisperASR
from src.diarization.pyannote_diarizer import PyannoteDiarizer
from src.analysis.sentiment import SentimentAnalyzer
from src.analysis.intent_classifier import IntentClassifier
from src.analysis.tone import ToneAnalyzer
from src.analysis.audio_tone import AudioToneAnalyzer
from src.analysis.ner import NERExtractor
from src.scoring.engine import ScoringEngine
from src.reporting.exporter import Exporter
from src.config import CONFIG

logger = get_logger(__name__)


class ChunkAggregator:
    """
    Aggregates chunk results after streaming stops.
    
    Process:
    1. Merge all chunk audio files into one
    2. Run FINAL Pyannote diarization on merged audio (high accuracy)
    3. Align speakers to merged transcription
    4. Aggregate intent scores by averaging
    5. Aggregate emotion/tone scores
    6. Run full analysis pipeline
    7. Generate final report
    8. Store in SQLite
    """
    
    def __init__(self):
        self.asr: Optional[WhisperASR] = None
        self.diarizer: Optional[PyannoteDiarizer] = None
        self.sentiment: Optional[SentimentAnalyzer] = None
        self.intent: Optional[IntentClassifier] = None
        self.tone: Optional[ToneAnalyzer] = None
        self.audio_tone: Optional[AudioToneAnalyzer] = None
        self.ner: Optional[NERExtractor] = None
        self.scoring: Optional[ScoringEngine] = None
        self.exporter: Optional[Exporter] = None
        self._loaded = False
    
    def load_resources(self) -> None:
        """Load full pipeline resources."""
        if self._loaded:
            return
        
        logger.info("[ChunkAggregator] Loading full pipeline resources...")
        
        # ASR & Diarization
        if CONFIG.use_api == "whisper_local":
            self.asr = WhisperASR()
            self.diarizer = PyannoteDiarizer()
            self.diarizer.load()
        elif CONFIG.use_api == "mock":
            from src.asr.mock_asr import MockASR
            self.asr = MockASR()
            self.diarizer = None
        else:
            logger.warning(f"ASR method '{CONFIG.use_api}' not supported, using mock")
            from src.asr.mock_asr import MockASR
            self.asr = MockASR()
            self.diarizer = None
        
        # Analysis
        self.sentiment = SentimentAnalyzer(CONFIG.sentiment_model)
        self.sentiment.load()
        
        self.intent = IntentClassifier()
        self.intent.load()
        
        self.tone = ToneAnalyzer(CONFIG.speech_emotion_model)
        self.tone.load()
        
        # Audio tone (per-speaker)
        if CONFIG.use_api != "mock":
            self.audio_tone = AudioToneAnalyzer()
            self.audio_tone.load()
        else:
            self.audio_tone = None
        
        self.ner = NERExtractor(CONFIG.ner_model)
        self.ner.load()
        
        # Scoring and export
        self.scoring = ScoringEngine()
        self.exporter = Exporter()
        
        self._loaded = True
        logger.info("[ChunkAggregator] Resources loaded")
    
    def merge_audio_chunks(self,
                          chunks: List[np.ndarray],
                          sr: int = 16000) -> np.ndarray:
        """
        Merge audio chunks into single audio array.
        
        Args:
            chunks: List of audio arrays (numpy)
            sr: Sample rate
        
        Returns:
            Merged audio array
        """
        if not chunks:
            logger.warning("No chunks to merge")
            return np.array([])
        
        # Ensure all chunks are 1D
        clean_chunks = []
        for chunk in chunks:
            if isinstance(chunk, np.ndarray):
                if chunk.ndim > 1:
                    chunk = chunk.squeeze()
                clean_chunks.append(chunk)
        
        merged = np.concatenate(clean_chunks)
        logger.info(f"[Aggregator] Merged {len(clean_chunks)} chunks into {len(merged)/sr:.1f}s audio")
        return merged
    
    def aggregate_results(self,
                         chunk_results: List[Dict[str, Any]],
                         merged_audio_path: str) -> Dict[str, Any]:
        """
        Aggregate chunk results and run final full analysis.
        
        Args:
            chunk_results: List of chunk processing results
            merged_audio_path: Path to merged audio WAV file
        
        Returns:
            Final analysis result (full pipeline output)
        """
        if not self._loaded:
            self.load_resources()
        
        logger.info(f"[Aggregator] Starting final aggregation ({len(chunk_results)} chunks)")
        
        # Build intermediate merged transcript
        merged_text = " ".join(c.get("text", "") for c in chunk_results if c.get("text"))
        logger.info(f"[Aggregator] Merged transcript length: {len(merged_text)} chars")
        
        # 1. Re-transcribe merged audio (for alignment)
        transcript, asr_turns = self.asr.transcribe(merged_audio_path)
        logger.info(f"[Aggregator] Transcribed merged audio: {len(asr_turns)} turns")
        
        # 2. Run diarization on merged audio (FINAL, high-accuracy pass)
        final_turns = asr_turns
        diarized_segments = []
        
        if self.diarizer and CONFIG.use_api == "whisper_local":
            logger.info("[Aggregator] Running FINAL Pyannote diarization on merged audio...")
            
            try:
                # Prepare clean 16kHz mono audio for diarization
                wav, sr = load_audio(merged_audio_path, target_sr=16000)
                
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp_path = tmp.name
                    sf.write(tmp_path, wav, sr)
                
                diarized_segments = self.diarizer.diarize(tmp_path)
                os.remove(tmp_path)
                
                logger.info(f"[Aggregator] Diarization complete: {len(diarized_segments)} segments")
                
                # Align speakers
                from src.pipeline import AudioPipeline
                pipeline = AudioPipeline()
                final_turns = pipeline._align_speakers(asr_turns, diarized_segments)
                
                # Reconstruct with speakers
                transcript = "\n".join([f'[{t["speaker"].upper()}] {t["text"]}' for t in final_turns])
            
            except Exception as e:
                logger.error(f"[Aggregator] Diarization failed: {e}")
                logger.warning("[Aggregator] Proceeding with ASR turns only")
        
        # 3. Aggregate intent scores (average across chunks)
        aggregated_intent_scores = self._aggregate_intent_scores(chunk_results)
        logger.info(f"[Aggregator] Aggregated intent scores: {aggregated_intent_scores}")
        
        # 4. Full analysis on merged audio
        logger.info("[Aggregator] Running full analysis pipeline...")
        
        result = {
            "transcript": transcript,
            "turns": final_turns,
            "diarized_segments": diarized_segments,
            "meta": {
                "mode": "live_streaming",
                "chunk_count": len(chunk_results),
                "total_duration": sum(c.get("duration", 0) for c in chunk_results),
                "aggregated_from_chunks": True,
            }
        }
        
        # Sentiment (merged text)
        sentiment_result = self.sentiment.analyze(merged_text) if merged_text else {}
        result["sentiment"] = sentiment_result
        
        # Intent (merged text + aggregated scores)
        intent_result = self.intent.classify(merged_text) if merged_text else {}
        # Override all_scores with aggregated
        if aggregated_intent_scores:
            intent_result["all_scores"] = aggregated_intent_scores
        result["intent"] = intent_result
        
        # Tone (merged text)
        tone_result = self.tone.analyze(merged_text) if merged_text else {}
        result["tone"] = tone_result
        
        # Audio tone (per-speaker on merged audio)
        audio_tone_result = {}
        if self.audio_tone and final_turns:
            try:
                audio_tone_result = self.audio_tone.analyze_per_speaker(merged_audio_path, final_turns)
            except Exception as e:
                logger.warning(f"[Aggregator] Audio tone analysis failed: {e}")
                audio_tone_result = {"overall": {}, "by_role": {}}
        result["audio_tone"] = audio_tone_result
        
        # NER (merged text)
        entities = self.ner.extract(merged_text) if merged_text else {}
        result["entities"] = entities
        
        # Scoring
        scores = self.scoring.compute_scores(final_turns, sentiment_result, intent_result)
        result["scores"] = scores
        
        # Speech emotion
        speech_emotion = self.tone.analyze(merged_text) if merged_text else {}
        result["speech_emotion"] = speech_emotion
        
        logger.info("[Aggregator] Aggregation complete")
        return result
    
    def _aggregate_intent_scores(self, chunk_results: List[Dict[str, Any]]) -> Dict[str, float]:
        """
        Aggregate intent scores from all chunks by averaging.
        
        Args:
            chunk_results: List of chunk results
        
        Returns:
            Dict of averaged intent probabilities
        """
        score_lists: Dict[str, List[float]] = {}
        
        for chunk in chunk_results:
            scores = chunk.get("intent_scores", {})
            for intent_label, score in scores.items():
                if intent_label not in score_lists:
                    score_lists[intent_label] = []
                try:
                    score_lists[intent_label].append(float(score))
                except (TypeError, ValueError):
                    pass
        
        # Average each intent
        aggregated = {}
        for intent_label, scores in score_lists.items():
            if scores:
                aggregated[intent_label] = float(np.mean(scores))
        
        return aggregated
    
    def export_results(self,
                      result: Dict[str, Any],
                      out_dir: str = "outputs") -> Dict[str, str]:
        """
        Export aggregated results to files (JSON, CSV, HTML, TXT).
        
        Args:
            result: Aggregated analysis result
            out_dir: Output directory
        
        Returns:
            Dict mapping format -> file path
        """
        if not self.exporter:
            logger.warning("Exporter not initialized")
            return {}
        
        os.makedirs(out_dir, exist_ok=True)
        
        try:
            exports = self.exporter.export(result, out_dir)
            logger.info(f"[Aggregator] Exported results to {out_dir}")
            return exports
        except Exception as e:
            logger.error(f"[Aggregator] Export failed: {e}")
            return {}
    
    def save_to_db(self, result: Dict[str, Any]) -> Optional[int]:
        """
        Save aggregated result to SQLite database.
        
        Args:
            result: Aggregated analysis result
        
        Returns:
            Record ID if successful, None otherwise
        """
        try:
            from src.storage import db
            record_id = db.insert_record(result)
            logger.info(f"[Aggregator] Saved to DB with ID: {record_id}")
            return record_id
        except Exception as e:
            logger.error(f"[Aggregator] DB save failed: {e}")
            return None
