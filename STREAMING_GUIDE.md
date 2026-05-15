# INTELLISCORE v2.2 — Live Streaming Implementation Guide

## Quick Start (3 steps)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Train the Intent Model (one-time)
```bash
python scripts/train_intent_model.py
```

### 3. Run the Dashboard
```bash
streamlit run streamlit_app.py
```

Then navigate to **🔴 Live Analysis** tab in your browser.

---

## What's New in v2.2

### New Tab: "🔴 Live Analysis"
Located between "Upload audio file" and existing tabs.

**Features:**
- Real-time transcript updates as you speak
- Live intent probability bars
- Live emotion/sentiment indicators
- Progressive analytics refresh every 4 seconds
- After stopping: automatic final analysis with high-accuracy diarization
- Final report generation (JSON, CSV, HTML, TXT)
- Automatic SQLite storage

### Why This is Different
| Aspect | Upload/Record | Live Analysis |
|--------|---------------|---------------|
| **When analysis happens** | After recording | During recording + Final pass |
| **User experience** | Submit → Wait | See live updates → Final report |
| **Diarization passes** | 1 (on full audio) | Multiple chunks + 1 final (on merged) |
| **Audio chunking** | One large file | 4-second increments |
| **Total time** | Upload + 2-5 min analysis | Real-time streaming + 1-2 min final |

---

## Using Live Analysis

### Basic Workflow

#### Step 1: Start
1. Open dashboard: `streamlit run streamlit_app.py`
2. Navigate to **🔴 Live Analysis** tab
3. Click **▶️ Start Live Analysis**

#### Step 2: Speak
- Speak naturally into your microphone
- Dashboard updates **every 4 seconds** with:
  - Growing transcript
  - Intent probability updates
  - Emotion/tone indicators
  - Live stats (chunks processed, duration, etc.)

#### Step 3: Stop
- Click **⏹️ Stop** when finished speaking
- System automatically:
  1. Merges all audio chunks
  2. Runs final Pyannote diarization on merged audio
  3. Performs full analysis (NER, scoring, audio tone analysis)
  4. Generates final report
  5. Stores results in SQLite

#### Step 4: Review
- Final dashboard report displayed (same as upload/record mode)
- Download results as JSON, CSV, HTML, TXT
- View in SQLite database

### Live Statistics
While streaming, you'll see:
- **Chunks Processed**: Number of 4-second chunks captured
- **Duration**: Total recording time
- **Transcript Length**: Characters transcribed so far
- **Errors**: Any processing errors

### Live Visualizations
- **Intent Probabilities**: Bar chart updating with aggregated scores
- **Sentiment**: Current sentiment label and confidence
- **Tone**: Current speech emotion and confidence

---

## Configuration

### Chunk Duration
Default: 4 seconds per chunk

To change, edit `streamlit_app.py`:
```python
# Find this line in the tab_live section:
recorder = StreamingRecorder(chunk_duration=4.0)

# Change to your preferred duration:
recorder = StreamingRecorder(chunk_duration=5.0)  # 5 seconds
```

**Recommended: 3–5 seconds**
- Shorter = more responsive, more processing
- Longer = less responsive, less processing

### Mode Selection
In the sidebar, select your ASR mode:
- **whisper_local** (default): Full Whisper processing
- **mock**: Fake data for testing (instant results)

Live Analysis is only available in **whisper_local** mode.

---

## Architecture Overview (Simple Version)

### What Happens During Streaming

```
1. User clicks "Start Live Analysis"
2. Microphone recording begins (background thread)
3. Every ~4 seconds:
   - Audio chunk extracted
   - Chunk transcribed (Whisper)
   - Intent scores computed
   - Sentiment/tone analyzed
   - Results added to live transcript
   - Dashboard refreshes
4. User clicks "Stop"
5. Chunks merged into single audio file
6. Final diarization run (Pyannote on merged)
7. Speakers aligned
8. Intent scores averaged
9. Full analysis performed
10. Results exported & stored
11. Final report displayed
```

### Key Design Decisions

**Why chunks?**
- Responsiveness (see updates every 4 sec)
- Manageable memory use
- Practical for real-time display

**Why final merged diarization?**
- Accuracy (Pyannote works best on complete audio)
- Speaker consistency (not per-chunk)
- Alignment (speakers matched across entire call)

**Why average intent scores?**
- Robustness (one chunk's error doesn't affect result)
- Stability (later chunks weighted same as earlier)
- Interpretability (easy to understand aggregation)

---

## Troubleshooting

### Issue: "🔴 Live Analysis" tab not appearing
**Cause:** Not in whisper_local mode
**Solution:** 
1. Open sidebar
2. Change mode to "whisper_local"
3. Refresh page

### Issue: No audio input device found
**Cause:** System doesn't detect microphone
**Solutions:**
1. Check system audio settings
2. Test microphone works elsewhere (e.g., browser test)
3. In Codespaces: Allow browser access to microphone
4. Fallback: Use "Record from microphone" tab instead

### Issue: Streaming is very slow
**Cause:** 
- CPU-intensive processing
- Large models loading
**Solutions:**
1. Reduce chunk duration (faster processing per chunk)
2. Close other applications
3. Switch to mock mode for testing
4. Run on machine with GPU (if available)

### Issue: Final analysis throws error
**Cause:** Diarization failure
**Solution:**
- Check audio quality
- Verify Pyannote model loaded correctly
- See logs for details
- Fall back to regular upload/record mode

### Issue: Results don't match upload mode
**Reason:** Expected differences:
- Chunks analyzed independently
- Final diarization on merged audio (may differ)
- Aggregation strategy (averaging vs. single pass)
**Solution:** This is normal behavior. If results are very different, investigate audio quality.

---

## Advanced Usage

### Accessing Results Programmatically

```python
import json
from src.storage import db

# Get last recorded session
records = db.get_all_records()
latest = records[0]

print(f"Call ID: {latest['id']}")
print(f"Transcript: {latest['transcript'][:100]}...")
print(f"Intent: {latest['intent_label']}")
print(f"Duration: {latest['duration']:.1f}s")
print(f"Mode: {latest.get('meta', {}).get('mode', 'unknown')}")
```

### Customizing Aggregation Strategy

Edit `src/streaming/aggregator.py`:

```python
def _aggregate_intent_scores(self, chunk_results):
    """Customize how intent scores are combined."""
    
    # Default: Simple average
    # Option 1: Weighted by chunk position (recent chunks matter more)
    # Option 2: Maximum confidence (use best chunk's scores)
    # Option 3: Majority vote (which intent appears most often)
    
    # Your custom logic here...
```

### Adding Custom Metrics

Edit `src/streaming/ui.py`:

```python
def render_custom_metrics():
    """Add your own live metrics."""
    st.metric("Custom Metric", value_here)
```

### Extending Final Analysis

Edit `src/streaming/aggregator.py`:

```python
def aggregate_results(self, chunk_results, merged_audio_path):
    # After line that calls full analysis...
    
    # Add your custom post-processing
    result["custom_field"] = my_analysis(result)
    return result
```

---

## Performance Tuning

### For Faster Streaming
```python
# Shorter chunks = faster processing
recorder = StreamingRecorder(chunk_duration=3.0)  # 3 sec

# Fewer models
# (Can't disable core models, but you can optimize in aggregator)
```

### For Better Accuracy
```python
# Longer chunks = more context for Whisper
recorder = StreamingRecorder(chunk_duration=5.0)  # 5 sec

# More models run during final aggregation
# (Already enabled by default)
```

### For Lower Memory Usage
```python
# Shorter chunks = less audio in memory
recorder = StreamingRecorder(chunk_duration=3.0)  # 3 sec

# Update UI less frequently (edit streamlit_app.py)
```

---

## Testing

### Run the Test Suite
```bash
python tests/test_streaming.py
```

### Run Specific Tests
```bash
python tests/test_streaming.py --test imports       # Test imports only
python tests/test_streaming.py --test state         # Test state management
python tests/test_streaming.py --test processor     # Test chunk processor
python tests/test_streaming.py --test aggregator    # Test aggregator
python tests/test_streaming.py --test end-to-end    # Full mock test
python tests/test_streaming.py --test requirements  # Check dependencies
```

### Mock Mode Testing
1. Start dashboard: `streamlit run streamlit_app.py`
2. In sidebar, select "mock" mode
3. Go to Live Analysis tab
4. Click Start (results will be instant fake data)
5. Verify UI updates correctly

---

## Deployment Checklist

### Before Going to Production

- [ ] Run full test suite: `python tests/test_streaming.py`
- [ ] Test with real microphone on target device
- [ ] Test with 10+ minute recordings
- [ ] Verify database storage
- [ ] Check export formats (JSON, CSV, HTML, TXT)
- [ ] Monitor CPU/memory usage during test session
- [ ] Ensure audio quality acceptable
- [ ] Document any custom configuration changes

### Linux/Docker Deployment
```dockerfile
# Add to Dockerfile
RUN apt-get install -y python3-dev portaudio19-dev
RUN pip install sounddevice>=0.4.5
```

### Windows Deployment
- Ensure microphone drivers up to date
- Test with Windows audio settings
- May need Visual C++ build tools

### macOS Deployment
- Grant microphone permission to browser/Streamlit
- Test with security settings

---

## Support & Community

### Getting Help
1. Check troubleshooting section above
2. Review logs: Dashboard shows error details
3. Run test suite to isolate issue
4. Check STREAMING_ARCHITECTURE.md for deep dive

### Reporting Issues
Include:
- Test output from `test_streaming.py`
- Streamlit logs
- System info (OS, Python version)
- Reproduce steps

### Contributing Improvements
- Submit PRs to streaming modules
- Add new tests to `tests/test_streaming.py`
- Update documentation
- Share performance tips

---

## Backward Compatibility

### Existing Features Still Work
- ✅ Upload mode (unchanged)
- ✅ Record mode (unchanged)
- ✅ Mock mode (unchanged)
- ✅ All analysis models (same versions)
- ✅ Database storage (same schema)
- ✅ Export formats (same outputs)

### Database Compatibility
- Old calls still accessible
- New calls have `meta.mode = "live_streaming"`
- No schema changes
- Old data remains intact

---

## Summary

| Aspect | Details |
|--------|---------|
| **New Files** | 5 streaming modules + tests |
| **Modified Files** | streamlit_app.py, requirements.txt |
| **New Dependencies** | sounddevice >=0.4.5 |
| **Backward Compatible** | ✅ Yes |
| **Models Changed** | ❌ No (all same) |
| **Database Schema Changed** | ❌ No |
| **Performance Impact** | None on upload/record modes |
| **New Capabilities** | Real-time streaming analysis |
| **User Experience** | Live updates + final high-accuracy report |

---

## Next Steps

1. **Install**: `pip install -r requirements.txt`
2. **Train**: `python scripts/train_intent_model.py`
3. **Test**: `python tests/test_streaming.py`
4. **Run**: `streamlit run streamlit_app.py`
5. **Try**: Go to 🔴 Live Analysis tab and start recording
6. **Explore**: Review results, download exports, check database

---

**Happy streaming! 🎙️**

For detailed architecture information, see [STREAMING_ARCHITECTURE.md](STREAMING_ARCHITECTURE.md)
