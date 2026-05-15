"""
Live Streaming UI for Streamlit dashboard.
Handles start/stop controls, real-time updates, and final report generation.
"""

import streamlit as st
import time
import tempfile
import os
from typing import Dict, Any, Optional, List
import numpy as np

from src.streaming.state import StreamingState, ChunkResult
from src.streaming.recorder import StreamingRecorder
from src.streaming.chunk_processor import ChunkProcessor
from src.streaming.aggregator import ChunkAggregator
from src.utils import get_logger, get_intent_label, get_intent_confidence

logger = get_logger(__name__)


def render_live_badge():
    """Render a pulsing LIVE badge."""
    st.markdown("""
    <style>
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .live-badge {
            display: inline-block;
            background: #dc2626;
            color: white;
            padding: 4px 10px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            animation: pulse 1.5s ease-in-out infinite;
            margin-right: 8px;
        }
    </style>
    <span class="live-badge">🔴 LIVE</span>
    """, unsafe_allow_html=True)


def render_streaming_controls() -> tuple[bool, bool, bool]:
    """
    Render start/stop/reset controls for streaming.
    Returns: (start_clicked, stop_clicked, reset_clicked)
    """
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        start_btn = st.button("▶️ Start Live Analysis", 
                             key="stream_start",
                             use_container_width=True,
                             type="primary")
    
    with col2:
        stop_btn = st.button("⏹️ Stop", 
                            key="stream_stop",
                            use_container_width=True,
                            disabled=(not st.session_state.get("streaming_active", False)))
    
    with col3:
        reset_btn = st.button("🔄 Reset", 
                             key="stream_reset",
                             use_container_width=True)
    
    with col4:
        st.empty()  # Spacer
    
    return start_btn, stop_btn, reset_btn


def render_live_stats():
    """Render live statistics: chunks processed, duration, etc."""
    state = StreamingState.get_from_session()
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Chunks Processed", state.get_chunk_count())
    
    with col2:
        duration_sec = int(state.total_duration)
        m, s = divmod(duration_sec, 60)
        st.metric("Duration", f"{m}:{s:02d}")
    
    with col3:
        text_len = len(state.get_live_transcript())
        st.metric("Transcript Length", f"{text_len} chars")
    
    with col4:
        st.metric("Errors", len(state.error_log))


def render_live_transcript():
    """Render live-updating transcript."""
    state = StreamingState.get_from_session()
    transcript = state.get_live_transcript()
    
    if transcript:
        st.text_area("Live Transcript", 
                    value=transcript, 
                    height=200, 
                    disabled=True,
                    key="live_transcript")
    else:
        st.info("Waiting for audio...")


def render_live_intent_bars():
    """Render live intent probability bars (aggregated from chunks)."""
    state = StreamingState.get_from_session()
    
    if not state.chunks:
        st.info("No chunks yet...")
        return
    
    # Aggregate intent scores
    intent_totals = {}
    intent_counts = {}
    
    for chunk in state.chunks:
        scores = chunk.get("intent_scores", {}) if hasattr(chunk, "get") else {}
        for intent, score in scores.items():
            if intent not in intent_totals:
                intent_totals[intent] = 0
                intent_counts[intent] = 0
            intent_totals[intent] += float(score)
            intent_counts[intent] += 1
    
    if not intent_totals:
        st.info("Computing intent...")
        return
    
    # Average and display
    intent_avg = {k: intent_totals[k] / intent_counts[k] 
                 for k in intent_totals.keys()}
    
    # Sort by probability
    sorted_intents = sorted(intent_avg.items(), key=lambda x: x[1], reverse=True)
    
    st.write("**Intent Probabilities (Live)**")
    for intent, prob in sorted_intents:
        col1, col2 = st.columns([1, 4])
        with col1:
            st.write(f"`{intent}`")
        with col2:
            st.progress(prob, text=f"{prob*100:.0f}%")


def render_live_emotion_indicators():
    """Render live emotion indicators from chunks."""
    state = StreamingState.get_from_session()
    
    if not state.chunks:
        return
    
    # Average tone/sentiment from chunks
    sentiments = []
    tones = []
    
    for chunk in state.chunks:
        if chunk.get("sentiment"):
            sentiments.append(chunk["sentiment"])
        if chunk.get("tone"):
            tones.append(chunk["tone"])
    
    col1, col2 = st.columns(2)
    
    with col1:
        if sentiments:
            latest_sent = sentiments[-1]
            st.metric("Sentiment", 
                     latest_sent.get("label", "—"),
                     delta=f"Score: {latest_sent.get('score', 0):.2f}")
    
    with col2:
        if tones:
            latest_tone = tones[-1]
            st.metric("Tone", 
                     latest_tone.get("label_pretty", "—"),
                     delta=f"Score: {latest_tone.get('score', 0):.2f}")


def run_streaming_session() -> Optional[Dict[str, Any]]:
    """
    Main streaming session loop.
    Returns final analysis result when complete, None if cancelled.
    """
    state = StreamingState.get_from_session()
    
    # Initialize recorder and processor
    recorder = StreamingRecorder(chunk_duration=4.0, sample_rate=16000)
    processor = ChunkProcessor()
    processor.load_resources()
    
    # Start recording
    recorder.start()
    state.start_session()
    StreamingState.save_to_session(state)
    
    # Collect chunks
    all_chunks: List[np.ndarray] = []
    chunk_results: List[Dict[str, Any]] = []
    chunk_id = 0
    current_time = 0.0
    
    # Real-time processing loop
    container = st.container()
    
    try:
        while state.is_recording:
            # Check for audio chunks
            audio_chunk = recorder.get_chunk(block=False, timeout=0.1)
            
            if audio_chunk is not None:
                # Process chunk
                end_time = current_time + len(audio_chunk) / 16000.0
                result = processor.process_chunk(
                    audio_chunk, 16000, chunk_id,
                    start_time=current_time,
                    end_time=end_time
                )
                
                chunk_results.append(result)
                all_chunks.append(audio_chunk)
                current_time = end_time
                
                # Update state
                chunk_obj = ChunkResult(
                    chunk_id=chunk_id,
                    timestamp=None,
                    duration=end_time - current_time,
                    text=result.get("text", ""),
                    start_time=current_time,
                    end_time=end_time,
                    speakers=result.get("speakers", []),
                    intent_scores=result.get("intent_scores", {}),
                    sentiment=result.get("sentiment"),
                    audio_tone=result.get("audio_tone"),
                    error=result.get("error")
                )
                state.add_chunk(chunk_obj)
                StreamingState.save_to_session(state)
                
                chunk_id += 1
                
                # Refresh UI every chunk
                with container:
                    render_live_stats()
                    st.write("---")
                    render_live_transcript()
                    st.write("---")
                    col1, col2 = st.columns(2)
                    with col1:
                        render_live_intent_bars()
                    with col2:
                        render_live_emotion_indicators()
            
            # Check for errors
            error = recorder.get_error()
            if error:
                state.add_error(error)
                st.error(f"Recording error: {error}")
            
            # Check for stop signal
            if st.session_state.get("streaming_stop_signal", False):
                logger.info("[STREAMING] Stop signal received")
                state.stop_session()
                break
            
            time.sleep(0.1)
    
    except Exception as e:
        logger.error(f"Streaming session error: {e}")
        state.add_error(str(e))
        st.error(f"Streaming error: {e}")
    
    finally:
        recorder.stop()
    
    # Finalization: merge chunks and run final analysis
    logger.info(f"[STREAMING] Recording stopped. Merging {len(all_chunks)} chunks...")
    
    if all_chunks:
        # Merge audio
        merged_audio = recorder.merge_audio_chunks(all_chunks, sr=16000)
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            import soundfile
            soundfile.write(tmp.name, merged_audio, 16000)
            merged_path = tmp.name
        
        state.merged_audio_path = merged_path
        StreamingState.save_to_session(state)
        
        # Run aggregation
        logger.info("[STREAMING] Running final aggregation...")
        aggregator = ChunkAggregator()
        aggregator.load_resources()
        final_result = aggregator.aggregate_results(chunk_results, merged_path)
        
        # Export and save
        aggregator.export_results(final_result, "outputs")
        aggregator.save_to_db(final_result)
        
        state.final_result = final_result
        state.finalize_session()
        StreamingState.save_to_session(state)
        
        return final_result
    
    return None


def display_final_report(result: Dict[str, Any]):
    """Display the final analysis report (same as normal pipeline)."""
    st.success("✅ Live Analysis Complete!")
    
    intent_obj = result.get("intent")
    intent_label = get_intent_label(intent_obj)
    intent_conf = get_intent_confidence(intent_obj)
    entities = result.get("entities", {}) or {}
    scores = result.get("scores", {}) or {}
    sentiment = result.get("sentiment", {}) or {}
    audio_tone = result.get("audio_tone", {}) or {}
    turns = result.get("turns", []) or []
    transcript = result.get("transcript", "") or ""
    
    # Summary cards
    st.markdown("## 📊 Final Call Summary")
    c1, c2, c3, c4, c5 = st.columns(5)
    
    # (Use same rendering functions as main pipeline)
    from streamlit_app import render_metric_card, render_intent_card
    
    with c1:
        color = {"PTP": "#10b981", "Partial Payment": "#f59e0b", 
                "Refusal": "#ef4444", "Already Paid": "#3b82f6",
                "Ambiguous": "#6b7280"}.get(intent_label, "#6b7280")
        chip = f'<span class="intent-chip" style="background:{color}">{intent_label}</span>'
        st.markdown(f"""
        <div class="metric-card">
            <div class="label">Intent</div>
            <div class="value">{chip}</div>
            <div class="sub">Confidence: {intent_conf*100:.0f}%</div>
        </div>""", unsafe_allow_html=True)
    
    with c2:
        st.markdown(render_metric_card(
            "Sentiment", sentiment.get("label", "—"),
            f"Score: {sentiment.get('score', 0):.2f}" if isinstance(sentiment.get("score"), (int, float)) else ""
        ), unsafe_allow_html=True)
    
    with c3:
        collector_avg = (scores.get("Listening", 0) + scores.get("Communication", 0) +
                        scores.get("Persuasion", 0) + scores.get("Outcome", 0)) / 4.0
        st.markdown(render_metric_card(
            "Collector Score", f"{collector_avg:.1f}/5",
            f"L:{scores.get('Listening',0)} · C:{scores.get('Communication',0)} · P:{scores.get('Persuasion',0)} · O:{scores.get('Outcome',0)}"
        ), unsafe_allow_html=True)
    
    with c4:
        from streamlit_app import fmt_time
        total_dur = sum(float(t.get("end", 0)) - float(t.get("start", 0)) for t in turns if t.get("end") and t.get("start"))
        st.markdown(render_metric_card(
            "Call Duration", fmt_time(total_dur),
            f"{len(turns)} turns"
        ), unsafe_allow_html=True)
    
    with c5:
        st.markdown(render_metric_card(
            "Speech Emotion", 
            result.get("speech_emotion", {}).get("label_pretty", "—"),
            f"Score: {result.get('speech_emotion', {}).get('score', 0):.2f}"
        ), unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Transcript
    st.markdown("## 💬 Final Transcript")
    st.text_area("Transcript", transcript, height=200, disabled=True)
    
    # Export
    st.markdown("## 📥 Export")
    c1, c2, c3, c4 = st.columns(4)
    
    for col, format_name in zip([c1, c2, c3, c4], ["TXT", "JSON", "CSV", "HTML"]):
        with col:
            path = f"outputs/transcript.{format_name.lower()}"
            if format_name == "JSON":
                path = "outputs/analysis.json"
            elif format_name == "CSV":
                path = "outputs/report.csv"
            elif format_name == "HTML":
                path = "outputs/report.html"
            
            if os.path.exists(path):
                with open(path, "rb") as f:
                    st.download_button(f"Download {format_name}", 
                                     f.read(),
                                     file_name=os.path.basename(path),
                                     use_container_width=True)
