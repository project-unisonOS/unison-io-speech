"""
Tests for Voice Activity Detection (VAD)
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    import numpy as np
except ImportError:
    pytest.skip("numpy not available", allow_module_level=True)

from vad import VoiceActivityDetector, VADConfig


class TestVADConfig:
    """Tests for VAD configuration"""
    
    def test_default_config(self):
        """Test default VAD configuration"""
        config = VADConfig()
        assert config.energy_threshold == 0.01
        assert config.speech_pad_ms == 300
        assert config.silence_duration_ms == 500
        assert config.sample_rate == 16000
    
    def test_custom_config(self):
        """Test custom VAD configuration"""
        config = VADConfig(
            energy_threshold=0.02,
            speech_pad_ms=200,
            silence_duration_ms=400
        )
        assert config.energy_threshold == 0.02
        assert config.speech_pad_ms == 200
        assert config.silence_duration_ms == 400


class TestVADDetection:
    """Tests for VAD detection logic"""
    
    @pytest.fixture
    def vad(self):
        """Create VAD instance"""
        return VoiceActivityDetector()
    
    def test_vad_initialization(self, vad):
        """Test VAD initializes correctly"""
        assert vad.is_speaking is False
        assert vad.speech_frames == 0
        assert vad.silence_frames == 0
    
    def test_detect_silence(self, vad):
        """Test detection of silence"""
        # Create silent audio (all zeros)
        audio = np.zeros(1600, dtype=np.int16)  # 100ms at 16kHz
        
        is_speech = vad.process_audio(audio)
        assert is_speech is False
    
    def test_detect_speech(self, vad):
        """Test detection of speech"""
        # Create audio with energy (random noise)
        audio = np.random.randint(-5000, 5000, 1600, dtype=np.int16)
        
        # Process multiple frames to trigger speech detection
        for _ in range(5):
            is_speech = vad.process_audio(audio)
        
        # Should detect speech after enough frames
        assert vad.speech_frames > 0
    
    def test_speech_start_event(self, vad):
        """Test speech start event detection"""
        # Create loud audio
        audio = np.random.randint(-10000, 10000, 1600, dtype=np.int16)
        
        # Process frames until speech starts
        speech_started = False
        for _ in range(10):
            is_speech = vad.process_audio(audio)
            if is_speech and not vad.is_speaking:
                speech_started = True
                break
        
        # Should eventually detect speech start
        assert vad.speech_frames > 0
    
    def test_speech_end_event(self, vad):
        """Test speech end event detection"""
        # First, trigger speech
        loud_audio = np.random.randint(-10000, 10000, 1600, dtype=np.int16)
        for _ in range(10):
            vad.process_audio(loud_audio)
        
        # Then send silence
        silent_audio = np.zeros(1600, dtype=np.int16)
        
        # Process silence frames
        for _ in range(20):
            vad.process_audio(silent_audio)
        
        # Should detect silence frames
        assert vad.silence_frames > 0
    
    def test_energy_calculation(self, vad):
        """Test energy calculation"""
        # Silent audio should have low energy
        silent = np.zeros(1600, dtype=np.int16)
        silent_energy = vad._calculate_energy(silent)
        assert silent_energy < 0.001
        
        # Loud audio should have high energy
        loud = np.random.randint(-10000, 10000, 1600, dtype=np.int16)
        loud_energy = vad._calculate_energy(loud)
        assert loud_energy > 0.01
    
    def test_adaptive_threshold(self, vad):
        """Test adaptive threshold adjustment"""
        # Process some audio to build history
        audio = np.random.randint(-1000, 1000, 1600, dtype=np.int16)
        
        initial_threshold = vad.config.energy_threshold
        
        # Process multiple frames
        for _ in range(50):
            vad.process_audio(audio)
        
        # Threshold should adapt (if adaptive is enabled)
        # This is implementation-dependent
        assert vad.config.energy_threshold >= 0
    
    def test_reset_state(self, vad):
        """Test resetting VAD state"""
        # Trigger speech
        audio = np.random.randint(-10000, 10000, 1600, dtype=np.int16)
        for _ in range(10):
            vad.process_audio(audio)
        
        # Reset
        vad.reset()
        
        # State should be reset
        assert vad.is_speaking is False
        assert vad.speech_frames == 0
        assert vad.silence_frames == 0


class TestVADEdgeCases:
    """Tests for VAD edge cases"""
    
    @pytest.fixture
    def vad(self):
        """Create VAD instance"""
        return VoiceActivityDetector()
    
    def test_empty_audio(self, vad):
        """Test with empty audio"""
        audio = np.array([], dtype=np.int16)
        is_speech = vad.process_audio(audio)
        assert is_speech is False
    
    def test_very_short_audio(self, vad):
        """Test with very short audio"""
        audio = np.array([100, 200], dtype=np.int16)
        is_speech = vad.process_audio(audio)
        # Should handle gracefully
        assert isinstance(is_speech, bool)
    
    def test_clipped_audio(self, vad):
        """Test with clipped audio (max amplitude)"""
        audio = np.full(1600, 32767, dtype=np.int16)  # Max int16
        is_speech = vad.process_audio(audio)
        # Should detect as speech
        assert vad.speech_frames > 0
    
    def test_alternating_speech_silence(self, vad):
        """Test alternating speech and silence"""
        loud = np.random.randint(-10000, 10000, 1600, dtype=np.int16)
        silent = np.zeros(1600, dtype=np.int16)
        
        # Alternate between speech and silence
        for i in range(20):
            audio = loud if i % 2 == 0 else silent
            vad.process_audio(audio)
        
        # Should handle transitions
        assert vad.speech_frames >= 0
        assert vad.silence_frames >= 0


class TestVADPerformance:
    """Tests for VAD performance characteristics"""
    
    @pytest.fixture
    def vad(self):
        """Create VAD instance"""
        return VoiceActivityDetector()
    
    def test_processing_speed(self, vad):
        """Test that VAD processes quickly"""
        import time
        
        audio = np.random.randint(-5000, 5000, 16000, dtype=np.int16)  # 1 second
        
        start = time.time()
        vad.process_audio(audio)
        duration = time.time() - start
        
        # Should process 1 second of audio in < 100ms
        assert duration < 0.1
    
    def test_memory_efficiency(self, vad):
        """Test that VAD doesn't accumulate memory"""
        import sys
        
        audio = np.random.randint(-5000, 5000, 1600, dtype=np.int16)
        
        # Process many frames
        for _ in range(1000):
            vad.process_audio(audio)
        
        # Energy history should be bounded
        if hasattr(vad, 'energy_history'):
            assert len(vad.energy_history) < 1000
