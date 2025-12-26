# Omega-13 Refactor Backlog: Provider Gateway Architecture

## Overview

Refactor the transcription engine to support multiple backends via a Provider Gateway (Strategy Pattern), with Podman Quadlets for local container management and cloud API fallbacks.

## Phase 1: Foundation

### 1. Create Provider Protocol Interface

- [ ] Create `src/omega13/providers/` directory
- [ ] Define `TranscriptionProvider` Protocol with required methods:
  - `transcribe(audio_path: Path) -> dict` (returns `{'text': str, 'language': str, ...}`)
  - `health_check() -> bool`
- [ ] Create `TranscriptionError` exception class for unified error handling

### 2. Update Configuration Schema

- [ ] Refactor `src/omega13/config.py` to support polymorphic provider configuration
- [ ] Update config structure to:

  ```json
  {
    "transcription": {
      "active_provider": "local_podman",
      "fallback_chain": ["huggingface", "groq", "gemini", "deepgram", "assemblyai"],
      "providers": {
        "local_podman": {
          "type": "openai_compatible",
          "base_url": "http://localhost:8080/v1",
          "api_key": "not-needed",
          "model": "whisper-1",
          "timeout": 600
        },
        "huggingface": {
          "type": "openai_compatible",
          "base_url": "https://your-endpoint.cloud/api/v1",
          "api_key": "${HF_API_TOKEN}",
          "model": "openai/whisper-large-v3",
          "timeout": 120
        },
        "groq": {
          "type": "openai_compatible",
          "base_url": "https://api.groq.com/openai/v1",
          "api_key": "${GROQ_API_KEY}",
          "model": "whisper-large-v3-turbo",
          "timeout": 120
        },
        "gemini": {
          "type": "openai_compatible",
          "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
          "api_key": "${GEMINI_API_KEY}",
          "model": "gemini-2.0-flash",
          "timeout": 120
        },
        "openai": {
          "type": "openai_compatible",
          "base_url": "https://api.openai.com/v1",
          "api_key": "${OPENAI_API_KEY}",
          "model": "whisper-1",
          "timeout": 120,
          "_note": "Optional - example provider"
        },
        "deepgram": {
          "type": "deepgram",
          "api_key": "${DEEPGRAM_API_KEY}",
          "model": "nova-3",
          "features": ["smart_format", "punctuate", "diarize"],
          "_note": "Phase 2 - for streaming/diarization"
        },
        "assemblyai": {
          "type": "assemblyai",
          "api_key": "${ASSEMBLYAI_API_KEY}",
          "features": ["speaker_labels", "auto_chapters"],
          "_note": "Phase 2 - for diarization/chapters"
        }
      }
    }
  }
  ```

- **Note**: Provider types: `openai_compatible` for standardized providers (Hugging Face, Groq, Gemini, local servers), `deepgram`/`assemblyai` for SDKs with proprietary response formats
- **Fallback Chain**: Array of provider names tried in order if primary fails. Example shows user preference: HF → Groq → Gemini → Deepgram → AssemblyAI
- **User Customizable**: Each user can define their own fallback order based on cost, speed, privacy preferences
- **whisper.cpp**: Supports both `/inference` (legacy) and `/v1/audio/transcriptions` (OpenAI-compatible). Configure server for OpenAI endpoint or add endpoint fallback logic

- [ ] Add migration logic for existing configs (legacy `server_url` → new structure)
- [ ] Implement config validation for required provider fields

## Phase 2: Provider Implementations

### 3. Local Podman Provider

- [ ] Create `src/omega13/providers/local_podman.py`
- [ ] Implement `LocalPodmanProvider` class
- [ ] Add Podman SDK integration (with lazy import inside class)
- [ ] Implement `health_check()` via systemd service status check
- [ ] Implement `transcribe()` using HTTP to local container API
- [ ] Add Quadlet-specific error messages (e.g., "Service not enabled, run: systemctl --user enable omega13-transcription")

### 4. OpenAI-Compatible Provider (Unified Cloud + Local)

- [ ] Create `src/omega13/providers/openai_compatible.py`
- [ ] Implement `OpenAICompatibleProvider` class (works with Groq, Gemini, local servers)
- [ ] Uses standard `/v1/audio/transcriptions` endpoint (multipart/form-data)
- [ ] Response format: `{"text": "...", "language": "...", "segments": [...]}`
- [ ] **Priority providers**: Hugging Face Inference, Groq, Gemini, LocalAI, vLLM, Ollama, faster-whisper-server
- [ ] **Optional**: OpenAI service (example only, not required)
- [ ] Hugging Face endpoint: `https://<endpoint>.cloud/api/v1/audio/transcriptions` (OpenAI-compatible)
- [ ] API key validation and environment variable substitution (`${VAR_NAME}`)
- [ ] Unified exception handling → `TranscriptionError`
- [ ] No provider-specific SDK required (uses `requests` library)
- [ ] **Note**: whisper.cpp supports `/v1/audio/transcriptions` when configured, or can fallback to `/inference`

### 5. Deepgram Provider (Optional - Phase 2)

- [ ] Create `src/omega13/providers/deepgram.py`
- [ ] Implement `DeepgramProvider` class using Deepgram SDK
- [ ] **Response Normalization**: Convert `results.channels[0].alternatives[0].transcript` → `TranscriptionResult`
- [ ] Handle Deepgram-specific features:
  - Streaming transcription
  - Speaker diarization (`speaker_labels`)
  - Smart formatting, punctuation
- [ ] Map Deepgram exceptions → `TranscriptionError`
- [ ] Only implement if users request streaming/diarization features

### 6. AssemblyAI Provider (Optional - Phase 2)

- [ ] Create `src/omega13/providers/assemblyai.py`
- [ ] Implement `AssemblyAIProvider` class using AssemblyAI SDK
- [ ] **Response Normalization**: Convert `response.text` + `utterances` → `TranscriptionResult`
- [ ] Handle AssemblyAI-specific features:
  - Speaker diarization (`speaker_labels`)
  - Auto chapters
  - Custom vocabulary
  - PII redaction
- [ ] Map AssemblyAI exceptions → `TranscriptionError`
- [ ] Only implement if users request diarization/chapter features

## Phase 3: Service Layer Refactoring

### 7. Refactor TranscriptionService

- [ ] Modify `src/omega13/transcription.py`:
  - Accept `TranscriptionProvider` in `__init__` via dependency injection
  - Replace raw `requests` logic in `_transcribe_file()` with `self.provider.transcribe(audio_path)`
  - Keep existing threading, locking, and `shutdown_event` logic
  - **Add fallback chain support**: Try providers in order from `fallback_chain` array until success
  - Log which provider succeeded for user visibility

### 8. Create Provider Gateway/Factory

- [ ] Create `src/omega13/providers/factory.py`
- [ ] Implement `create_provider(config: Config) -> TranscriptionProvider`
- [ ] Add `ImportError` handling for missing SDK dependencies
- [ ] Return mock provider for testing when environment variable set

### 9. Update Application Integration

- [ ] Modify `src/omega13/app.py`:
  - Initialize `TranscriptionService` with provider from factory
  - Create fallback provider chain from config
  - Update startup sequence to check primary provider health
  - Display provider-specific error messages in UI
  - Show which provider handled transcription (primary vs fallback)

## Phase 4: Podman Quadlet Integration

### 10. Create Quadlet Generator

- [ ] Create `src/omega13/quadlet.py`
- [ ] Implement Quadlet unit file generator:
  - Generate `~/.config/containers/systemd/omega13-transcription.container`
  - Include volume mounts for model directory
  - Configure port exposure and restart policy
- [ ] Add helper script for `systemctl --user daemon-reload`

### 11. First-Run Wizard

- [ ] Create `src/omega13/wizard.py`
- [ ] Implement provider selection interface (Textual-based)
- [ ] Add configuration steps for each provider:
  - Local Podman: Generate Quadlet file, provide systemctl commands
  - Cloud: Prompt for API keys, model selection
- [ ] Validate configuration before saving
- [ ] Trigger provider health check after setup

## Phase 5: Dependencies & Extras

### 12. Update PyProject.toml

- [ ] Add optional dependencies section:

  ```toml
  [project.optional-dependencies]
  local = ["podman>=4.0.0"]
  cloud = []  # OpenAI-compatible providers (Groq, Gemini, local servers) use requests
  deepgram = ["deepgram-sdk>=3.0.0"]
  assemblyai = ["assemblyai>=0.25.0"]
  all = ["podman>=4.0.0", "deepgram-sdk>=3.0.0", "assemblyai>=0.25.0"]
  ```

- **Rationale**: Groq, Gemini, and local servers use OpenAI-compatible API (no SDK needed). OpenAI service is optional. Deepgram/AssemblyAI require proprietary SDKs

- [ ] Keep existing `requests` dependency (used by local provider)

### 13. Update Install Instructions

- [ ] Update `README.md` with installation options:
  - `pip install omega13[local]` for Podman/local server support
  - `pip install omega13` for OpenAI-compatible cloud providers (Hugging Face, Groq, Gemini)
  - `pip install omega13[deepgram]` for Deepgram streaming/diarization
  - `pip install omega13[assemblyai]` for AssemblyAI diarization/chapters
  - `pip install omega13[all]` for all providers
- [ ] Document fallback chain configuration with examples:
  - Privacy-focused: `["local_podman"]` (no cloud fallback)
  - Cost-optimized: `["local_podman", "huggingface", "groq"]`
  - Reliability-focused: `["local_podman", "huggingface", "groq", "gemini", "deepgram", "assemblyai"]`

## Phase 6: Testing

### 14. Create Mock Provider for Testing

- [ ] Create `src/omega13/providers/mock.py`
- [ ] Implement `MockTranscriptionProvider`:
  - Configurable delays and failure modes
  - Return predictable test data
  - Enable TUI testing without real services

### 15. Unit Tests

- [ ] `tests/test_provider_factory.py`:
  - Test provider instantiation
  - Test `ImportError` handling
  - Test mock provider fallback
- [ ] `tests/test_local_podman.py`:
  - Test health check logic
  - Test HTTP transcription calls (mocked)
- [ ] `tests/test_cloud_providers.py`:
  - Test API key validation
  - Test response formatting
- [ ] `tests/test_transcription_service.py`:
  - Test with mock provider
  - Test retry logic
  - Test shutdown behavior

### 16. Integration Tests

- [ ] Test full workflow with mock provider
- [ ] Test config migration from legacy to new format
- [ ] Test provider switching in running app

## Phase 7: Documentation & Cleanup

### 17. Update Documentation

- [ ] Document Provider API in `docs/providers.md`
- [ ] Add Quadlet setup guide
- [ ] Document first-run wizard flow
- [ ] Update troubleshooting section

### 18. Remove Legacy Code

- [ ] Remove hardcoded `localhost:8080` references
- [ ] Remove legacy config fields after migration
- [ ] Deprecate `docker compose.yml` (replace with Quadlet docs)

## Phase 8: Polish & Optimization

### 19. Dynamic Loading Optimization

- [ ] Move provider SDK imports inside provider classes
- [ ] Add lazy loading in factory
- [ ] Measure startup time impact

### 20. Error Handling Polish

- [ ] Ensure all provider exceptions map to `TranscriptionError`
- [ ] Add provider-specific error messages for user-friendly feedback
- [ ] Test error paths in TUI

### 21. Telemetry/Metrics (Optional)

- [ ] Add transcription timing per provider
- [ ] Log provider selection on startup
- [ ] Track fallback events

---

## Task Dependencies

```
Phase 1 → Phase 2 → Phase 3 → Phase 4
                              ↓
                         Phase 6 (testing can run in parallel with Phases 2-4)
                              ↓
Phase 5 (can run in parallel with Phase 4)
                              ↓
                        Phase 7 → Phase 8
```

**Critical Path**: 1 → 2 → 3 → 7 → 9 (local provider working end-to-end)

**Parallelizable**:

- Tasks 4, 5, 6 (cloud providers)
- Tasks 10, 11 (Quadlet/wizard)
- Tasks 12, 13 (dependencies)
- Task 15 (unit tests after Phase 2)
