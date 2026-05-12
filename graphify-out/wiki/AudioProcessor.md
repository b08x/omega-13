# AudioProcessor

> God node · 29 connections · `src/omega13/audio_processor.py`

## Connections by Relation

### calls
- [[.setup()]] `INFERRED`
- [[._file_writer()]] `EXTRACTED`
- [[.setUp()]] `INFERRED`
- [[run_standalone()]] `INFERRED`
- [[.setUp()]] `INFERRED`
- [[processor()]] `INFERRED`

### contains
- [[audio_processor.py]] `EXTRACTED`

### method
- [[._validate_cli_tools_availability()]] `EXTRACTED`
- [[._generate_output_path()]] `EXTRACTED`
- [[.downsample()]] `EXTRACTED`
- [[.encode_mp3()]] `EXTRACTED`
- [[.get_audio_info()]] `EXTRACTED`
- [[.convert_to_pcm()]] `EXTRACTED`
- [[.process_pipeline()]] `EXTRACTED`
- [[.trim_silence()]] `EXTRACTED`
- [[._get_quality_params()]] `EXTRACTED`
- [[.preprocess_for_transcription()]] `EXTRACTED`
- [[.__init__()]] `EXTRACTED`
- [[.__enter__()]] `EXTRACTED`
- [[.__exit__()]] `EXTRACTED`

### rationale_for
- [[Audio preprocessing pipeline using FFmpeg and SoX.]] `EXTRACTED`

### uses
- [[AudioEngine]] `INFERRED`
- [[BaselineMeasurementRunner]] `INFERRED`
- [[TestFormatConversion]] `INFERRED`
- [[TestMetadataExtraction]] `INFERRED`
- [[TestMP3Encoding]] `INFERRED`
- [[OperationMetrics]] `INFERRED`
- [[TestMetadataComparison]] `INFERRED`
- [[AudioMetrics]] `INFERRED`

---

*Part of the graphify knowledge wiki. See [[index]] to navigate.*