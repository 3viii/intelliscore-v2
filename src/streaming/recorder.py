"""
Continuous microphone recorder for streaming audio capture.
Uses threading + queue for non-blocking recording and chunk generation.
"""

import threading
import queue
import numpy as np
import soundfile as sf
from typing import Optional, Tuple
import logging
import time

logger = logging.getLogger(__name__)


class StreamingRecorder:
    """
    Records audio from microphone in chunks using threading.
    
    Non-blocking architecture:
    - Recording runs in background thread
    - Chunks are placed on a queue as they're captured
    - Main thread can check for new chunks without blocking
    """
    
    def __init__(self, 
                 chunk_duration: float = 4.0,
                 sample_rate: int = 16000,
                 channels: int = 1):
        """
        Args:
            chunk_duration: Duration of each chunk in seconds (3-5 recommended)
            sample_rate: Audio sample rate in Hz (16000 for Whisper)
            channels: Number of audio channels (1 = mono)
        """
        self.chunk_duration = chunk_duration
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_samples = int(chunk_duration * sample_rate)
        
        self.is_recording = False
        self.recording_thread: Optional[threading.Thread] = None
        self.chunk_queue: queue.Queue = queue.Queue()
        self.error_queue: queue.Queue = queue.Queue()
        
        self.total_samples_recorded = 0
        self.stop_event = threading.Event()
    
    def start(self) -> None:
        """Start recording in background thread."""
        if self.is_recording:
            logger.warning("Recording already active")
            return
        
        self.is_recording = True
        self.stop_event.clear()
        self.total_samples_recorded = 0
        self.recording_thread = threading.Thread(target=self._record_loop, daemon=True)
        self.recording_thread.start()
        logger.info(f"Recording started (chunk_duration={self.chunk_duration}s, sr={self.sample_rate})")
    
    def stop(self) -> None:
        """Stop recording."""
        if not self.is_recording:
            logger.warning("Recording not active")
            return
        
        self.stop_event.set()
        if self.recording_thread:
            self.recording_thread.join(timeout=5.0)
        
        self.is_recording = False
        logger.info(f"Recording stopped (total samples: {self.total_samples_recorded})")
    
    def get_chunk(self, block: bool = False, timeout: Optional[float] = 1.0) -> Optional[np.ndarray]:
        """
        Get next audio chunk from queue.
        
        Args:
            block: Whether to block if queue is empty
            timeout: Timeout in seconds (if block=True)
        
        Returns:
            Audio chunk as numpy array, or None if queue empty/timeout
        """
        try:
            return self.chunk_queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def get_error(self) -> Optional[str]:
        """Get next error from error queue."""
        try:
            return self.error_queue.get_nowait()
        except queue.Empty:
            return None
    
    def _record_loop(self) -> None:
        """Background recording loop (runs in thread)."""
        try:
            import sounddevice as sd
        except ImportError:
            self.error_queue.put("sounddevice not installed. Install with: pip install sounddevice")
            return
        
        try:
            logger.info(f"Opening audio device (channels={self.channels}, sr={self.sample_rate})")
            
            # Initialize recording stream
            audio_buffer = np.zeros((self.chunk_samples, self.channels), dtype=np.float32)
            stream = sd.InputStream(
                channels=self.channels,
                samplerate=self.sample_rate,
                blocksize=self.sample_rate // 4,  # 250ms blocks
                dtype=np.float32,
            )
            
            with stream:
                buffer_idx = 0
                
                while not self.stop_event.is_set():
                    try:
                        # Read a small block from the stream (non-blocking within timeout)
                        block = stream.read(self.sample_rate // 4)
                        
                        if block[0].size == 0:
                            continue  # No data available
                        
                        data = block[0]
                        
                        # Convert stereo to mono if needed
                        if data.ndim > 1 and data.shape[1] > 1:
                            data = data.mean(axis=1)
                        elif data.ndim > 1:
                            data = data.squeeze()
                        
                        # Fill chunk buffer
                        chunk_remaining = self.chunk_samples - buffer_idx
                        data_samples = min(len(data), chunk_remaining)
                        
                        audio_buffer[buffer_idx:buffer_idx + data_samples] = data[:data_samples].reshape(-1, 1)
                        buffer_idx += data_samples
                        self.total_samples_recorded += data_samples
                        
                        # If chunk is full, emit it
                        if buffer_idx >= self.chunk_samples:
                            chunk = audio_buffer.copy().squeeze()
                            self.chunk_queue.put(chunk)
                            
                            # Reset buffer for next chunk
                            audio_buffer = np.zeros((self.chunk_samples, self.channels), dtype=np.float32)
                            buffer_idx = 0
                    
                    except Exception as e:
                        logger.error(f"Error in recording loop: {e}")
                        self.error_queue.put(f"Recording error: {e}")
                        break
        
        except Exception as e:
            logger.error(f"Recording device error: {e}")
            self.error_queue.put(f"Device error: {e}")
    
    def save_all_chunks(self, output_path: str) -> None:
        """
        Save all accumulated chunks to a WAV file.
        (Utility for testing/debugging)
        """
        chunks = []
        while True:
            chunk = self.get_chunk(block=False)
            if chunk is None:
                break
            chunks.append(chunk)
        
        if chunks:
            audio = np.concatenate(chunks)
            sf.write(output_path, audio, self.sample_rate)
            logger.info(f"Saved {len(chunks)} chunks to {output_path}")
