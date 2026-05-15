# INTELLISCORE v2.2 — Exact Run Commands for GitHub Codespaces

## Complete Setup in 10 Minutes

### Step 1: Extract Project (1 min)
```bash
tar -xzf intelliscore-v2-streaming.tar.gz
cd intelliscore-v2
```

### Step 2: Install Dependencies (2 min)
```bash
pip install -r requirements.txt
```

**Output expected:** ~20 packages installed, no errors

### Step 3: Train Intent Model (2 min)
```bash
python scripts/train_intent_model.py
```

**Output expected:** Model saved to `models/intent_classifier.pkl`

### Step 4: Verify Installation (1 min)
```bash
python tests/test_streaming.py
```

**Output expected:** ✅ All 6 tests passed

### Step 5: Run Dashboard (immediate)
```bash
streamlit run streamlit_app.py
```

**Output expected:**
```
  You can now view your Streamlit app in your browser.

  URL: http://localhost:8501
```

---

## Quick Test (Mock Mode - 2 min)

### In Browser
1. Navigate to `http://localhost:8501`
2. In sidebar: Change mode to **"mock"**
3. Click tab **"🔴 Live Analysis"**
4. Click **"▶️ Start Live Analysis"**
5. Wait 10 seconds
6. Click **"⏹️ Stop"**
7. See final report appear

**Expected:** Instant results (mock mode) + Full report displayed

---

## Live Test (Real Microphone - 5+ min)

### Prerequisites
- Grant browser microphone permission when prompted
- Microphone connected and working

### In Browser
1. Navigate to `http://localhost:8501`
2. In sidebar: Mode is **"whisper_local"** (default)
3. Click tab **"🔴 Live Analysis"**
4. Click **"▶️ Start Live Analysis"**
5. Speak into microphone (updates every 4 sec)
6. Watch:
   - Transcript growing
   - Intent bars updating
   - Emotion/tone changing
   - Stats updating
7. Click **"⏹️ Stop"** when done
8. Wait 1-2 min for final analysis
9. See final professional report

**Expected:** 
- Real-time updates during speaking
- Final report after 1-2 min
- Results exported to files
- Results stored in SQLite

---

## File Locations

### Project Structure
```
intelliscore-v2/
├── src/
│   ├── streaming/           ← NEW: Streaming modules
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── recorder.py
│   │   ├── chunk_processor.py
│   │   ├── aggregator.py
│   │   └── ui.py
│   ├── analysis/            (existing)
│   ├── asr/                 (existing)
│   ├── diarization/         (existing)
│   └── ... (other modules)
├── tests/
│   ├── test_streaming.py    ← NEW: Test suite
│   └── ... (other tests)
├── streamlit_app.py         (updated with Live tab)
├── requirements.txt         (updated)
├── STREAMING_GUIDE.md       ← NEW: User guide
├── STREAMING_ARCHITECTURE.md ← NEW: Technical docs
├── RELEASE_NOTES.md         ← NEW: Version info
├── IMPLEMENTATION_SUMMARY.md ← NEW: Overview
└── COMPLETION_SUMMARY.md    ← NEW: This guide
```

### Important Paths
| Path | Purpose |
|------|---------|
| `models/intent_classifier.pkl` | Trained intent model |
| `outputs/` | Exported results |
| `~/.streamlit/` | Streamlit config |

---

## Useful Commands

### View Logs
```bash
# During streamlit run, logs appear in terminal
# Press Ctrl+C to stop
```

### Reset Everything
```bash
cd intelliscore-v2
rm -rf models/intent_classifier.pkl
rm -rf outputs/*
pip install -r requirements.txt --force-reinstall
python scripts/train_intent_model.py
streamlit run streamlit_app.py
```

### Run Tests Again
```bash
python tests/test_streaming.py              # All tests
python tests/test_streaming.py --test state # Specific test
python tests/test_streaming.py --verbose    # Detailed output
```

### Check Dependencies
```bash
pip list | grep -E "(streamlit|torch|whisper|pyannote|sounddevice)"
```

### Access Results
```bash
# View exported files
ls -la outputs/

# View database
python -c "from src.storage import db; print(db.get_all_records()[:1])"
```

---

## Stopping the Dashboard

### In Browser
- Close browser tab (or just leave it)

### In Terminal
```bash
# Press Ctrl+C to stop Streamlit
# Normal exit
```

---

## Restarting the Dashboard

### Resume from Same Terminal
```bash
streamlit run streamlit_app.py
```

### New Terminal Session
```bash
cd intelliscore-v2
streamlit run streamlit_app.py
```

---

## Environment Variables

### Optional Configuration

```bash
# Use mock mode (for testing)
export INTELLISCORE_USE_API=mock
streamlit run streamlit_app.py

# Use Whisper local (for real analysis)
export INTELLISCORE_USE_API=whisper_local
streamlit run streamlit_app.py

# HuggingFace token (if using gated models)
export INTELLISCORE_HF_TOKEN=your_token_here
streamlit run streamlit_app.py
```

---

## Common Issues & Fixes

### Issue: `ModuleNotFoundError: No module named 'sounddevice'`
**Fix:**
```bash
pip install sounddevice>=0.4.5
```

### Issue: `No module named 'streamlit'`
**Fix:**
```bash
pip install -r requirements.txt
```

### Issue: Microphone not found
**Fix:**
1. In Codespaces: Grant browser permission
2. Check audio settings in OS
3. Use mock mode for testing
4. Try `--logger.level=debug` to see details

### Issue: Tests fail
**Fix:**
```bash
python tests/test_streaming.py --verbose  # See details
pip install -r requirements.txt           # Reinstall deps
python tests/test_streaming.py            # Try again
```

### Issue: Slow processing
**Fix:**
1. Use mock mode (instant)
2. Reduce chunk duration in code
3. Close other applications
4. Try on faster machine

---

## Performance Notes

### Typical Times
- Install deps: 2-3 min
- Train model: 1-2 min
- Run tests: 30-60 sec
- Mock test: 10-15 sec
- Real test (5 min call):
  - Recording: 5 min
  - Final analysis: 1-2 min
  - Total: 6-7 min

### Resource Usage
- Disk: 10 GB (models)
- RAM: 8+ GB (16+ GB recommended)
- CPU: 20-60% (varies by phase)
- Network: 0 (local only)

---

## What to Try First

### Quickest (Mock Mode - 2 min)
```bash
# 1. Setup
pip install -r requirements.txt
python scripts/train_intent_model.py

# 2. Run
streamlit run streamlit_app.py

# 3. Test
# → Go to "🔴 Live Analysis"
# → Change mode to "mock"
# → Click "▶️ Start"
# → Click "⏹️ Stop" after 10 sec
# → See instant results
```

### Real Test (With Microphone - 10+ min)
```bash
# 1. Setup
pip install -r requirements.txt
python scripts/train_intent_model.py

# 2. Run
streamlit run streamlit_app.py

# 3. Test
# → Go to "🔴 Live Analysis"
# → Mode is "whisper_local" (default)
# → Click "▶️ Start Live Analysis"
# → Speak into microphone for 1-5 min
# → Click "⏹️ Stop"
# → Wait 1-2 min for final analysis
# → See professional report
```

### Verify Everything (Tests - 5 min)
```bash
python tests/test_streaming.py

# Expected: ✅ All 6 tests passed
```

---

## Success Criteria

### Installation Successful If:
- ✅ All dependencies installed
- ✅ Intent model trained
- ✅ All tests pass
- ✅ Streamlit runs without errors

### Live Analysis Works If:
- ✅ "🔴 Live Analysis" tab visible
- ✅ Start button clickable
- ✅ Microphone detected
- ✅ Chunks processed (live updates)
- ✅ Stop button stops recording
- ✅ Final report generated
- ✅ Results exported
- ✅ Results stored in DB

### Everything Good If:
- ✅ All three modes work (Upload, Record, Live)
- ✅ Results comparable across modes
- ✅ No errors in logs
- ✅ Database stores results
- ✅ Tests all pass

---

## Next Steps After Setup

1. **Read guides:**
   - `STREAMING_GUIDE.md` — How to use
   - `STREAMING_ARCHITECTURE.md` — How it works

2. **Try examples:**
   - Mock mode (instant)
   - Real microphone (with speech)
   - Different audio lengths
   - Different speaking patterns

3. **Explore results:**
   - View exported files
   - Check database
   - Compare with upload mode
   - Download different formats

4. **Customize (optional):**
   - Change chunk duration
   - Modify aggregation strategy
   - Add custom metrics
   - Extend functionality

---

## Getting Help

### Documentation
- `STREAMING_GUIDE.md` — User guide
- `STREAMING_ARCHITECTURE.md` — Technical details
- `RELEASE_NOTES.md` — Version info
- Code comments — Implementation details

### Testing
- `python tests/test_streaming.py --verbose`
- `streamlit run streamlit_app.py --logger.level=debug`

### Issues
1. Check troubleshooting section above
2. Review logs in terminal
3. Run test suite for details
4. Check documentation

---

## Clean Reinstall

If something goes wrong:

```bash
# Remove everything
cd ..
rm -rf intelliscore-v2
rm -f intelliscore-v2-streaming.tar.gz

# Start fresh
tar -xzf intelliscore-v2-streaming.tar.gz
cd intelliscore-v2

# Clear Python cache
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Reinstall from scratch
pip install -r requirements.txt
python scripts/train_intent_model.py
python tests/test_streaming.py

# Run
streamlit run streamlit_app.py
```

---

## Ready to Go! 🚀

You now have everything you need to use INTELLISCORE v2.2 with Live Streaming Analysis.

**Just 5 steps to get started:**
1. Extract: `tar -xzf intelliscore-v2-streaming.tar.gz`
2. Install: `pip install -r requirements.txt`
3. Prepare: `python scripts/train_intent_model.py`
4. Verify: `python tests/test_streaming.py`
5. Run: `streamlit run streamlit_app.py`

**Then navigate to the 🔴 Live Analysis tab and start streaming!**

---

**Happy analyzing! 🎙️**
