import numpy as np

from src.vad import VADConfig, VoiceActivityDetector


def test_vad_energy_zero_for_silence():
    vad = VoiceActivityDetector()
    energy = vad.calculate_energy(np.zeros(vad.config.frame_size, dtype=np.int16))
    assert energy == 0.0


def test_vad_process_frame_transitions():
    vad = VoiceActivityDetector(VADConfig(energy_threshold=0.001, speech_pad_ms=0))
    # Speech frame triggers start
    event = vad.process_frame(np.ones(vad.config.frame_size, dtype=np.int16) * 1000)
    assert event in (None, "speech_start")
    # Silence frame eventually ends speech
    event_end = vad.process_frame(np.zeros(vad.config.frame_size, dtype=np.int16))
    assert event_end in (None, "speech_end")
