# omega-13 Middleware & Daemon Refactor — Design Spec

**Date:** 2026-04-27
**Status:** Approved for implementation
**Scope:** Middleware pipeline, systemd daemon split, per-preset LM config, CLI assistant integration

---

## 1. Overview

This refactor bridges the gap between raw transcription output and intelligent, workflow-aware routing. It introduces three capabilities:

1. **Background service** — `omega13-daemon` runs as a systemd user service with no Textual dependency
2. **Middleware pipeline** — DSPy-powered SFL cleaning, register detection, and intent tagging between transcription and output
3. **Composable presets** — YAML-defined workflow scenarios that configure LM provider, assistant CLI tool, and output destination per use case

The existing TUI (`omega13`) becomes a control interface that connects to the running daemon over D-Bus rather than owning the audio stack directly.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────┐
│  omega13-daemon  (systemd user service)              │
│                                                      │
│  AudioEngine → VAD → TranscriptionService           │
│                              ↓                      │
│                       pipeline.py                   │
│               ┌──────────────────────┐              │
│               │ 1. tagger.py         │  DSPy module │
│               │    clean + tag       │  per-preset  │
│               │ 2. assistant.py      │  LM via      │
│               │    CLI call [opt]    │  dspy.context│
│               │ 3. output_router.py  │              │
│               └──────────────────────┘              │
└───────────────────────┬─────────────────────────────┘
                        │  D-Bus (extended dbus_service.py)
┌───────────────────────┴─────────────────────────────┐
│  omega13  (TUI, optional, user-launched)             │
│  Displays state, toggles auto-record,                │
│  switches active preset via D-Bus                    │
└─────────────────────────────────────────────────────┘
```

---

## 3. New Binary: `omega13-daemon`

Registered in `pyproject.toml`:

```toml
[project.scripts]
omega13        = "omega13.app:main"
omega13-daemon = "omega13.daemon:main"
```

### Startup sequence (`daemon.py`)

```python
def main():
    config        = ConfigManager.load()
    lm_registry   = LMRegistry.from_config(config)
    preset_loader = PresetLoader(config.presets_dir)
    active_preset = preset_loader.load(config.active_preset)

    audio_engine    = AudioEngine(config)
    signal_detector = SignalDetector(config)
    rec_controller  = RecordingController(audio_engine, signal_detector, config)

    transcription = TranscriptionService.from_config(config)
    pipeline      = TranscriptionPipeline(active_preset, lm_registry)
    transcription.set_post_processor(pipeline.process)

    dbus_service = Omega13DBusService(rec_controller, preset_loader, pipeline)
    dbus_service.start()

    signal.signal(signal.SIGTERM, lambda *_: shutdown(rec_controller, transcription))
    rec_controller.run_forever()
```

No Textual imports in this path. The TUI and daemon share no in-process state.

---

## 4. Systemd User Unit

Path: `~/.config/systemd/user/omega13.service`

```ini
[Unit]
Description=Omega-13 Audio Transcription Daemon
Documentation=https://github.com/b08x/omega-13
After=pipewire.service wireplumber.service
Wants=pipewire.service

[Service]
Type=simple
ExecStartPre=/usr/bin/wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 33%
ExecStart=%h/.local/bin/omega13-daemon
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal
EnvironmentFile=-%h/.config/omega13/env
Environment=OMEGA13_LOG_LEVEL=INFO

[Install]
WantedBy=default.target
```

The `ExecStartPre` wpctl command sets the microphone level before the JACK client opens — resolving the mic-level-reset-on-reboot issue. The `-` prefix on `EnvironmentFile` means the unit starts cleanly if the file is absent.

---

## 5. Middleware Pipeline

### `pipeline.py` — `TranscriptionPipeline`

```python
@dataclass
class PipelineContext:
    raw_text:     str
    cleaned_text: str = ""
    register:     str = "unknown"
    intent:       str = "unknown"
    confidence:   float = 0.0
    assistant_response: Optional[str] = None
    errors:       list[str] = field(default_factory=list)

@dataclass
class PipelineResult:
    text:     str
    context:  PipelineContext
    success:  bool
    stage_failed: Optional[str] = None

class TranscriptionPipeline:
    def __init__(self, preset: Preset, lm_registry: LMRegistry):
        self.preset      = preset
        self.lm_registry = lm_registry
        self.tagger      = TranscriptionTagger()
        self.assistant   = AssistantCaller()
        self.router      = OutputRouter()

    def process(self, raw_text: str) -> PipelineResult:
        ctx = PipelineContext(raw_text=raw_text)
        lm  = self.lm_registry.get(self.preset.lm)

        # Stage 1: clean + tag (DSPy, scoped LM)
        try:
            with dspy.context(lm=lm):
                tagged = self.tagger(raw_text=raw_text)
            ctx.cleaned_text = tagged.cleaned_text
            ctx.register     = tagged.register
            ctx.intent       = tagged.intent
            ctx.confidence   = tagged.confidence
        except Exception as e:
            ctx.errors.append(f"tagger: {e}")
            ctx.cleaned_text = raw_text   # graceful degradation

        # Stage 2: optional assistant call
        output_text = ctx.cleaned_text
        if self.preset.assistant.enabled:
            try:
                output_text = self.assistant.call(ctx.cleaned_text, self.preset)
                ctx.assistant_response = output_text
            except Exception as e:
                ctx.errors.append(f"assistant: {e}")

        # Stage 3: route output
        self.router.route(output_text, ctx, self.preset)
        return PipelineResult(text=output_text, context=ctx, success=not ctx.errors)
```

---

## 6. DSPy Tagger

### `middleware/tagger.py`

```python
from typing import Literal
import dspy

class TranscriptionSignature(dspy.Signature):
    """Analyze dictated voice transcription for register and intent."""

    raw_text: str = dspy.InputField(
        desc="Raw voice transcription with possible filler words and false starts"
    )
    cleaned_text: str = dspy.OutputField(
        desc="Text with fillers, false starts, and repetitions removed"
    )
    register: Literal["technical", "conversational", "reflective"] = dspy.OutputField(
        desc="Cognitive register of the speaker"
    )
    intent: Literal["instruction", "question", "brainstorm", "narrative"] = dspy.OutputField(
        desc="Primary communicative intent of the utterance"
    )
    confidence: float = dspy.OutputField(
        desc="Confidence score 0.0-1.0 for the register/intent classification"
    )

class TranscriptionTagger(dspy.Module):
    def __init__(self):
        super().__init__()
        self.analyze = dspy.ChainOfThought(TranscriptionSignature)

    def forward(self, raw_text: str) -> dspy.Prediction:
        return self.analyze(raw_text=raw_text)
```

`ChainOfThought` adds a reasoning step before classification, improving accuracy on mid-utterance register shifts. `Literal` output fields constrain the LLM to valid labels — no parsing or validation needed downstream.

---

## 7. LM Registry

### `lm_registry.py`

```python
PROVIDER_PREFIXES = {
    "groq":       "groq/{model}",
    "mistral":    "mistral/{model}",
    "gemini":     "gemini/{model}",
    "openrouter": "openrouter/{model}",
    "ollama":     "ollama_chat/{model}",
}

PROVIDER_ENV_KEYS = {
    "groq":       "GROQ_API_KEY",
    "mistral":    "MISTRAL_API_KEY",
    "gemini":     "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "ollama":     None,
}

class LMRegistry:
    """Lazy-init, cached dspy.LM instances keyed by (provider, model)."""

    def __init__(self):
        self._cache: dict[tuple, dspy.LM] = {}

    def get(self, lm_config: LMConfig) -> dspy.LM:
        key = (lm_config.provider, lm_config.model)
        if key not in self._cache:
            self._cache[key] = self._build(lm_config)
        return self._cache[key]

    def _build(self, cfg: LMConfig) -> dspy.LM:
        model_str = PROVIDER_PREFIXES[cfg.provider].format(model=cfg.model)
        env_key   = PROVIDER_ENV_KEYS[cfg.provider]
        kwargs    = {}
        if env_key:
            api_key = os.environ.get(env_key)
            if not api_key:
                raise RuntimeError(f"Missing env var {env_key} for provider {cfg.provider}")
            kwargs["api_key"] = api_key
        if cfg.api_base:
            kwargs["api_base"] = cfg.api_base
        return dspy.LM(model_str, **kwargs)
```

`dspy.context(lm=...)` is thread-safe — concurrent pipeline invocations with different LMs do not share global state.

---

## 8. Preset Schema

### Full schema reference

```yaml
name: string                          # unique identifier, matches filename
description: string                   # human-readable label

lm:
  provider: groq | mistral | gemini | openrouter | ollama
  model: string                       # provider-specific model name
  api_base: string                    # optional, ollama only

cleaning:
  remove_fillers: bool                # uh, um, like (mid-sentence)
  remove_false_starts: bool           # "I— I mean the"
  fix_punctuation: bool
  normalize_whitespace: bool

register:
  expected: technical | conversational | reflective | any

intent:
  tag: bool                           # always tag (metadata only)
  filter: list[str]                   # restrict to these intents [optional]

assistant:
  enabled: bool
  command: string                     # CLI tool on PATH (claude, gemini, aichat)
  args: list[string]                  # extra CLI args
  system_prompt: string               # prepended as system context
  timeout_seconds: int

output:
  primary: daily_note | inject_active_window | clipboard | new_note
  fallback: daily_note | clipboard    # used if primary fails
```

### Built-in presets

| Preset | Provider | Primary Output | Assistant |
|--------|----------|----------------|-----------|
| `dictate` | ollama/llama3.2 (local) | daily_note | no |
| `code` | groq/llama-3.3-70b-versatile | inject_active_window | yes |
| `reflect` | gemini/gemini-2.0-flash | daily_note | yes |
| `brainstorm` | openrouter/mistral-large-latest | new_note | yes |

---

## 9. D-Bus Interface Extensions

Additions to `dbus_service.py`:

```
# Methods (TUI → Daemon)
SetPreset(name: str) → bool
GetActivePreset() → str
ListPresets() → list[str]
GetStatus() → dict
SetAutoRecord(enabled: bool) → bool    # existing, unchanged

# Signals (Daemon → TUI)
PresetChanged(name: str)
PipelineStarted(preset: str)
PipelineComplete(preset: str, register: str, intent: str)
PipelineFailed(preset: str, stage: str, error: str)
AssistantCalling(preset: str, command: str)
AssistantComplete(preset: str)
```

---

## 10. File Map

### New files

```
src/omega13/
├── daemon.py
├── lm_registry.py
├── pipeline.py
├── preset_loader.py
└── middleware/
    ├── __init__.py
    ├── tagger.py
    ├── assistant.py
    └── output_router.py

~/.config/omega13/
├── env                    # API keys, not committed to git
└── presets/
    ├── dictate.yaml
    ├── code.yaml
    ├── reflect.yaml
    └── brainstorm.yaml

~/.config/systemd/user/
└── omega13.service
```

### Modified files

```
src/omega13/transcription.py    # remove flat output flags, add set_post_processor()
src/omega13/dbus_service.py     # add preset methods + pipeline signals
src/omega13/config.py           # add active_preset, presets_dir fields
src/omega13/app.py              # TUI connects to daemon via D-Bus
pyproject.toml                  # add omega13-daemon entry point, dspy + pyyaml deps
```

### Unchanged files

```
audio.py, audio_processor.py, recording_controller.py,
signal_detector.py, session.py, hotkeys.py,
notifications.py, obsidian_cli.py, injection.py, clipboard.py
```

---

## 11. Dependencies Added

```toml
dependencies = [
    # existing...
    "dspy-ai>=2.5.0",
    "pyyaml>=6.0",
]
```

---

## 12. Future Upgrade Path

- **DSPy optimization**: Once ~50 labeled transcriptions exist (daily notes are ready-made training data), run DSPy's optimizer to tune `TranscriptionSignature` prompts automatically — no code changes required
- **Streaming assistant responses**: `AssistantCaller` can be extended to stream stdout from the CLI tool to D-Bus signals, enabling live TUI display of assistant output
- **Preset hot-reload**: `SetPreset()` D-Bus method already supports this; extend to watch `~/.config/omega13/presets/` with inotify for automatic reload on file change
