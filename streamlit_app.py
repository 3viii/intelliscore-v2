"""
INTELLISCORE — Professional Streamlit Dashboard
================================================
Production-style UI for the AI Call Analysis pipeline.

Run:
    streamlit run streamlit_app.py
    streamlit run streamlit_app.py example.wav   # auto-load a file
"""

import os
import sys
import json
import tempfile
import traceback
from pathlib import Path
from datetime import datetime

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Local imports
from src.pipeline import AudioPipeline
from src.config import CONFIG
from src.utils import get_intent_label, get_intent_confidence
from src.storage import db as dbmod


# =============================================================================
# Page configuration & theme
# =============================================================================
st.set_page_config(
    page_title="INTELLISCORE — AI Call Analysis",
    page_icon="📞",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS — corporate look
st.markdown("""
<style>
    /* Hide Streamlit chrome */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* App-wide */
    .main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

    /* Hero header */
    .hero {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        padding: 28px 32px;
        border-radius: 14px;
        color: white;
        margin-bottom: 22px;
        box-shadow: 0 8px 24px rgba(30,58,138,.18);
    }
    .hero h1 { margin:0 0 4px; font-size:26px; font-weight:700; letter-spacing:-.02em;}
    .hero p  { margin:0; opacity:.85; font-size:13px;}

    /* Summary cards */
    .metric-card {
        background: white;
        padding: 18px 20px;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,.04);
        height: 100%;
    }
    .metric-card .label {
        font-size: 11px; font-weight:600; color:#64748b;
        text-transform: uppercase; letter-spacing:.06em; margin-bottom:8px;
    }
    .metric-card .value { font-size: 22px; font-weight: 700; color:#0f172a;}
    .metric-card .sub   { font-size: 12px; color:#64748b; margin-top:4px;}

    /* Intent chip */
    .intent-chip {
        display:inline-block; padding:4px 12px; border-radius:999px;
        color:white; font-weight:600; font-size:13px;
    }

    /* Transcript turn bubbles */
    .turn {
        padding:10px 14px; margin:6px 0; border-radius:8px; line-height:1.45;
    }
    .turn-collector { background:#eff6ff; border-left:4px solid #1e3a8a;}
    .turn-debtor    { background:#ecfdf5; border-left:4px solid #065f46;}
    .turn-unknown   { background:#f3f4f6; border-left:4px solid #6b7280;}
    .turn-meta { display:flex; justify-content:space-between; margin-bottom:3px;}
    .turn-role-collector { color:#1e3a8a; font-weight:700; font-size:11px; letter-spacing:.05em;}
    .turn-role-debtor    { color:#065f46; font-weight:700; font-size:11px; letter-spacing:.05em;}
    .turn-role-unknown   { color:#374151; font-weight:700; font-size:11px; letter-spacing:.05em;}
    .turn-time { color:#94a3b8; font-size:10px; font-family:'SF Mono', Consolas, monospace;}
    .turn-text { color:#1e293b; font-size:14px;}

    /* Entity chips */
    .entity-chip {
        display:inline-block; padding:5px 12px; border-radius:6px;
        margin:3px 4px 3px 0; font-size:12px; font-weight:500;
    }

    /* Section headings inside the app */
    .sec-title {
        font-size:15px; font-weight:700; color:#1e293b;
        margin: 6px 0 10px; letter-spacing:-.01em;
    }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# Helpers
# =============================================================================
INTENT_COLOR = {
    "PTP": "#10b981",
    "Partial Payment": "#f59e0b",
    "Refusal": "#ef4444",
    "Already Paid": "#3b82f6",
    "Ambiguous": "#6b7280",
}


def fmt_time(s):
    try:
        s = float(s)
    except (TypeError, ValueError):
        return "--:--"
    m, sec = divmod(int(s), 60)
    return f"{m:02d}:{sec:02d}"


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def render_metric_card(label, value, sub=""):
    return f"""
    <div class="metric-card">
        <div class="label">{label}</div>
        <div class="value">{value}</div>
        <div class="sub">{sub}</div>
    </div>"""


def render_intent_card(label, intent_label, intent_conf):
    color = INTENT_COLOR.get(intent_label, "#6b7280")
    chip = f'<span class="intent-chip" style="background:{color}">{intent_label}</span>'
    return f"""
    <div class="metric-card">
        <div class="label">{label}</div>
        <div class="value">{chip}</div>
        <div class="sub">Confidence: {intent_conf*100:.0f}%</div>
    </div>"""


# Audio-tone label → colour (used for the per-speaker tone cards)
TONE_COLOR = {
    "Angry":       "#dc2626",
    "Frustrated":  "#ea580c",
    "Sad":         "#0284c7",
    "Fear":        "#7c3aed",
    "Disgust":     "#9333ea",
    "Surprise":    "#ec4899",
    "Happy":       "#16a34a",
    "Excited":     "#22c55e",
    "Calm":        "#14b8a6",
    "Neutral":     "#6b7280",
    "Unknown":     "#94a3b8",
}


def render_tone_card(title, tone_dict, accent="#6366f1"):
    """One per-speaker tone card."""
    label = (tone_dict or {}).get("label_pretty") or "Unknown"
    score = float((tone_dict or {}).get("score") or 0)
    chip_color = TONE_COLOR.get(label, "#6b7280")
    chip = (f'<span style="display:inline-block;padding:4px 12px;border-radius:999px;'
            f'background:{chip_color};color:white;font-weight:600;font-size:13px">{label}</span>')
    return f"""
    <div class="metric-card" style="border-left:4px solid {accent}">
        <div class="label">{title}</div>
        <div class="value">{chip}</div>
        <div class="sub">Confidence: {score*100:.0f}%</div>
    </div>"""


def render_transcript(turns):
    parts = []
    for t in (turns or []):
        role = t.get("role") or t.get("speaker", "SPEAKER")
        text = (t.get("text") or "").replace("<", "&lt;").replace(">", "&gt;")
        time_label = f"{fmt_time(t.get('start', 0))} – {fmt_time(t.get('end', 0))}"
        conf = t.get("confidence", 0)

        if role == "COLLECTOR":
            css_turn, css_role, badge = "turn-collector", "turn-role-collector", "COLLECTOR"
        elif role == "DEBTOR":
            css_turn, css_role, badge = "turn-debtor", "turn-role-debtor", "DEBTOR"
        else:
            css_turn, css_role, badge = "turn-unknown", "turn-role-unknown", str(role)

        parts.append(f'<div class="turn {css_turn}"><div class="turn-meta"><span class="{css_role}">{badge}</span><span class="turn-time">{time_label} · conf {conf:.2f}</span></div><div class="turn-text">{text}</div></div>')
    return "<div>" + "\n".join(parts) + "</div>"


def render_entity_chips(items, color):
    if not items:
        return f'<span class="entity-chip" style="background:#f1f5f9;color:#94a3b8">—</span>'
    return "".join(
        f'<span class="entity-chip" style="background:{color};color:#0f172a">{i}</span>'
        for i in items
    )


def compute_analytics(turns):
    """Return {role: total_seconds}, num turns per role, distribution."""
    talk_time = {"COLLECTOR": 0.0, "DEBTOR": 0.0, "OTHER": 0.0}
    turn_count = {"COLLECTOR": 0, "DEBTOR": 0, "OTHER": 0}
    for t in turns or []:
        try:
            dur = max(0.0, float(t.get("end", 0)) - float(t.get("start", 0)))
        except (TypeError, ValueError):
            dur = 0.0
        role = t.get("role") or "OTHER"
        if role not in talk_time:
            role = "OTHER"
        talk_time[role] += dur
        turn_count[role] += 1
    total_time = sum(talk_time.values()) or 1.0
    ratios = {k: round(v / total_time * 100, 1) for k, v in talk_time.items()}
    return {
        "talk_time": talk_time,
        "turn_count": turn_count,
        "ratios": ratios,
        "total_duration": sum(talk_time.values()),
        "total_turns": sum(turn_count.values()),
    }


def plot_score_radar(scores_dict):
    """Radar chart of the 4 collector performance scores."""
    keys = list(scores_dict.keys())
    vals = list(scores_dict.values())
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals + [vals[0]], theta=keys + [keys[0]],
        fill="toself", line=dict(color="#3b82f6", width=2),
        fillcolor="rgba(59,130,246,0.25)", name="Score",
    ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 5], tickvals=[1, 2, 3, 4, 5])),
        showlegend=False, margin=dict(l=20, r=20, t=20, b=20), height=300,
    )
    return fig


def plot_speaker_donut(analytics):
    """Speaker distribution by talk time."""
    talk_time = analytics["talk_time"]
    labels, values, colors = [], [], []
    color_map = {"COLLECTOR": "#1e3a8a", "DEBTOR": "#10b981", "OTHER": "#94a3b8"}
    for role, t in talk_time.items():
        if t > 0:
            labels.append(role); values.append(t); colors.append(color_map[role])
    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values, hole=0.55,
        marker=dict(colors=colors), textinfo="label+percent",
        textfont=dict(size=12),
    )])
    fig.update_layout(showlegend=False, margin=dict(l=10, r=10, t=10, b=10), height=300)
    return fig


def plot_intent_breakdown(intent_obj):
    """Horizontal bar chart of intent probabilities."""
    if not isinstance(intent_obj, dict) or not intent_obj.get("all_scores"):
        return None
    scores = intent_obj["all_scores"]
    df = pd.DataFrame({"Intent": list(scores.keys()),
                       "Probability": [float(v) for v in scores.values()]})
    df = df.sort_values("Probability", ascending=True)
    df["Color"] = df["Intent"].map(INTENT_COLOR).fillna("#94a3b8")
    fig = go.Figure(go.Bar(
        x=df["Probability"], y=df["Intent"], orientation="h",
        marker=dict(color=df["Color"]),
        text=[f"{v*100:.0f}%" for v in df["Probability"]],
        textposition="outside",
    ))
    fig.update_layout(
        margin=dict(l=10, r=40, t=10, b=10), height=240,
        xaxis=dict(range=[0, 1.0], showgrid=True, gridcolor="#f1f5f9"),
        yaxis=dict(showgrid=False),
    )
    return fig


# =============================================================================
# Sidebar
# =============================================================================
with st.sidebar:
    st.markdown("### ⚙️  Settings")
    method = st.selectbox(
        "Transcription mode", ["mock", "whisper_local"],
        index=0 if CONFIG.use_api == "mock" else 1,
        help="`mock` uses a built-in fake transcript (fast, no models). "
             "`whisper_local` runs Whisper + Pyannote on the uploaded audio.",
    )
    CONFIG.use_api = method

    st.markdown("---")
    st.markdown("### 📚 History")
    try:
        all_calls = dbmod.get_all_calls(limit=10)
        if all_calls:
            st.caption(f"{dbmod.count_calls()} call(s) stored")
            with st.expander("Recent calls", expanded=False):
                for c in all_calls[:5]:
                    intent_color = INTENT_COLOR.get(c["intent"], "#6b7280")
                    st.markdown(
                        f"<div style='font-size:12px;margin:6px 0;padding:8px;"
                        f"background:#f8fafc;border-radius:6px;'>"
                        f"<b>#{c['id']}</b> <span style='color:{intent_color}'>●</span> "
                        f"{c['intent']}<br>"
                        f"<span style='color:#94a3b8;font-size:10px;'>{c['filename'] or '—'}</span>"
                        f"</div>", unsafe_allow_html=True)
        else:
            st.caption("No calls processed yet.")
    except Exception as e:
        st.caption(f"DB unavailable: {e}")

    st.markdown("---")
    st.caption("**INTELLISCORE** v2.0  \nAI Call Analysis Platform")


# =============================================================================
# Hero header
# =============================================================================
st.markdown("""
<div class="hero">
  <h1>📞 INTELLISCORE — AI Call Analysis</h1>
  <p>Whisper · Pyannote · TF-IDF Intent Classifier · Real-time Analytics</p>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# File input
# =============================================================================
# CLI-passed file
file_arg = None
if len(sys.argv) > 1:
    maybe = sys.argv[-1]
    if os.path.exists(maybe):
        file_arg = maybe

upload_col, info_col = st.columns([3, 1])
with upload_col:
    if file_arg:
        st.info(f"📂 Loaded from command line: `{Path(file_arg).name}`")

    # ----- Tabs: Upload file  |  Record from mic ---------------------------
    tab_upload, tab_record = st.tabs(["📁 Upload audio file", "🎙️  Record from microphone"])

    uploaded_file = None
    recorded_audio = None

    with tab_upload:
        uploaded_file = st.file_uploader(
            "Choose an audio file",
            type=["wav", "mp3", "m4a", "flac", "ogg"],
            help="Supports WAV, MP3, M4A, FLAC, OGG (max 200 MB)",
            label_visibility="collapsed",
        )

    with tab_record:
        # Preferred path: Streamlit's built-in audio_input (≥ 1.36, ~2024).
        # Returns an UploadedFile-like object containing WAV bytes.
        # Falls back to streamlit-mic-recorder if the built-in isn't available.
        recorded_audio = None
        builtin_recorder = getattr(st, "audio_input", None)
        if callable(builtin_recorder):
            st.caption("Click the mic, speak, then click stop. Then press **▶ Analyze Call** below.")
            recorded_audio = builtin_recorder(
                "Record audio",
                label_visibility="collapsed",
                key="mic_recorder_builtin",
            )
        else:
            # Fallback for older Streamlit installs
            try:
                from streamlit_mic_recorder import mic_recorder  # type: ignore
                st.caption("Press 'Start recording', speak, then 'Stop recording'.")
                rec = mic_recorder(
                    start_prompt="● Start recording",
                    stop_prompt="■ Stop recording",
                    just_once=False,
                    use_container_width=True,
                    format="wav",
                    key="mic_recorder_fallback",
                )
                if rec and rec.get("bytes"):
                    # Wrap bytes in a tiny object exposing .name and .read() to match UploadedFile
                    class _RecObj:
                        def __init__(self, data):
                            self._d = data
                            self.name = "mic_recording.wav"
                        def read(self):
                            return self._d
                    recorded_audio = _RecObj(rec["bytes"])
            except ImportError:
                st.warning(
                    "Microphone recording isn't available in this Streamlit version. "
                    "Either upgrade Streamlit (`pip install -U streamlit`) "
                    "or install the fallback (`pip install streamlit-mic-recorder`)."
                )

        if recorded_audio is not None:
            st.success("✅ Recording captured. Click **▶ Analyze Call** to process it.")
            if method == "mock":
                st.warning(
                    "⚠️  Transcription mode is set to **mock** — the recorded audio will be ignored "
                    "and the bundled demo transcript will be used. Switch to **whisper_local** in the "
                    "sidebar to analyse your recording."
                )

with info_col:
    if method == "mock":
        st.markdown("""
        <div style='background:#fef3c7;padding:10px;border-radius:8px;
                    border-left:3px solid #f59e0b;font-size:12px'>
          <b>Mock mode</b> — bundled demo transcript will be used.
          No audio is required.
        </div>""", unsafe_allow_html=True)

# Resolve which audio source to use (priority: upload > recording > CLI arg > mock)
selected_file_path = None
if uploaded_file:
    suffix = Path(uploaded_file.name).suffix or ".wav"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.read()); tmp.close()
    selected_file_path = tmp.name
elif recorded_audio is not None:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.write(recorded_audio.read()); tmp.close()
    selected_file_path = tmp.name
elif file_arg:
    selected_file_path = file_arg
elif method == "mock":
    # In mock mode, the pipeline doesn't actually open the file
    selected_file_path = "mock_demo.wav"

# Audio player (only when real file)
if selected_file_path and os.path.exists(selected_file_path) and method != "mock":
    st.audio(read_bytes(selected_file_path))

analyze_btn = st.button("▶  Analyze Call", type="primary", use_container_width=False,
                        disabled=(selected_file_path is None))


# =============================================================================
# Run analysis
# =============================================================================
if analyze_btn and selected_file_path:
    progress_bar = st.progress(0, text="Initializing pipeline…")
    try:
        progress_bar.progress(15, text="Loading models (Whisper, NER, sentiment, intent)…")
        pipeline = AudioPipeline()

        progress_bar.progress(45, text="Transcribing & diarizing audio…")
        results = pipeline.process_file(selected_file_path)

        progress_bar.progress(85, text="Running analysis & scoring…")
        progress_bar.progress(100, text="Done.")
        progress_bar.empty()

        # Unpack
        intent_obj = results.get("intent")
        intent_label = get_intent_label(intent_obj)
        intent_conf = get_intent_confidence(intent_obj)
        entities = results.get("entities", {}) or {}
        scores = results.get("scores", {}) or {}
        sentiment = results.get("sentiment", {}) or {}
        speech_emotion = results.get("speech_emotion", {}) or {}
        audio_tone = results.get("audio_tone", {}) or {}
        turns = results.get("turns", []) or []
        transcript = results.get("transcript", "") or ""
        meta = results.get("meta", {}) or {}

        if not turns:
            st.warning("⚠️  Pipeline returned no turns. Check the audio file and pipeline logs.")
            st.stop()

        analytics = compute_analytics(turns)
        avg_conf = sum(t.get("confidence", 0) for t in turns) / max(len(turns), 1)

        # ---------------------------------------------------------------
        # SECTION A — Summary cards
        # ---------------------------------------------------------------
        st.markdown('<div class="sec-title">📊 Call Summary</div>', unsafe_allow_html=True)
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.markdown(render_intent_card("Intent", intent_label, intent_conf),
                        unsafe_allow_html=True)
        with c2:
            sent_label = sentiment.get("label", "—")
            sent_score = sentiment.get("score", 0)
            st.markdown(render_metric_card(
                "Sentiment", sent_label,
                f"Score: {sent_score:.2f}" if isinstance(sent_score, (int, float)) else ""
            ), unsafe_allow_html=True)
        with c3:
            collector_avg = (scores.get("Listening", 0) + scores.get("Communication", 0)
                             + scores.get("Persuasion", 0) + scores.get("Outcome", 0)) / 4.0
            st.markdown(render_metric_card(
                "Collector Score", f"{collector_avg:.1f}/5",
                f"L:{scores.get('Listening',0)} · C:{scores.get('Communication',0)} · "
                f"P:{scores.get('Persuasion',0)} · O:{scores.get('Outcome',0)}"
            ), unsafe_allow_html=True)
        with c4:
            st.markdown(render_metric_card(
                "Call Duration", fmt_time(analytics["total_duration"]),
                f"{analytics['total_turns']} turns"
            ), unsafe_allow_html=True)
        with c5:
            st.markdown(render_metric_card(
                "Speech Emotion", speech_emotion.get("label_pretty", "—"),
                f"Score: {speech_emotion.get('score', 0):.2f}"
                if isinstance(speech_emotion.get("score"), (int, float)) else ""
            ), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # ---------------------------------------------------------------
        # SECTION D — Analytics (charts side-by-side)
        # ---------------------------------------------------------------
        st.markdown('<div class="sec-title">📈 Analytics</div>', unsafe_allow_html=True)
        col_radar, col_donut, col_intent = st.columns(3)
        with col_radar:
            st.caption("Collector Performance")
            st.plotly_chart(plot_score_radar(scores), use_container_width=True)
        with col_donut:
            st.caption("Speaker Talk-time Distribution")
            st.plotly_chart(plot_speaker_donut(analytics), use_container_width=True)
            ratios = analytics["ratios"]
            st.markdown(
                f"<div style='text-align:center;font-size:12px;color:#64748b'>"
                f"COLLECTOR <b>{ratios.get('COLLECTOR',0)}%</b> &nbsp;·&nbsp; "
                f"DEBTOR <b>{ratios.get('DEBTOR',0)}%</b></div>",
                unsafe_allow_html=True)
        with col_intent:
            st.caption("Intent Probability Breakdown")
            fig_int = plot_intent_breakdown(intent_obj)
            if fig_int:
                st.plotly_chart(fig_int, use_container_width=True)
            else:
                st.info("Intent breakdown not available (rule-based fallback).")

        # ---------------------------------------------------------------
        # SECTION D2 — Audio Tone Detection (NEW: per-speaker)
        # ---------------------------------------------------------------
        by_role = (audio_tone or {}).get("by_role") or {}
        overall_tone = (audio_tone or {}).get("overall") or {}
        # Only show if at least one slot has real data, otherwise it's noise on mock mode
        has_tone_data = any(
            (d or {}).get("source") == "ml"
            for d in [overall_tone, by_role.get("COLLECTOR"), by_role.get("DEBTOR")]
        )
        if has_tone_data:
            st.markdown("---")
            st.markdown('<div class="sec-title">🎙️ Audio Tone Detection</div>',
                        unsafe_allow_html=True)
            st.caption(
                "Detected directly from the audio waveform using "
                "`superb/wav2vec2-base-superb-er`. Per-speaker tones use the "
                "diarization timestamps to slice each speaker's audio."
            )
            t_col1, t_col2, t_col3 = st.columns(3)
            with t_col1:
                st.markdown(render_tone_card("Overall Call Tone", overall_tone, "#6366f1"),
                            unsafe_allow_html=True)
            with t_col2:
                st.markdown(render_tone_card("Collector Tone",
                                             by_role.get("COLLECTOR"), "#1e3a8a"),
                            unsafe_allow_html=True)
            with t_col3:
                st.markdown(render_tone_card("Debtor Tone",
                                             by_role.get("DEBTOR"), "#10b981"),
                            unsafe_allow_html=True)
        elif method != "mock":
            # Real audio mode but tone detection unavailable — show a hint, not silence
            st.markdown("---")
            st.markdown('<div class="sec-title">🎙️ Audio Tone Detection</div>',
                        unsafe_allow_html=True)
            st.info(
                "Audio tone detection ran but produced no results "
                "(model unavailable or no speaker audio long enough). "
                "Check the pipeline logs."
            )

        st.markdown("---")

        # ---------------------------------------------------------------
        # SECTION B + C — Transcript & Entities (two columns)
        # ---------------------------------------------------------------
        left, right = st.columns([2.0, 1.0])

        with left:
            st.markdown('<div class="sec-title">💬 Styled Transcript</div>',
                        unsafe_allow_html=True)
            st.markdown(render_transcript(turns), unsafe_allow_html=True)
            st.caption(f"Average alignment confidence: {avg_conf:.2f}")

        with right:
            st.markdown('<div class="sec-title">🏷️  Extracted Entities</div>',
                        unsafe_allow_html=True)
            st.markdown("**💰  Amount**", unsafe_allow_html=True)
            st.markdown(render_entity_chips(entities.get("Amount", []), "#dbeafe"),
                        unsafe_allow_html=True)
            st.markdown("**📅  Date**", unsafe_allow_html=True)
            st.markdown(render_entity_chips(entities.get("Date", []), "#fef3c7"),
                        unsafe_allow_html=True)
            st.markdown("**💳  Payment Mode**", unsafe_allow_html=True)
            st.markdown(render_entity_chips(entities.get("Mode", []), "#dcfce7"),
                        unsafe_allow_html=True)
            if entities.get("PERSON"):
                st.markdown("**👤  Person**", unsafe_allow_html=True)
                st.markdown(render_entity_chips(entities.get("PERSON", []), "#fce7f3"),
                            unsafe_allow_html=True)
            if entities.get("ORG"):
                st.markdown("**🏢  Organization**", unsafe_allow_html=True)
                st.markdown(render_entity_chips(entities.get("ORG", []), "#ede9fe"),
                            unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="sec-title">⏱️  Turn Timeline</div>',
                        unsafe_allow_html=True)
            timeline_df = pd.DataFrame([{
                "#": i + 1,
                "Role": t.get("role") or "—",
                "Start": fmt_time(t.get("start", 0)),
                "Dur(s)": round((t.get("end", 0) - t.get("start", 0)), 1),
                "Conf": round(t.get("confidence", 0), 2),
            } for i, t in enumerate(turns)])
            st.dataframe(timeline_df, use_container_width=True, hide_index=True,
                         height=min(350, 38 * len(timeline_df) + 40))

        st.markdown("---")

        # ---------------------------------------------------------------
        # SECTION E — Export buttons
        # ---------------------------------------------------------------
        st.markdown('<div class="sec-title">📥 Export</div>', unsafe_allow_html=True)
        e1, e2, e3, e4 = st.columns(4)
        out_dir = "outputs"
        with e1:
            p = os.path.join(out_dir, "transcript.txt")
            if os.path.exists(p):
                st.download_button("📄 Transcript (TXT)", read_bytes(p),
                                   file_name="transcript.txt",
                                   use_container_width=True)
        with e2:
            p = os.path.join(out_dir, "analysis.json")
            if os.path.exists(p):
                st.download_button("🧩 Analysis (JSON)", read_bytes(p),
                                   file_name="analysis.json",
                                   use_container_width=True)
        with e3:
            p = os.path.join(out_dir, "report.csv")
            if os.path.exists(p):
                st.download_button("📊 Report (CSV)", read_bytes(p),
                                   file_name="report.csv",
                                   use_container_width=True)
        with e4:
            p = os.path.join(out_dir, "report.html")
            if os.path.exists(p):
                st.download_button("🌐 Report (HTML)", read_bytes(p),
                                   file_name="report.html",
                                   use_container_width=True)

        st.success(f"✅ Analysis complete — saved to `{out_dir}/` and SQLite DB.")

    except Exception as e:
        progress_bar.empty()
        st.error(f"❌ Pipeline failed: {e}")
        with st.expander("Show traceback"):
            st.code(traceback.format_exc())

else:
    if not selected_file_path:
        st.info("👆 Upload an audio file or switch to **mock** mode in the sidebar "
                "to try a built-in demo.")


# =============================================================================
# Footer
# =============================================================================
st.markdown("---")
st.markdown(
    "<div style='text-align:center;color:#94a3b8;font-size:12px'>"
    "INTELLISCORE • AI-driven debt-collection call analysis • "
    "Powered by Whisper, Pyannote & custom-trained TF-IDF intent classifier"
    "</div>", unsafe_allow_html=True)
