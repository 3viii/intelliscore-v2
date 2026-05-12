"""
Exporter — saves transcript, JSON, CSV and a polished HTML report.
Tolerant of intent in either legacy-string or new dict form.
"""

import os
import json
import csv
import html as _html
from datetime import datetime, timezone
from typing import List, Dict, Any, Union

from src.utils import get_intent_label, get_intent_confidence


def _fmt_time(s: float) -> str:
    try:
        s = float(s)
    except (TypeError, ValueError):
        return "--:--"
    m, sec = divmod(int(s), 60)
    return f"{m:02d}:{sec:02d}"


class Exporter:
    @staticmethod
    def save(
        transcript: str,
        turns: List[Dict],
        diarized: List[Dict],
        intent: Union[str, Dict],
        entities: Dict,
        scores: Dict,
        sentiment: Dict = None,
        speech_emotion: Dict = None,
        out_dir: str = "outputs",
        meta: Dict[str, Any] = None,
        audio_tone: Dict[str, Any] = None,
    ):
        os.makedirs(out_dir, exist_ok=True)
        timestamp = datetime.now(timezone.utc).isoformat()
        meta = meta or {}

        intent_label = get_intent_label(intent)
        intent_conf = get_intent_confidence(intent)

        # ------------------------------------------------------------------
        # Transcript TXT
        # ------------------------------------------------------------------
        with open(os.path.join(out_dir, "transcript.txt"), "w", encoding="utf-8") as f:
            f.write(transcript or "")

        # ------------------------------------------------------------------
        # Analysis JSON
        # ------------------------------------------------------------------
        analysis = {
            "timestamp": timestamp,
            "filename": meta.get("filename"),
            "duration_sec": meta.get("duration_sec"),
            "intent": intent,                # full dict if available
            "intent_label": intent_label,    # convenience field
            "intent_confidence": intent_conf,
            "entities": entities,
            "scores": scores,
            "sentiment": sentiment,
            "speech_emotion": speech_emotion,
            "audio_tone": audio_tone,        # NEW: per-speaker audio tone
            "turns": turns,
            "diarized": diarized,
        }
        with open(os.path.join(out_dir, "analysis.json"), "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False, default=str)

        # ------------------------------------------------------------------
        # CSV
        # ------------------------------------------------------------------
        with open(os.path.join(out_dir, "report.csv"), "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "call_id", "filename", "timestamp",
                "intent", "intent_confidence",
                "amounts", "dates", "modes",
                "listening", "communication", "persuasion", "outcome",
                "text_sentiment", "speech_emotion",
                "n_turns", "duration_sec",
            ])
            writer.writerow([
                meta.get("call_id", "call_001"),
                meta.get("filename", ""),
                timestamp,
                intent_label,
                f"{intent_conf:.3f}",
                "|".join(entities.get("Amount", []) or []),
                "|".join(entities.get("Date", []) or []),
                "|".join(entities.get("Mode", []) or []),
                scores.get("Listening"),
                scores.get("Communication"),
                scores.get("Persuasion"),
                scores.get("Outcome"),
                (sentiment or {}).get("label"),
                (speech_emotion or {}).get("label_pretty"),
                len(turns or []),
                meta.get("duration_sec", ""),
            ])

        # ------------------------------------------------------------------
        # HTML — polished, self-contained report
        # ------------------------------------------------------------------
        html_str = _build_html_report(
            transcript=transcript,
            turns=turns,
            intent_label=intent_label,
            intent_conf=intent_conf,
            intent_obj=intent,
            entities=entities,
            scores=scores,
            sentiment=sentiment,
            speech_emotion=speech_emotion,
            audio_tone=audio_tone,
            meta=meta,
            timestamp=timestamp,
        )
        with open(os.path.join(out_dir, "report.html"), "w", encoding="utf-8") as f:
            f.write(html_str)


# ---------------------------------------------------------------------------
# HTML builder (kept module-level to avoid bloating the class)
# ---------------------------------------------------------------------------
def _build_html_report(transcript, turns, intent_label, intent_conf, intent_obj,
                       entities, scores, sentiment, speech_emotion, meta, timestamp,
                       audio_tone=None):
    e = _html.escape

    # ---- transcript rendering ------------------------------------------------
    transcript_rows = []
    for t in (turns or []):
        role = t.get("role") or t.get("speaker", "SPEAKER")
        text = e(t.get("text", ""))
        time_label = f"{_fmt_time(t.get('start', 0))} – {_fmt_time(t.get('end', 0))}"

        if role == "COLLECTOR":
            bg, color, badge = "#eff6ff", "#1e3a8a", "COLLECTOR"
        elif role == "DEBTOR":
            bg, color, badge = "#ecfdf5", "#065f46", "DEBTOR"
        else:
            bg, color, badge = "#f3f4f6", "#374151", e(str(role))

        transcript_rows.append(f"""
        <div class="turn" style="background:{bg};border-left:4px solid {color}">
          <div class="turn-meta">
            <span class="turn-badge" style="color:{color}">{badge}</span>
            <span class="turn-time">{time_label}</span>
          </div>
          <div class="turn-text">{text}</div>
        </div>""")
    transcript_html = "\n".join(transcript_rows) if transcript_rows else f"<pre>{e(transcript or '')}</pre>"

    # ---- intent badge --------------------------------------------------------
    intent_color = {
        "PTP": "#10b981",
        "Partial Payment": "#f59e0b",
        "Refusal": "#ef4444",
        "Already Paid": "#3b82f6",
        "Ambiguous": "#6b7280",
    }.get(intent_label, "#6b7280")

    # ---- scores chart (inline bars) -----------------------------------------
    score_bars = ""
    for k, v in (scores or {}).items():
        try:
            vv = int(v)
        except (TypeError, ValueError):
            vv = 0
        pct = (vv / 5) * 100
        score_bars += f"""
        <div class="score-row">
          <div class="score-label">{e(k)}</div>
          <div class="score-bar"><div class="score-fill" style="width:{pct}%"></div></div>
          <div class="score-value">{vv}/5</div>
        </div>"""

    # ---- entity chips --------------------------------------------------------
    def _chips(items, color):
        items = items or []
        if not items:
            return "<span class='chip chip-empty'>—</span>"
        return "".join(f"<span class='chip' style='background:{color}'>{e(str(x))}</span>" for x in items)

    amount_chips = _chips(entities.get("Amount"), "#dbeafe")
    date_chips   = _chips(entities.get("Date"),   "#fef3c7")
    mode_chips   = _chips(entities.get("Mode"),   "#dcfce7")

    # ---- intent score breakdown ---------------------------------------------
    intent_breakdown = ""
    if isinstance(intent_obj, dict) and intent_obj.get("all_scores"):
        rows = []
        for lbl, sc in sorted(intent_obj["all_scores"].items(), key=lambda x: -x[1]):
            pct = float(sc) * 100
            rows.append(f"""
            <div class="score-row">
              <div class="score-label" style="min-width:130px">{e(lbl)}</div>
              <div class="score-bar"><div class="score-fill" style="width:{pct:.1f}%;background:{intent_color}"></div></div>
              <div class="score-value">{pct:.0f}%</div>
            </div>""")
        intent_breakdown = "".join(rows)

    duration_str = ""
    if meta.get("duration_sec"):
        try:
            duration_str = _fmt_time(meta["duration_sec"])
        except Exception:
            duration_str = ""

    # ---- audio tone (per-speaker) -------------------------------------------
    tone_html = ""
    if isinstance(audio_tone, dict) and audio_tone.get("by_role"):
        by_role = audio_tone["by_role"]
        coll = by_role.get("COLLECTOR") or {}
        debt = by_role.get("DEBTOR") or {}
        overall = audio_tone.get("overall") or {}

        def _tone_card(title, data, accent):
            label = e(str(data.get("label_pretty") or "Unknown"))
            score = float(data.get("score") or 0)
            return (
                f'<div style="flex:1;min-width:200px;background:white;border-radius:10px;'
                f'border:1px solid #e2e8f0;padding:16px;border-left:4px solid {accent};">'
                f'<div style="font-size:11px;font-weight:600;color:#64748b;text-transform:uppercase;'
                f'letter-spacing:.06em;margin-bottom:6px">{e(title)}</div>'
                f'<div style="font-size:20px;font-weight:700;color:#0f172a">{label}</div>'
                f'<div style="font-size:12px;color:#64748b;margin-top:4px">'
                f'Confidence: {score*100:.0f}%</div></div>'
            )

        tone_html = (
            '<div class="section"><h2>Audio Tone Detection (per-speaker)</h2>'
            '<div style="display:flex;gap:12px;flex-wrap:wrap">'
            + _tone_card("Overall Call", overall, "#6366f1")
            + _tone_card("Collector Tone", coll, "#1e3a8a")
            + _tone_card("Debtor Tone", debt, "#10b981")
            + '</div></div>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>INTELLISCORE — Call Analysis Report</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background:#f8fafc; color:#0f172a; margin:0; padding:32px;
  }}
  .container {{ max-width:1100px; margin:0 auto; }}
  .header {{
    background:linear-gradient(135deg,#1e3a8a 0%,#3b82f6 100%);
    color:white; padding:32px; border-radius:14px; margin-bottom:24px;
    box-shadow:0 8px 28px rgba(30,58,138,.18);
  }}
  .header h1 {{ margin:0 0 8px; font-size:28px; font-weight:700; letter-spacing:-.02em; }}
  .header .sub {{ opacity:.85; font-size:14px; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:16px; margin-bottom:24px; }}
  .card {{ background:white; padding:20px; border-radius:12px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,.04); }}
  .card-label {{ font-size:11px; font-weight:600; color:#64748b; text-transform:uppercase; letter-spacing:.06em; margin-bottom:8px; }}
  .card-value {{ font-size:22px; font-weight:700; color:#0f172a; }}
  .intent-chip {{ display:inline-block; padding:4px 12px; border-radius:999px; color:white; font-weight:600; font-size:13px; background:{intent_color}; }}
  .section {{ background:white; padding:24px; border-radius:12px; margin-bottom:20px; border:1px solid #e2e8f0; }}
  .section h2 {{ margin:0 0 16px; font-size:18px; color:#1e293b; }}
  .turn {{ padding:12px 14px; margin:8px 0; border-radius:8px; }}
  .turn-meta {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; }}
  .turn-badge {{ font-size:11px; font-weight:700; letter-spacing:.05em; }}
  .turn-time  {{ font-size:11px; color:#64748b; font-family:"SF Mono",monospace; }}
  .turn-text  {{ font-size:14px; color:#1e293b; line-height:1.45; }}
  .score-row {{ display:flex; align-items:center; gap:12px; margin:8px 0; }}
  .score-label {{ min-width:110px; font-size:13px; color:#475569; font-weight:500; }}
  .score-bar {{ flex:1; background:#e2e8f0; height:10px; border-radius:5px; overflow:hidden; }}
  .score-fill {{ background:linear-gradient(90deg,#3b82f6,#1e3a8a); height:100%; border-radius:5px; transition:width .3s; }}
  .score-value {{ min-width:46px; text-align:right; font-weight:600; font-size:13px; color:#0f172a; }}
  .chip {{ display:inline-block; padding:4px 10px; border-radius:6px; margin:3px; font-size:12px; color:#0f172a; }}
  .chip-empty {{ color:#94a3b8; background:#f1f5f9; }}
  .footer {{ text-align:center; color:#94a3b8; font-size:12px; margin-top:28px; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📞 INTELLISCORE — Call Analysis Report</h1>
    <div class="sub">{e(meta.get('filename') or 'audio.wav')} &nbsp;•&nbsp; Generated: {e(timestamp)}</div>
  </div>

  <div class="grid">
    <div class="card">
      <div class="card-label">Intent</div>
      <div class="card-value"><span class="intent-chip">{e(intent_label)}</span></div>
    </div>
    <div class="card">
      <div class="card-label">Intent Confidence</div>
      <div class="card-value">{intent_conf*100:.0f}%</div>
    </div>
    <div class="card">
      <div class="card-label">Sentiment</div>
      <div class="card-value">{e((sentiment or {}).get('label', '—'))}</div>
    </div>
    <div class="card">
      <div class="card-label">Speech Emotion</div>
      <div class="card-value">{e((speech_emotion or {}).get('label_pretty', '—'))}</div>
    </div>
    <div class="card">
      <div class="card-label">Duration</div>
      <div class="card-value">{e(duration_str) or '—'}</div>
    </div>
    <div class="card">
      <div class="card-label">Turns</div>
      <div class="card-value">{len(turns or [])}</div>
    </div>
  </div>

  <div class="section">
    <h2>Collector Performance Scores</h2>
    {score_bars or '<p style="color:#94a3b8">No scores available.</p>'}
  </div>

  {('<div class="section"><h2>Intent Probability Breakdown</h2>' + intent_breakdown + '</div>') if intent_breakdown else ''}

  {tone_html}

  <div class="section">
    <h2>Extracted Entities</h2>
    <div style="margin-bottom:10px"><strong>Amount:</strong> {amount_chips}</div>
    <div style="margin-bottom:10px"><strong>Date:</strong> {date_chips}</div>
    <div><strong>Payment Mode:</strong> {mode_chips}</div>
  </div>

  <div class="section">
    <h2>Transcript</h2>
    {transcript_html}
  </div>

  <div class="footer">INTELLISCORE • AI-driven debt-collection call analysis • {e(timestamp)}</div>
</div>
</body>
</html>"""
