# AudioProcessor Pipeline

> 44 nodes · cohesion 0.06

## Key Concepts

- **AudioProcessor** (29 connections) — `src/omega13/audio_processor.py`
- **audio_processor.py** (13 connections) — `src/omega13/audio_processor.py`
- **TestMP3Encoding** (10 connections) — `tests/test_mp3_encoding.py`
- **._generate_output_path()** (7 connections) — `src/omega13/audio_processor.py`
- **._validate_cli_tools_availability()** (7 connections) — `src/omega13/audio_processor.py`
- **.encode_mp3()** (6 connections) — `src/omega13/audio_processor.py`
- **.convert_to_pcm()** (5 connections) — `src/omega13/audio_processor.py`
- **.process_pipeline()** (4 connections) — `src/omega13/audio_processor.py`
- **_get_ver()** (4 connections) — `src/omega13/audio_processor.py`
- **._get_quality_params()** (3 connections) — `src/omega13/audio_processor.py`
- **.preprocess_for_transcription()** (3 connections) — `src/omega13/audio_processor.py`
- **.trim_silence()** (3 connections) — `src/omega13/audio_processor.py`
- **check_ffmpeg_available()** (3 connections) — `src/omega13/audio_processor.py`
- **check_sox_available()** (3 connections) — `src/omega13/audio_processor.py`
- **get_ffmpeg_version()** (3 connections) — `src/omega13/audio_processor.py`
- **get_sox_version()** (3 connections) — `src/omega13/audio_processor.py`
- **.setUp()** (3 connections) — `tests/test_mp3_encoding.py`
- **.__init__()** (2 connections) — `src/omega13/audio_processor.py`
- **test_mp3_encoding.py** (2 connections) — `tests/test_mp3_encoding.py`
- **.test_encode_mp3_auto_output_path()** (2 connections) — `tests/test_mp3_encoding.py`
- **.test_encode_mp3_custom_bitrate()** (2 connections) — `tests/test_mp3_encoding.py`
- **.test_encode_mp3_default_bitrate()** (2 connections) — `tests/test_mp3_encoding.py`
- **.test_encode_mp3_invalid_bitrate_type()** (2 connections) — `tests/test_mp3_encoding.py`
- **.test_encode_mp3_nonexistent_input()** (2 connections) — `tests/test_mp3_encoding.py`
- **.__enter__()** (1 connections) — `src/omega13/audio_processor.py`
- *... and 19 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `src/omega13/audio_processor.py`
- `tests/test_mp3_encoding.py`

## Audit Trail

- EXTRACTED: 125 (87%)
- INFERRED: 18 (13%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*