"""
INTELLISCORE v2.2 — Streaming Analysis Test Suite
===================================================
Comprehensive tests for the new live streaming feature.

Usage:
    python tests/test_streaming.py                    # Run all tests
    python tests/test_streaming.py --test recorder    # Run specific test
    python tests/test_streaming.py --verbose          # Show detailed output
"""

import sys
import os
import tempfile
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import CONFIG
from src.utils import get_logger

logger = get_logger(__name__)


class TestStreaming:
    """Test suite for streaming feature."""
    
    @staticmethod
    def test_imports():
        """Test 1: All streaming modules import successfully."""
        print("\n" + "="*60)
        print("TEST 1: Import Streaming Modules")
        print("="*60)
        
        try:
            from src.streaming.state import StreamingState, ChunkResult
            print("✅ src.streaming.state imported")
            
            from src.streaming.recorder import StreamingRecorder
            print("✅ src.streaming.recorder imported")
            
            from src.streaming.chunk_processor import ChunkProcessor
            print("✅ src.streaming.chunk_processor imported")
            
            from src.streaming.aggregator import ChunkAggregator
            print("✅ src.streaming.aggregator imported")
            
            from src.streaming.ui import render_live_badge, render_streaming_controls
            print("✅ src.streaming.ui imported")
            
            print("\n✅ All imports successful!")
            return True
        
        except Exception as e:
            print(f"❌ Import failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def test_state_management():
        """Test 2: Session state management."""
        print("\n" + "="*60)
        print("TEST 2: Session State Management")
        print("="*60)
        
        try:
            from src.streaming.state import StreamingState, ChunkResult
            from datetime import datetime
            
            # Create state
            state = StreamingState()
            assert not state.is_active, "Initial state should not be active"
            print("✅ StreamingState created")
            
            # Start session
            state.start_session()
            assert state.is_active, "State should be active after start"
            assert state.is_recording, "State should be recording after start"
            print("✅ Session started")
            
            # Add chunk
            chunk = ChunkResult(
                chunk_id=0,
                timestamp=datetime.now(),
                duration=4.0,
                text="Hello world",
                start_time=0.0,
                end_time=4.0,
                speakers=["SPEAKER"],
                intent_scores={"PTP": 0.8},
                sentiment={"label": "neutral", "score": 0.9},
                audio_tone=None,
                error=None
            )
            state.add_chunk(chunk)
            assert state.get_chunk_count() == 1, "Chunk count should be 1"
            print("✅ Chunk added to state")
            
            # Check transcript
            transcript = state.get_live_transcript()
            assert "Hello world" in transcript, "Transcript should contain chunk text"
            print(f"✅ Transcript generated: {len(transcript)} chars")
            
            # Stop session
            state.stop_session()
            assert not state.is_recording, "State should not be recording after stop"
            print("✅ Session stopped")
            
            # Error logging
            state.add_error("Test error message")
            assert len(state.error_log) == 1, "Error should be logged"
            print("✅ Error logging works")
            
            # Serialization
            state_dict = state.to_dict()
            assert state_dict["chunk_count"] == 1, "Serialized state should have chunk count"
            print(f"✅ State serialized: {state_dict}")
            
            print("\n✅ All state management tests passed!")
            return True
        
        except Exception as e:
            print(f"❌ State management test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def test_chunk_processor():
        """Test 3: Chunk processor (mock mode)."""
        print("\n" + "="*60)
        print("TEST 3: Chunk Processor")
        print("="*60)
        
        try:
            from src.streaming.chunk_processor import ChunkProcessor
            
            # Initialize processor
            processor = ChunkProcessor()
            processor.load_resources()
            print("✅ ChunkProcessor loaded")
            
            # Create dummy audio (4 seconds at 16kHz)
            audio = np.random.randn(4 * 16000).astype(np.float32)
            
            # Process chunk
            result = processor.process_chunk(audio, 16000, 0, 0.0, 4.0)
            
            # Validate result
            assert result["chunk_id"] == 0, "Chunk ID should match"
            assert result["duration"] == 4.0, "Duration should be 4.0"
            assert result["start_time"] == 0.0, "Start time should be 0"
            assert result["end_time"] == 4.0, "End time should be 4"
            print("✅ Chunk metadata correct")
            
            if CONFIG.use_api == "mock":
                assert result["text"], "Mock mode should produce text"
                print(f"✅ Transcription (mock): '{result['text'][:50]}...'")
            
            assert isinstance(result["intent_scores"], dict), "Intent scores should be dict"
            assert isinstance(result["sentiment"], (dict, type(None))), "Sentiment should be dict or None"
            assert isinstance(result["tone"], (dict, type(None))), "Tone should be dict or None"
            print("✅ Analysis results structured correctly")
            
            print("\n✅ All chunk processor tests passed!")
            return True
        
        except Exception as e:
            print(f"❌ Chunk processor test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def test_aggregator():
        """Test 4: Chunk aggregator (mock mode)."""
        print("\n" + "="*60)
        print("TEST 4: Chunk Aggregator")
        print("="*60)
        
        try:
            from src.streaming.aggregator import ChunkAggregator
            
            # Initialize aggregator
            aggregator = ChunkAggregator()
            aggregator.load_resources()
            print("✅ ChunkAggregator loaded")
            
            # Test intent score aggregation
            chunk_results = [
                {"intent_scores": {"PTP": 0.8, "Refusal": 0.2}},
                {"intent_scores": {"PTP": 0.7, "Refusal": 0.3}},
                {"intent_scores": {"PTP": 0.9, "Refusal": 0.1}},
            ]
            
            aggregated = aggregator._aggregate_intent_scores(chunk_results)
            
            assert "PTP" in aggregated, "PTP should be in aggregated scores"
            assert "Refusal" in aggregated, "Refusal should be in aggregated scores"
            
            # Check average
            expected_ptp = (0.8 + 0.7 + 0.9) / 3
            assert abs(aggregated["PTP"] - expected_ptp) < 0.001, "PTP average should be correct"
            print(f"✅ Intent score aggregation: PTP={aggregated['PTP']:.3f}")
            
            # Test audio merging
            chunks = [
                np.random.randn(4 * 16000).astype(np.float32),
                np.random.randn(4 * 16000).astype(np.float32),
                np.random.randn(4 * 16000).astype(np.float32),
            ]
            
            merged = aggregator.merge_audio_chunks(chunks, sr=16000)
            expected_len = len(chunks[0]) + len(chunks[1]) + len(chunks[2])
            assert len(merged) == expected_len, f"Merged audio length should be {expected_len}"
            print(f"✅ Audio merging: {len(chunks)} chunks → {len(merged)/16000:.1f}s audio")
            
            print("\n✅ All aggregator tests passed!")
            return True
        
        except Exception as e:
            print(f"❌ Aggregator test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def test_end_to_end_mock():
        """Test 5: End-to-end mock streaming (without actual microphone)."""
        print("\n" + "="*60)
        print("TEST 5: End-to-End Mock Streaming")
        print("="*60)
        
        try:
            from src.streaming.chunk_processor import ChunkProcessor
            from src.streaming.aggregator import ChunkAggregator
            import soundfile as sf
            
            # Simulate streaming: create 3 chunks
            processor = ChunkProcessor()
            processor.load_resources()
            
            aggregator = ChunkAggregator()
            aggregator.load_resources()
            
            print("✅ Resources loaded")
            
            # Create simulated chunks
            chunk_results = []
            audio_chunks = []
            
            for i in range(3):
                # Create dummy audio
                audio = np.random.randn(4 * 16000).astype(np.float32) * 0.1
                audio_chunks.append(audio)
                
                # Process chunk
                result = processor.process_chunk(audio, 16000, i, i*4, (i+1)*4)
                chunk_results.append(result)
                print(f"✅ Chunk {i} processed: {result['text'][:30] if result['text'] else '(no text)'}...")
            
            print(f"✅ {len(chunk_results)} chunks processed")
            
            # Merge audio
            merged_audio = aggregator.merge_audio_chunks(audio_chunks, sr=16000)
            print(f"✅ Audio merged: {len(merged_audio)/16000:.1f}s")
            
            # Save merged audio
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                sf.write(tmp.name, merged_audio, 16000)
                merged_path = tmp.name
            
            print(f"✅ Merged audio saved to: {merged_path}")
            
            # Run aggregation (mock mode)
            if CONFIG.use_api == "mock":
                final_result = aggregator.aggregate_results(chunk_results, merged_path)
                
                assert "transcript" in final_result, "Final result should have transcript"
                assert "turns" in final_result, "Final result should have turns"
                assert "intent" in final_result, "Final result should have intent"
                assert "sentiment" in final_result, "Final result should have sentiment"
                
                print(f"✅ Final aggregation complete")
                print(f"   - Transcript: {len(final_result['transcript'])} chars")
                print(f"   - Turns: {len(final_result['turns'])}")
                print(f"   - Intent: {final_result.get('intent', {}).get('label', '—')}")
            else:
                print("⚠️  Skipping full aggregation (not in mock mode)")
            
            # Cleanup
            if os.path.exists(merged_path):
                os.remove(merged_path)
            
            print("\n✅ End-to-end mock streaming test passed!")
            return True
        
        except Exception as e:
            print(f"❌ End-to-end test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    @staticmethod
    def test_requirements():
        """Test 6: Check required dependencies."""
        print("\n" + "="*60)
        print("TEST 6: Check Required Dependencies")
        print("="*60)
        
        required = {
            "streamlit": "Dashboard",
            "faster-whisper": "ASR",
            "pyannote.audio": "Diarization",
            "transformers": "ML models",
            "torch": "Deep learning",
            "soundfile": "Audio I/O",
            "numpy": "Numerical computing",
            "scipy": "Signal processing",
            "sounddevice": "🆕 Microphone input",
        }
        
        missing = []
        
        for pkg, desc in required.items():
            try:
                __import__(pkg)
                print(f"✅ {pkg:25} - {desc}")
            except ImportError:
                print(f"❌ {pkg:25} - {desc} [MISSING]")
                missing.append(pkg)
        
        if missing:
            print(f"\n⚠️  Missing packages: {', '.join(missing)}")
            print("Install with: pip install -r requirements.txt")
            return False
        
        print("\n✅ All required dependencies available!")
        return True


def main():
    """Run all tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description="INTELLISCORE Streaming Tests")
    parser.add_argument("--test", help="Run specific test", choices=[
        "imports", "state", "processor", "aggregator", "end-to-end", "requirements"
    ])
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    print("\n")
    print("╔════════════════════════════════════════════════════════════╗")
    print("║  INTELLISCORE v2.2 — Streaming Analysis Test Suite       ║")
    print("║  Testing Live Streaming Architecture                     ║")
    print("╚════════════════════════════════════════════════════════════╝")
    
    tests = {
        "imports": TestStreaming.test_imports,
        "state": TestStreaming.test_state_management,
        "processor": TestStreaming.test_chunk_processor,
        "aggregator": TestStreaming.test_aggregator,
        "end-to-end": TestStreaming.test_end_to_end_mock,
        "requirements": TestStreaming.test_requirements,
    }
    
    results = {}
    
    if args.test:
        # Run specific test
        if args.test in tests:
            results[args.test] = tests[args.test]()
    else:
        # Run all tests
        for name, test_func in tests.items():
            try:
                results[name] = test_func()
            except Exception as e:
                print(f"\n❌ Unexpected error in {name}: {e}")
                results[name] = False
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}  {name:20}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Streaming feature is ready to use.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. See details above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
