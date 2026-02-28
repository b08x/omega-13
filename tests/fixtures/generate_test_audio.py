#!/usr/bin/env python3
"""
Generate synthetic test audio files for baseline measurements.

Creates test audio files with known properties:
- Mono 44100Hz, 1s duration
- Stereo 48000Hz, 2s duration
- Mono 16000Hz, 3s duration
- Mono 44100Hz with silence, 2s duration
- Stereo 48000Hz with silence, 2s duration
"""

import numpy as np
import soundfile as sf
from pathlib import Path


def generate_test_audio():
    """Generate all test audio files."""
    fixtures_dir = Path(__file__).parent / "audio"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    # Test 1: Mono 44100Hz, 1s, sine wave at 440Hz
    print("Generating mono_44100_1s.wav...")
    sr = 44100
    duration = 1.0
    freq = 440  # A4 note
    t = np.linspace(0, duration, int(sr * duration), False)
    audio = 0.3 * np.sin(2 * np.pi * freq * t)
    sf.write(fixtures_dir / "mono_44100_1s.wav", audio, sr)

    # Test 2: Stereo 48000Hz, 2s, different frequencies per channel
    print("Generating stereo_48000_2s.wav...")
    sr = 48000
    duration = 2.0
    t = np.linspace(0, duration, int(sr * duration), False)
    left = 0.3 * np.sin(2 * np.pi * 440 * t)  # 440Hz
    right = 0.3 * np.sin(2 * np.pi * 880 * t)  # 880Hz
    audio = np.column_stack([left, right])
    sf.write(fixtures_dir / "stereo_48000_2s.wav", audio, sr)

    # Test 3: Mono 16000Hz, 3s, sine wave at 220Hz
    print("Generating mono_16000_3s.wav...")
    sr = 16000
    duration = 3.0
    freq = 220  # A3 note
    t = np.linspace(0, duration, int(sr * duration), False)
    audio = 0.3 * np.sin(2 * np.pi * freq * t)
    sf.write(fixtures_dir / "mono_16000_3s.wav", audio, sr)

    # Test 4: Mono 44100Hz with silence (0.5s silence, 1s tone, 0.5s silence)
    print("Generating mono_44100_with_silence.wav...")
    sr = 44100
    silence_duration = 0.5
    tone_duration = 1.0
    freq = 440

    silence = np.zeros(int(sr * silence_duration))
    t = np.linspace(0, tone_duration, int(sr * tone_duration), False)
    tone = 0.3 * np.sin(2 * np.pi * freq * t)

    audio = np.concatenate([silence, tone, silence])
    sf.write(fixtures_dir / "mono_44100_with_silence.wav", audio, sr)

    # Test 5: Stereo 48000Hz with silence (0.5s silence, 1s tone, 0.5s silence)
    print("Generating stereo_48000_with_silence.wav...")
    sr = 48000
    silence_duration = 0.5
    tone_duration = 1.0

    silence_left = np.zeros(int(sr * silence_duration))
    silence_right = np.zeros(int(sr * silence_duration))

    t = np.linspace(0, tone_duration, int(sr * tone_duration), False)
    tone_left = 0.3 * np.sin(2 * np.pi * 440 * t)
    tone_right = 0.3 * np.sin(2 * np.pi * 880 * t)

    left = np.concatenate([silence_left, tone_left, silence_left])
    right = np.concatenate([silence_right, tone_right, silence_right])
    audio = np.column_stack([left, right])
    sf.write(fixtures_dir / "stereo_48000_with_silence.wav", audio, sr)

    # Test 6: Mono 44100Hz, very short (0.5s)
    print("Generating mono_44100_short.wav...")
    sr = 44100
    duration = 0.5
    freq = 440
    t = np.linspace(0, duration, int(sr * duration), False)
    audio = 0.3 * np.sin(2 * np.pi * freq * t)
    sf.write(fixtures_dir / "mono_44100_short.wav", audio, sr)

    # Test 7: Mono 16000Hz, longer (5s)
    print("Generating mono_16000_long.wav...")
    sr = 16000
    duration = 5.0
    freq = 220
    t = np.linspace(0, duration, int(sr * duration), False)
    audio = 0.3 * np.sin(2 * np.pi * freq * t)
    sf.write(fixtures_dir / "mono_16000_long.wav", audio, sr)

    print(
        f"\nGenerated {len(list(fixtures_dir.glob('*.wav')))} test audio files in {fixtures_dir}"
    )

    # Print file info
    for wav_file in sorted(fixtures_dir.glob("*.wav")):
        data, sr = sf.read(wav_file)
        if len(data.shape) == 1:
            channels = 1
        else:
            channels = data.shape[1]
        duration = len(data) / sr
        size_bytes = wav_file.stat().st_size
        print(
            f"  {wav_file.name}: {channels}ch, {sr}Hz, {duration:.2f}s, {size_bytes} bytes"
        )


if __name__ == "__main__":
    generate_test_audio()
