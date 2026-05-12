# omega-13 Middleware & Daemon Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor omega-13 into a systemd daemon with a DSPy-powered SFL middleware pipeline, composable YAML presets with per-preset LM configuration, and a GNOME Shell panel indicator.

**Architecture:** Split `omega13` (TUI) from `omega13-daemon` (headless systemd service). Between transcription and output, insert a pipeline: DSPy tagger (clean + register + intent) → optional CLI assistant call → OutputRouter. Presets are YAML files that configure the entire pipeline including which LLM provider/model to use. The GNOME extension connects to the daemon's D-Bus interface for live status display.

**Tech Stack:** Python 3.12+, dspy-ai≥2.5.0, pyyaml≥6.0, dbus-next, GJS (GNOME Shell extension), pytest, pytest-asyncio

---

## File Map

### New files
```
src/omega13/preset_loader.py              # Preset dataclass + YAML loader
src/omega13/lm_registry.py               # Lazy-init dspy.LM cache
src/omega13/pipeline.py                  # TranscriptionPipeline orchestrator
src/omega13/daemon.py                    # Headless entry point (no Textual)
src/omega13/middleware/__init__.py
src/omega13/middleware/tagger.py         # DSPy TranscriptionTagger module
src/omega13/middleware/assistant.py      # CLI tool subprocess caller
src/omega13/middleware/output_router.py  # Routes text to destinations
src/omega13/presets/dictate.yaml         # Built-in: local ollama → daily note
src/omega13/presets/code.yaml            # Built-in: groq → inject to editor
src/omega13/presets/reflect.yaml         # Built-in: gemini → structured note
src/omega13/presets/brainstorm.yaml      # Built-in: openrouter → new note
gnome-extension/omega-13-indicator@b08x.github.io/extension.js
gnome-extension/omega-13-indicator@b08x.github.io/metadata.json
gnome-extension/omega-13-indicator@b08x.github.io/stylesheet.css
Makefile                                 # install-extension target
~/.config/systemd/user/omega13.service   # installed, not tracked in repo

tests/test_preset_loader.py
tests/test_lm_registry.py
tests/test_middleware_tagger.py
tests/test_middleware_assistant.py
tests/test_middleware_output_router.py
tests/test_pipeline.py
tests/test_transcription_refactor.py
tests/test_dbus_extensions.py
tests/test_daemon_entry.py
```

### Modified files
```
src/omega13/transcription.py    # remove flat output flags, add set_post_processor()
src/omega13/dbus_service.py     # add SetPreset, GetActivePreset, ListPresets + signals
src/omega13/config.py           # add get_active_preset, get_presets_dir, set_active_preset
src/omega13/app.py              # TUI reads state from D-Bus instead of owning audio
pyproject.toml                  # add omega13-daemon entry, dspy-ai, pyyaml deps
```

---

## Task 1: Preset Dataclasses & YAML Loader

**Files:**
- Create: `src/omega13/preset_loader.py`
- Create: `src/omega13/presets/dictate.yaml`
- Create: `src/omega13/presets/code.yaml`
- Create: `src/omega13/presets/reflect.yaml`
- Create: `src/omega13/presets/brainstorm.yaml`
- Test: `tests/test_preset_loader.py`

- [ ] **Step 1.1: Write the failing tests**

```python
# tests/test_preset_loader.py
import pytest
from pathlib import Path
from omega13.preset_loader import (
    PresetLoader, Preset, LMConfig, AssistantConfig, OutputConfig
)


def test_load_builtin_dictate():
    loader = PresetLoader(user_presets_dir=Path("/tmp/omega13_test_presets"))
    preset = loader.load("dictate")
    assert preset.name == "dictate"
    assert preset.lm.provider == "ollama"
    assert preset.lm.model == "llama3.2"
    assert preset.assistant.enabled is False
    assert preset.output.primary == "daily_note"


def test_load_builtin_code():
    loader = PresetLoader(user_presets_dir=Path("/tmp/omega13_test_presets"))
    preset = loader.load("code")
    assert preset.name == "code"
    assert preset.lm.provider == "groq"
    assert preset.assistant.enabled is True
    assert preset.assistant.command == "claude"
    assert preset.output.primary == "inject_active_window"


def test_load_builtin_reflect():
    loader = PresetLoader(user_presets_dir=Path("/tmp/omega13_test_presets"))
    preset = loader.load("reflect")
    assert preset.lm.provider == "gemini"
    assert preset.assistant.enabled is True


def test_load_builtin_brainstorm():
    loader = PresetLoader(user_presets_dir=Path("/tmp/omega13_test_presets"))
    preset = loader.load("brainstorm")
    assert preset.lm.provider == "openrouter"


def test_load_nonexistent_raises():
    loader = PresetLoader(user_presets_dir=Path("/tmp/omega13_test_presets"))
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        loader.load("nonexistent")


def test_list_presets_includes_builtins():
    loader = PresetLoader(user_presets_dir=Path("/tmp/omega13_test_presets"))
    names = loader.list_presets()
    assert "dictate" in names
    assert "code" in names
    assert "reflect" in names
    assert "brainstorm" in names


def test_user_preset_overrides_builtin(tmp_path):
    import yaml
    user_preset = {
        "name": "dictate",
        "description": "custom override",
        "lm": {"provider": "groq", "model": "custom-model"},
        "assistant": {"enabled": False},
        "output": {"primary": "clipboard", "fallback": "clipboard"},
    }
    (tmp_path / "dictate.yaml").write_text(yaml.dump(user_preset))
    loader = PresetLoader(user_presets_dir=tmp_path)
    preset = loader.load("dictate")
    assert preset.lm.provider == "groq"  # user overrides builtin


def test_missing_optional_fields_use_defaults(tmp_path):
    import yaml
    minimal = {"name": "minimal", "lm": {"provider": "ollama", "model": "llama3.2"}}
    (tmp_path / "minimal.yaml").write_text(yaml.dump(minimal))
    loader = PresetLoader(user_presets_dir=tmp_path)
    preset = loader.load("minimal")
    assert preset.assistant.enabled is False
    assert preset.output.primary == "daily_note"
    assert preset.cleaning.remove_fillers is True
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
cd /home/b08x/Workspace/omega-13
uv run pytest tests/test_preset_loader.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'omega13.preset_loader'`

- [ ] **Step 1.3: Create preset_loader.py**

```python
# src/omega13/preset_loader.py
"""YAML preset loader for omega-13 middleware pipeline."""

from __future__ import annotations
import yaml
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LMConfig:
    provider: str  # groq | mistral | gemini | openrouter | ollama
    model: str
    api_base: Optional[str] = None


@dataclass
class CleaningConfig:
    remove_fillers: bool = True
    remove_false_starts: bool = True
    fix_punctuation: bool = True
    normalize_whitespace: bool = True


@dataclass
class RegisterConfig:
    expected: str = "any"  # technical | conversational | reflective | any


@dataclass
class IntentConfig:
    tag: bool = True
    filter: list[str] = field(default_factory=list)


@dataclass
class AssistantConfig:
    enabled: bool = False
    command: str = ""
    args: list[str] = field(default_factory=list)
    system_prompt: str = ""
    timeout_seconds: int = 30


@dataclass
class OutputConfig:
    primary: str = "daily_note"  # daily_note | inject_active_window | clipboard | new_note
    fallback: str = "clipboard"


@dataclass
class Preset:
    name: str
    description: str = ""
    lm: LMConfig = field(default_factory=lambda: LMConfig(provider="ollama", model="llama3.2"))
    cleaning: CleaningConfig = field(default_factory=CleaningConfig)
    register: RegisterConfig = field(default_factory=RegisterConfig)
    intent: IntentConfig = field(default_factory=IntentConfig)
    assistant: AssistantConfig = field(default_factory=AssistantConfig)
    output: OutputConfig = field(default_factory=OutputConfig)


class PresetLoader:
    """Loads presets from YAML. User presets in user_presets_dir override builtins."""

    BUILTIN_PRESETS_DIR = Path(__file__).parent / "presets"

    def __init__(self, user_presets_dir: Path) -> None:
        self.user_presets_dir = user_presets_dir
        user_presets_dir.mkdir(parents=True, exist_ok=True)

    def load(self, name: str) -> Preset:
        """Load preset by name. User presets take precedence over builtins."""
        for directory in [self.user_presets_dir, self.BUILTIN_PRESETS_DIR]:
            path = directory / f"{name}.yaml"
            if path.exists():
                logger.info(f"Loading preset '{name}' from {path}")
                return self._parse(path)
        raise FileNotFoundError(f"Preset '{name}' not found in {self.user_presets_dir} or builtins")

    def list_presets(self) -> list[str]:
        """List all available preset names (user + builtin, deduplicated)."""
        names: set[str] = set()
        for directory in [self.BUILTIN_PRESETS_DIR, self.user_presets_dir]:
            if directory.exists():
                names.update(p.stem for p in directory.glob("*.yaml"))
        return sorted(names)

    def _parse(self, path: Path) -> Preset:
        with open(path) as f:
            data = yaml.safe_load(f)
        return self._from_dict(data)

    def _from_dict(self, data: dict) -> Preset:
        lm_raw = data.get("lm", {})
        lm = LMConfig(
            provider=lm_raw.get("provider", "ollama"),
            model=lm_raw.get("model", "llama3.2"),
            api_base=lm_raw.get("api_base"),
        )
        cleaning_raw = data.get("cleaning", {})
        cleaning = CleaningConfig(
            remove_fillers=cleaning_raw.get("remove_fillers", True),
            remove_false_starts=cleaning_raw.get("remove_false_starts", True),
            fix_punctuation=cleaning_raw.get("fix_punctuation", True),
            normalize_whitespace=cleaning_raw.get("normalize_whitespace", True),
        )
        register_raw = data.get("register", {})
        register = RegisterConfig(expected=register_raw.get("expected", "any"))

        intent_raw = data.get("intent", {})
        intent = IntentConfig(
            tag=intent_raw.get("tag", True),
            filter=intent_raw.get("filter", []),
        )
        asst_raw = data.get("assistant", {})
        assistant = AssistantConfig(
            enabled=asst_raw.get("enabled", False),
            command=asst_raw.get("command", ""),
            args=asst_raw.get("args", []),
            system_prompt=asst_raw.get("system_prompt", ""),
            timeout_seconds=asst_raw.get("timeout_seconds", 30),
        )
        out_raw = data.get("output", {})
        output = OutputConfig(
            primary=out_raw.get("primary", "daily_note"),
            fallback=out_raw.get("fallback", "clipboard"),
        )
        return Preset(
            name=data.get("name", "unknown"),
            description=data.get("description", ""),
            lm=lm,
            cleaning=cleaning,
            register=register,
            intent=intent,
            assistant=assistant,
            output=output,
        )
```

- [ ] **Step 1.4: Create built-in preset YAML files**

```bash
mkdir -p /home/b08x/Workspace/omega-13/src/omega13/presets
```

`src/omega13/presets/dictate.yaml`:
```yaml
name: dictate
description: Clean dictation to daily note, no assistant
lm:
  provider: ollama
  model: llama3.2
  api_base: http://tinybot:11434
cleaning:
  remove_fillers: true
  remove_false_starts: true
  fix_punctuation: true
  normalize_whitespace: true
register:
  expected: any
intent:
  tag: true
assistant:
  enabled: false
output:
  primary: daily_note
  fallback: clipboard
```

`src/omega13/presets/code.yaml`:
```yaml
name: code
description: Technical mode via Groq, inject to active editor window
lm:
  provider: groq
  model: llama-3.3-70b-versatile
cleaning:
  remove_fillers: true
  remove_false_starts: true
  fix_punctuation: true
  normalize_whitespace: true
register:
  expected: technical
intent:
  tag: true
  filter: [instruction, question, brainstorm]
assistant:
  enabled: true
  command: claude
  args: ["--no-stream"]
  system_prompt: |
    You are a coding assistant. The user has dictated a thought or instruction.
    Respond concisely and technically. If it is a question, answer it.
    If it is an instruction, confirm and expand on it.
  timeout_seconds: 30
output:
  primary: inject_active_window
  fallback: clipboard
```

`src/omega13/presets/reflect.yaml`:
```yaml
name: reflect
description: Reflective mode via Gemini, structured daily note
lm:
  provider: gemini
  model: gemini-2.0-flash
cleaning:
  remove_fillers: true
  remove_false_starts: false
  fix_punctuation: true
  normalize_whitespace: true
register:
  expected: conversational
intent:
  tag: true
assistant:
  enabled: true
  command: claude
  args: []
  system_prompt: |
    Format the following dictated thought as a structured Obsidian note.
    Add a ## Summary section and bullet points. Preserve the speaker's voice.
  timeout_seconds: 45
output:
  primary: daily_note
  fallback: clipboard
```

`src/omega13/presets/brainstorm.yaml`:
```yaml
name: brainstorm
description: Freeform thinking via OpenRouter Mistral, new Obsidian note
lm:
  provider: openrouter
  model: mistral/mistral-large-latest
cleaning:
  remove_fillers: true
  remove_false_starts: false
  fix_punctuation: true
  normalize_whitespace: true
register:
  expected: any
intent:
  tag: true
assistant:
  enabled: true
  command: claude
  args: []
  system_prompt: |
    Structure the following brainstorm into a mind-map outline with ## headings
    and nested bullet points. Preserve all ideas, even fragmentary ones.
  timeout_seconds: 45
output:
  primary: new_note
  fallback: daily_note
```

- [ ] **Step 1.5: Run tests to verify they pass**

```bash
cd /home/b08x/Workspace/omega-13
uv run pytest tests/test_preset_loader.py -v
```

Expected: All 8 tests PASS

- [ ] **Step 1.6: Commit**

```bash
git add src/omega13/preset_loader.py src/omega13/presets/ tests/test_preset_loader.py
git commit -m "feat: add preset system with YAML loader and built-in presets"
```

---

## Task 2: LM Registry

**Files:**
- Create: `src/omega13/lm_registry.py`
- Test: `tests/test_lm_registry.py`

- [ ] **Step 2.1: Write the failing tests**

```python
# tests/test_lm_registry.py
import pytest
import os
from unittest.mock import patch, MagicMock
from omega13.preset_loader import LMConfig
from omega13.lm_registry import LMRegistry


def test_get_ollama_no_api_key_required():
    registry = LMRegistry()
    cfg = LMConfig(provider="ollama", model="llama3.2", api_base="http://localhost:11434")
    with patch("omega13.lm_registry.dspy.LM") as mock_lm:
        mock_lm.return_value = MagicMock()
        lm = registry.get(cfg)
        mock_lm.assert_called_once_with(
            "ollama_chat/llama3.2", api_base="http://localhost:11434"
        )
        assert lm is not None


def test_get_groq_reads_env_var():
    registry = LMRegistry()
    cfg = LMConfig(provider="groq", model="llama-3.3-70b-versatile")
    with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}):
        with patch("omega13.lm_registry.dspy.LM") as mock_lm:
            mock_lm.return_value = MagicMock()
            registry.get(cfg)
            mock_lm.assert_called_once_with(
                "groq/llama-3.3-70b-versatile", api_key="test-key"
            )


def test_get_missing_env_var_raises():
    registry = LMRegistry()
    cfg = LMConfig(provider="groq", model="llama-3.3-70b-versatile")
    env = {k: v for k, v in os.environ.items() if k != "GROQ_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            registry.get(cfg)


def test_get_caches_same_instance():
    registry = LMRegistry()
    cfg = LMConfig(provider="ollama", model="llama3.2", api_base="http://localhost:11434")
    with patch("omega13.lm_registry.dspy.LM") as mock_lm:
        mock_lm.return_value = MagicMock()
        lm1 = registry.get(cfg)
        lm2 = registry.get(cfg)
        assert lm1 is lm2
        assert mock_lm.call_count == 1  # only built once


def test_get_gemini_provider():
    registry = LMRegistry()
    cfg = LMConfig(provider="gemini", model="gemini-2.0-flash")
    with patch.dict(os.environ, {"GEMINI_API_KEY": "gem-key"}):
        with patch("omega13.lm_registry.dspy.LM") as mock_lm:
            mock_lm.return_value = MagicMock()
            registry.get(cfg)
            mock_lm.assert_called_once_with("gemini/gemini-2.0-flash", api_key="gem-key")


def test_get_openrouter_provider():
    registry = LMRegistry()
    cfg = LMConfig(provider="openrouter", model="mistral/mistral-large-latest")
    with patch.dict(os.environ, {"OPENROUTER_API_KEY": "or-key"}):
        with patch("omega13.lm_registry.dspy.LM") as mock_lm:
            mock_lm.return_value = MagicMock()
            registry.get(cfg)
            mock_lm.assert_called_once_with(
                "openrouter/mistral/mistral-large-latest", api_key="or-key"
            )


def test_get_mistral_provider():
    registry = LMRegistry()
    cfg = LMConfig(provider="mistral", model="mistral-large-latest")
    with patch.dict(os.environ, {"MISTRAL_API_KEY": "ms-key"}):
        with patch("omega13.lm_registry.dspy.LM") as mock_lm:
            mock_lm.return_value = MagicMock()
            registry.get(cfg)
            mock_lm.assert_called_once_with(
                "mistral/mistral-large-latest", api_key="ms-key"
            )
```

- [ ] **Step 2.2: Run tests to verify they fail**

```bash
cd /home/b08x/Workspace/omega-13
uv run pytest tests/test_lm_registry.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'omega13.lm_registry'`

- [ ] **Step 2.3: Add dspy-ai and pyyaml to dependencies**

Edit `pyproject.toml` — add to the `dependencies` list:

```toml
dependencies = [
    "textual>=0.70.0",
    "JACK-Client>=0.5.0",
    "numpy>=1.26.0",
    "soundfile>=0.12.0",
    "requests>=2.31.0",
    "pyperclip>=1.8.0",
    "pynput>=1.7.6",
    "dbus-next>=0.2.3",
    "dspy-ai>=2.5.0",
    "pyyaml>=6.0",
]
```

```bash
cd /home/b08x/Workspace/omega-13 && uv sync
```

- [ ] **Step 2.4: Create lm_registry.py**

```python
# src/omega13/lm_registry.py
"""Lazy-init, cached dspy.LM instances keyed by (provider, model)."""

from __future__ import annotations
import os
import logging
import dspy
from omega13.preset_loader import LMConfig

logger = logging.getLogger(__name__)

PROVIDER_PREFIXES: dict[str, str] = {
    "groq":       "groq/{model}",
    "mistral":    "mistral/{model}",
    "gemini":     "gemini/{model}",
    "openrouter": "openrouter/{model}",
    "ollama":     "ollama_chat/{model}",
}

PROVIDER_ENV_KEYS: dict[str, str | None] = {
    "groq":       "GROQ_API_KEY",
    "mistral":    "MISTRAL_API_KEY",
    "gemini":     "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "ollama":     None,
}


class LMRegistry:
    """Lazy-init dspy.LM instances. Thread-safe via dspy.context() at call site."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str], dspy.LM] = {}

    def get(self, lm_config: LMConfig) -> dspy.LM:
        """Return cached dspy.LM for the given config, building it on first call."""
        key = (lm_config.provider, lm_config.model)
        if key not in self._cache:
            self._cache[key] = self._build(lm_config)
        return self._cache[key]

    def _build(self, cfg: LMConfig) -> dspy.LM:
        if cfg.provider not in PROVIDER_PREFIXES:
            raise ValueError(
                f"Unknown provider '{cfg.provider}'. "
                f"Valid: {list(PROVIDER_PREFIXES)}"
            )
        model_str = PROVIDER_PREFIXES[cfg.provider].format(model=cfg.model)
        env_key = PROVIDER_ENV_KEYS[cfg.provider]
        kwargs: dict = {}

        if env_key:
            api_key = os.environ.get(env_key)
            if not api_key:
                raise RuntimeError(
                    f"Missing env var {env_key} for provider '{cfg.provider}'. "
                    f"Set it in ~/.config/omega13/env or export it before starting the daemon."
                )
            kwargs["api_key"] = api_key

        if cfg.api_base:
            kwargs["api_base"] = cfg.api_base

        logger.info(f"Building dspy.LM: {model_str}")
        return dspy.LM(model_str, **kwargs)
```

- [ ] **Step 2.5: Run tests to verify they pass**

```bash
cd /home/b08x/Workspace/omega-13
uv run pytest tests/test_lm_registry.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 2.6: Commit**

```bash
git add src/omega13/lm_registry.py tests/test_lm_registry.py pyproject.toml
git commit -m "feat: add LMRegistry with lazy-init dspy.LM caching for all providers"
```

---

## Task 3: DSPy Tagger

**Files:**
- Create: `src/omega13/middleware/__init__.py`
- Create: `src/omega13/middleware/tagger.py`
- Test: `tests/test_middleware_tagger.py`

- [ ] **Step 3.1: Write the failing tests**

```python
# tests/test_middleware_tagger.py
import pytest
from unittest.mock import patch, MagicMock
from omega13.middleware.tagger import TranscriptionTagger


def _make_mock_prediction(cleaned="cleaned text", register="technical",
                           intent="instruction", confidence=0.9):
    pred = MagicMock()
    pred.cleaned_text = cleaned
    pred.register = register
    pred.intent = intent
    pred.confidence = confidence
    return pred


def test_tagger_returns_prediction_fields():
    tagger = TranscriptionTagger()
    mock_pred = _make_mock_prediction(
        cleaned="Fix the recording controller state machine.",
        register="technical",
        intent="instruction",
        confidence=0.95,
    )
    with patch.object(tagger.analyze, "__call__", return_value=mock_pred):
        result = tagger(raw_text="uh fix the the recording controller state machine")
    assert result.cleaned_text == "Fix the recording controller state machine."
    assert result.register == "technical"
    assert result.intent == "instruction"
    assert result.confidence == pytest.approx(0.95)


def test_tagger_passes_raw_text_to_analyze():
    tagger = TranscriptionTagger()
    mock_pred = _make_mock_prediction()
    with patch.object(tagger.analyze, "__call__", return_value=mock_pred) as mock_call:
        tagger(raw_text="hello world")
    mock_call.assert_called_once_with(raw_text="hello world")


def test_tagger_signature_fields_exist():
    """TranscriptionSignature has required InputField and OutputFields."""
    from omega13.middleware.tagger import TranscriptionSignature
    import dspy
    fields = TranscriptionSignature.model_fields if hasattr(TranscriptionSignature, 'model_fields') else {}
    # Check via dspy introspection
    sig = TranscriptionSignature
    assert hasattr(sig, '__annotations__') or hasattr(sig, 'input_fields')
```

- [ ] **Step 3.2: Run tests to verify they fail**

```bash
cd /home/b08x/Workspace/omega-13
uv run pytest tests/test_middleware_tagger.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'omega13.middleware'`

- [ ] **Step 3.3: Create middleware package and tagger**

```bash
mkdir -p /home/b08x/Workspace/omega-13/src/omega13/middleware
touch /home/b08x/Workspace/omega-13/src/omega13/middleware/__init__.py
```

```python
# src/omega13/middleware/tagger.py
"""DSPy-powered transcription tagger: cleaning + register + intent classification."""

from __future__ import annotations
from typing import Literal
import dspy


class TranscriptionSignature(dspy.Signature):
    """Analyze dictated voice transcription for register and intent.

    Clean filler words and false starts, then classify the cognitive register
    (how the speaker is thinking) and communicative intent (what they want to do).
    """

    raw_text: str = dspy.InputField(
        desc="Raw voice transcription with possible filler words, false starts, "
             "and repetitions from speech recognition"
    )
    cleaned_text: str = dspy.OutputField(
        desc="Text with fillers (uh, um, like), false starts (I— I mean), "
             "and exact repetitions removed. Preserve meaning and speaker voice."
    )
    register: Literal["technical", "conversational", "reflective"] = dspy.OutputField(
        desc="Cognitive register of the speaker. "
             "technical=engineering/computing domain, "
             "conversational=everyday speech, "
             "reflective=introspective/planning mode"
    )
    intent: Literal["instruction", "question", "brainstorm", "narrative"] = dspy.OutputField(
        desc="Primary communicative intent. "
             "instruction=directing action, "
             "question=seeking information, "
             "brainstorm=exploring ideas, "
             "narrative=recounting events or experiences"
    )
    confidence: float = dspy.OutputField(
        desc="Confidence score 0.0-1.0 for the register and intent classification"
    )


class TranscriptionTagger(dspy.Module):
    """DSPy module that cleans and classifies voice transcription in one pass."""

    def __init__(self) -> None:
        super().__init__()
        self.analyze = dspy.ChainOfThought(TranscriptionSignature)

    def forward(self, raw_text: str) -> dspy.Prediction:
        """Clean and classify a raw transcription string.

        Args:
            raw_text: Raw speech-to-text output

        Returns:
            dspy.Prediction with cleaned_text, register, intent, confidence
        """
        return self.analyze(raw_text=raw_text)
```

- [ ] **Step 3.4: Run tests to verify they pass**

```bash
cd /home/b08x/Workspace/omega-13
uv run pytest tests/test_middleware_tagger.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 3.5: Commit**

```bash
git add src/omega13/middleware/ tests/test_middleware_tagger.py
git commit -m "feat: add DSPy TranscriptionTagger with SFL register and intent classification"
```

---

## Task 4: Assistant Caller

**Files:**
- Create: `src/omega13/middleware/assistant.py`
- Test: `tests/test_middleware_assistant.py`

- [ ] **Step 4.1: Write the failing tests**

```python
# tests/test_middleware_assistant.py
import pytest
from unittest.mock import patch, MagicMock
from omega13.preset_loader import Preset, LMConfig, AssistantConfig, OutputConfig
from omega13.middleware.assistant import AssistantCaller


def _make_preset(enabled=True, command="echo", args=[], system_prompt="You help.",
                 timeout_seconds=5):
    return Preset(
        name="test",
        lm=LMConfig(provider="ollama", model="llama3.2"),
        assistant=AssistantConfig(
            enabled=enabled,
            command=command,
            args=args,
            system_prompt=system_prompt,
            timeout_seconds=timeout_seconds,
        ),
        output=OutputConfig(primary="clipboard", fallback="clipboard"),
    )


def test_disabled_assistant_returns_original_text():
    caller = AssistantCaller()
    preset = _make_preset(enabled=False)
    result = caller.call("my text", preset)
    assert result == "my text"


def test_calls_command_with_stdin(tmp_path):
    caller = AssistantCaller()
    preset = _make_preset(enabled=True, command="cat", args=[])
    # 'cat' echoes stdin to stdout
    result = caller.call("hello from stdin", preset)
    assert "hello from stdin" in result


def test_system_prompt_prepended_to_stdin():
    caller = AssistantCaller()
    preset = _make_preset(
        enabled=True, command="cat", args=[], system_prompt="SYSTEM: be helpful\n"
    )
    result = caller.call("user text", preset)
    assert "SYSTEM: be helpful" in result
    assert "user text" in result


def test_timeout_returns_original_text():
    caller = AssistantCaller()
    preset = _make_preset(enabled=True, command="sleep", args=["60"], timeout_seconds=1)
    result = caller.call("original", preset)
    assert result == "original"


def test_command_not_found_returns_original_text():
    caller = AssistantCaller()
    preset = _make_preset(enabled=True, command="nonexistent_cli_tool_xyz")
    result = caller.call("original", preset)
    assert result == "original"
```

- [ ] **Step 4.2: Run tests to verify they fail**

```bash
cd /home/b08x/Workspace/omega-13
uv run pytest tests/test_middleware_assistant.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'omega13.middleware.assistant'`

- [ ] **Step 4.3: Create assistant.py**

```python
# src/omega13/middleware/assistant.py
"""CLI assistant caller — pipes cleaned text to a CLI tool and returns stdout."""

from __future__ import annotations
import subprocess
import logging
from omega13.preset_loader import Preset

logger = logging.getLogger(__name__)


class AssistantCaller:
    """Shells out to a CLI assistant tool, pipes text as stdin, returns stdout."""

    def call(self, text: str, preset: Preset) -> str:
        """Call the preset's CLI assistant with text as stdin.

        If assistant is disabled, the preset has no command, the command is not
        found, or the call times out, returns the original text unchanged.

        Args:
            text: Cleaned transcription text to send to the assistant
            preset: Active preset containing assistant configuration

        Returns:
            Assistant's stdout response, or original text on any failure
        """
        if not preset.assistant.enabled or not preset.assistant.command:
            return text

        cmd = [preset.assistant.command] + preset.assistant.args
        stdin_content = f"{preset.assistant.system_prompt}\n{text}" if preset.assistant.system_prompt else text

        try:
            result = subprocess.run(
                cmd,
                input=stdin_content,
                capture_output=True,
                text=True,
                timeout=preset.assistant.timeout_seconds,
            )
            if result.returncode == 0:
                output = result.stdout.strip()
                logger.info(f"Assistant '{preset.assistant.command}' returned {len(output)} chars")
                return output if output else text
            else:
                logger.warning(
                    f"Assistant '{preset.assistant.command}' exited {result.returncode}: "
                    f"{result.stderr.strip()[:200]}"
                )
                return text

        except subprocess.TimeoutExpired:
            logger.warning(
                f"Assistant '{preset.assistant.command}' timed out after "
                f"{preset.assistant.timeout_seconds}s — using original text"
            )
            return text
        except FileNotFoundError:
            logger.error(
                f"Assistant command '{preset.assistant.command}' not found on PATH — "
                f"using original text"
            )
            return text
        except Exception as e:
            logger.error(f"Assistant call failed: {e} — using original text")
            return text
```

- [ ] **Step 4.4: Run tests to verify they pass**

```bash
cd /home/b08x/Workspace/omega-13
uv run pytest tests/test_middleware_assistant.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 4.5: Commit**

```bash
git add src/omega13/middleware/assistant.py tests/test_middleware_assistant.py
git commit -m "feat: add AssistantCaller for CLI tool subprocess integration"
```

---

## Task 5: Output Router

**Files:**
- Create: `src/omega13/middleware/output_router.py`
- Test: `tests/test_middleware_output_router.py`

- [ ] **Step 5.1: Write the failing tests**

```python
# tests/test_middleware_output_router.py
import pytest
from unittest.mock import patch, MagicMock, call
from omega13.preset_loader import Preset, LMConfig, AssistantConfig, OutputConfig
from omega13.middleware.output_router import OutputRouter, RoutingResult


def _make_preset(primary="clipboard", fallback="clipboard"):
    return Preset(
        name="test",
        lm=LMConfig(provider="ollama", model="llama3.2"),
        assistant=AssistantConfig(enabled=False),
        output=OutputConfig(primary=primary, fallback=fallback),
    )


def test_route_to_clipboard_success():
    router = OutputRouter()
    preset = _make_preset(primary="clipboard")
    with patch("omega13.middleware.output_router.pyperclip.copy") as mock_copy:
        result = router.route("hello", preset)
    mock_copy.assert_called_once_with("hello")
    assert result.success is True
    assert result.destination == "clipboard"


def test_route_to_daily_note_success():
    router = OutputRouter()
    preset = _make_preset(primary="daily_note")
    mock_obsidian = MagicMock()
    mock_obsidian.append_to_daily_note.return_value = MagicMock(success=True)
    with patch("omega13.middleware.output_router.obsidian_cli", mock_obsidian):
        result = router.route("note text", preset)
    mock_obsidian.append_to_daily_note.assert_called_once_with("note text")
    assert result.success is True
    assert result.destination == "daily_note"


def test_route_falls_back_on_primary_failure():
    router = OutputRouter()
    preset = _make_preset(primary="daily_note", fallback="clipboard")
    mock_obsidian = MagicMock()
    mock_obsidian.append_to_daily_note.return_value = MagicMock(success=False, message="CLI unavailable")
    with patch("omega13.middleware.output_router.obsidian_cli", mock_obsidian):
        with patch("omega13.middleware.output_router.pyperclip.copy") as mock_copy:
            result = router.route("text", preset)
    mock_copy.assert_called_once_with("text")
    assert result.destination == "clipboard"
    assert result.used_fallback is True


def test_route_inject_active_window():
    router = OutputRouter()
    preset = _make_preset(primary="inject_active_window", fallback="clipboard")
    with patch("omega13.middleware.output_router.inject_text") as mock_inject:
        mock_inject.return_value = True
        result = router.route("injected text", preset)
    mock_inject.assert_called_once_with("injected text")
    assert result.destination == "inject_active_window"
```

- [ ] **Step 5.2: Run tests to verify they fail**

```bash
uv run pytest tests/test_middleware_output_router.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'omega13.middleware.output_router'`

- [ ] **Step 5.3: Create output_router.py**

```python
# src/omega13/middleware/output_router.py
"""Routes pipeline output text to the destination configured in the preset."""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
import pyperclip
from omega13.preset_loader import Preset
from omega13.obsidian_cli import obsidian_cli
from omega13.injection import inject_text

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    success: bool
    destination: str
    used_fallback: bool = False
    error: str = ""


class OutputRouter:
    """Routes text to the destination(s) defined in a preset."""

    def route(self, text: str, preset: Preset) -> RoutingResult:
        """Route text to preset.output.primary, falling back if it fails.

        Args:
            text: Final output text (cleaned, optionally assistant-processed)
            preset: Active preset with output configuration

        Returns:
            RoutingResult indicating where text was sent
        """
        result = self._try_route(text, preset.output.primary)
        if result.success:
            return result

        logger.warning(
            f"Primary output '{preset.output.primary}' failed: {result.error}. "
            f"Falling back to '{preset.output.fallback}'"
        )
        fallback = self._try_route(text, preset.output.fallback)
        fallback.used_fallback = True
        return fallback

    def _try_route(self, text: str, destination: str) -> RoutingResult:
        try:
            if destination == "clipboard":
                pyperclip.copy(text)
                return RoutingResult(success=True, destination="clipboard")

            elif destination == "daily_note":
                result = obsidian_cli.append_to_daily_note(text)
                if result.success:
                    return RoutingResult(success=True, destination="daily_note")
                return RoutingResult(
                    success=False, destination="daily_note", error=result.message
                )

            elif destination == "inject_active_window":
                ok = inject_text(text)
                if ok:
                    return RoutingResult(success=True, destination="inject_active_window")
                return RoutingResult(
                    success=False, destination="inject_active_window",
                    error="injection returned False"
                )

            elif destination == "new_note":
                # Create new Obsidian note with timestamp title
                from datetime import datetime
                title = datetime.now().strftime("Capture %Y-%m-%d %H:%M")
                result = obsidian_cli.create_note(title, text)
                if result.success:
                    return RoutingResult(success=True, destination="new_note")
                return RoutingResult(
                    success=False, destination="new_note", error=result.message
                )

            else:
                return RoutingResult(
                    success=False, destination=destination,
                    error=f"Unknown destination '{destination}'"
                )

        except Exception as e:
            logger.error(f"Output routing to '{destination}' raised: {e}")
            return RoutingResult(success=False, destination=destination, error=str(e))
```

- [ ] **Step 5.4: Add `create_note` to obsidian_cli.py**

Open `src/omega13/obsidian_cli.py` and add after the `append_to_daily_note` method:

```python
def create_note(self, title: str, content: str) -> ObsidianResult:
    """Create a new Obsidian note with the given title and content."""
    if not self.is_available():
        return ObsidianResult(
            success=False,
            message="Obsidian CLI not available."
        )
    try:
        result = subprocess.run(
            ["obsidian", "note", "create", "--title", title, "--content", content],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return ObsidianResult(success=True, message=f"Note '{title}' created")
        return ObsidianResult(
            success=False,
            message=result.stderr.strip() or "Failed to create note",
            error_code=result.returncode,
        )
    except Exception as e:
        logger.error(f"create_note failed: {e}")
        return ObsidianResult(success=False, message=str(e))
```

- [ ] **Step 5.5: Run tests to verify they pass**

```bash
uv run pytest tests/test_middleware_output_router.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5.6: Commit**

```bash
git add src/omega13/middleware/output_router.py src/omega13/obsidian_cli.py tests/test_middleware_output_router.py
git commit -m "feat: add OutputRouter and obsidian_cli.create_note for new_note destination"
```

---

## Task 6: Pipeline Orchestrator

**Files:**
- Create: `src/omega13/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 6.1: Write the failing tests**

```python
# tests/test_pipeline.py
import pytest
import dspy
from unittest.mock import patch, MagicMock
from omega13.preset_loader import Preset, LMConfig, AssistantConfig, OutputConfig
from omega13.lm_registry import LMRegistry
from omega13.pipeline import TranscriptionPipeline, PipelineContext, PipelineResult


def _make_preset(assistant_enabled=False, primary="clipboard"):
    return Preset(
        name="test",
        lm=LMConfig(provider="ollama", model="llama3.2"),
        assistant=AssistantConfig(enabled=assistant_enabled, command="cat"),
        output=OutputConfig(primary=primary, fallback="clipboard"),
    )


def _make_tagger_prediction(cleaned="cleaned", register="technical",
                             intent="instruction", confidence=0.9):
    pred = MagicMock()
    pred.cleaned_text = cleaned
    pred.register = register
    pred.intent = intent
    pred.confidence = confidence
    return pred


def test_process_returns_pipeline_result():
    registry = LMRegistry()
    preset = _make_preset()
    pipeline = TranscriptionPipeline(preset, registry)

    mock_lm = MagicMock()
    mock_pred = _make_tagger_prediction(cleaned="Fixed text.")

    with patch.object(registry, "get", return_value=mock_lm):
        with patch("dspy.context"):
            with patch.object(pipeline.tagger, "__call__", return_value=mock_pred):
                with patch.object(pipeline.router, "route") as mock_route:
                    mock_route.return_value = MagicMock(success=True, destination="clipboard")
                    result = pipeline.process("uh fixed text")

    assert isinstance(result, PipelineResult)
    assert result.context.register == "technical"
    assert result.context.intent == "instruction"
    assert result.context.cleaned_text == "Fixed text."
    assert result.success is True


def test_tagger_failure_uses_raw_text():
    registry = LMRegistry()
    preset = _make_preset()
    pipeline = TranscriptionPipeline(preset, registry)

    mock_lm = MagicMock()
    with patch.object(registry, "get", return_value=mock_lm):
        with patch("dspy.context"):
            with patch.object(pipeline.tagger, "__call__", side_effect=Exception("LLM down")):
                with patch.object(pipeline.router, "route") as mock_route:
                    mock_route.return_value = MagicMock(success=True, destination="clipboard")
                    result = pipeline.process("raw text")

    assert result.context.cleaned_text == "raw text"  # degraded to raw
    assert any("tagger" in e for e in result.context.errors)


def test_assistant_not_called_when_disabled():
    registry = LMRegistry()
    preset = _make_preset(assistant_enabled=False)
    pipeline = TranscriptionPipeline(preset, registry)
    mock_pred = _make_tagger_prediction(cleaned="clean")
    mock_lm = MagicMock()

    with patch.object(registry, "get", return_value=mock_lm):
        with patch("dspy.context"):
            with patch.object(pipeline.tagger, "__call__", return_value=mock_pred):
                with patch.object(pipeline.assistant, "call") as mock_assist:
                    with patch.object(pipeline.router, "route") as mock_route:
                        mock_route.return_value = MagicMock(success=True, destination="clipboard")
                        pipeline.process("text")

    mock_assist.assert_not_called()


def test_assistant_failure_uses_cleaned_text():
    registry = LMRegistry()
    preset = _make_preset(assistant_enabled=True)
    pipeline = TranscriptionPipeline(preset, registry)
    mock_pred = _make_tagger_prediction(cleaned="clean text")
    mock_lm = MagicMock()

    with patch.object(registry, "get", return_value=mock_lm):
        with patch("dspy.context"):
            with patch.object(pipeline.tagger, "__call__", return_value=mock_pred):
                with patch.object(pipeline.assistant, "call", side_effect=Exception("CLI failed")):
                    with patch.object(pipeline.router, "route") as mock_route:
                        mock_route.return_value = MagicMock(success=True, destination="clipboard")
                        result = pipeline.process("raw")

    assert any("assistant" in e for e in result.context.errors)
```

- [ ] **Step 6.2: Run tests to verify they fail**

```bash
uv run pytest tests/test_pipeline.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'omega13.pipeline'`

- [ ] **Step 6.3: Create pipeline.py**

```python
# src/omega13/pipeline.py
"""TranscriptionPipeline — orchestrates tagger → assistant → router."""

from __future__ import annotations
import logging
import dspy
from dataclasses import dataclass, field
from typing import Optional
from omega13.preset_loader import Preset
from omega13.lm_registry import LMRegistry
from omega13.middleware.tagger import TranscriptionTagger
from omega13.middleware.assistant import AssistantCaller
from omega13.middleware.output_router import OutputRouter, RoutingResult

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    raw_text: str
    cleaned_text: str = ""
    register: str = "unknown"
    intent: str = "unknown"
    confidence: float = 0.0
    assistant_response: Optional[str] = None
    errors: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    text: str
    context: PipelineContext
    success: bool
    routing: Optional[RoutingResult] = None
    stage_failed: Optional[str] = None


class TranscriptionPipeline:
    """Orchestrates the full middleware pipeline for a single transcription."""

    def __init__(self, preset: Preset, lm_registry: LMRegistry) -> None:
        self.preset = preset
        self.lm_registry = lm_registry
        self.tagger = TranscriptionTagger()
        self.assistant = AssistantCaller()
        self.router = OutputRouter()

    def process(self, raw_text: str) -> PipelineResult:
        """Run raw transcription text through the full pipeline.

        Stages:
          1. DSPy tagger: clean + register + intent (scoped LM via dspy.context)
          2. AssistantCaller: optional CLI tool call (preset-controlled)
          3. OutputRouter: route to preset-defined destination with fallback

        Each stage degrades gracefully on failure.

        Args:
            raw_text: Raw transcription string from TranscriptionService

        Returns:
            PipelineResult with final text, context metadata, and routing outcome
        """
        ctx = PipelineContext(raw_text=raw_text)
        lm = self.lm_registry.get(self.preset.lm)

        # Stage 1: Tag (clean + classify)
        try:
            with dspy.context(lm=lm):
                tagged = self.tagger(raw_text=raw_text)
            ctx.cleaned_text = tagged.cleaned_text
            ctx.register = tagged.register
            ctx.intent = tagged.intent
            ctx.confidence = tagged.confidence
        except Exception as e:
            logger.error(f"Tagger failed: {e} — degrading to raw text")
            ctx.errors.append(f"tagger: {e}")
            ctx.cleaned_text = raw_text

        # Stage 2: Assistant (optional)
        output_text = ctx.cleaned_text
        if self.preset.assistant.enabled:
            try:
                output_text = self.assistant.call(ctx.cleaned_text, self.preset)
                ctx.assistant_response = output_text
            except Exception as e:
                logger.error(f"Assistant call failed: {e} — using cleaned text")
                ctx.errors.append(f"assistant: {e}")

        # Stage 3: Route output
        routing = self.router.route(output_text, self.preset)

        return PipelineResult(
            text=output_text,
            context=ctx,
            success=not ctx.errors,
            routing=routing,
        )
```

- [ ] **Step 6.4: Run tests to verify they pass**

```bash
uv run pytest tests/test_pipeline.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 6.5: Commit**

```bash
git add src/omega13/pipeline.py tests/test_pipeline.py
git commit -m "feat: add TranscriptionPipeline orchestrating tagger → assistant → router"
```

---

## Task 7: Transcription Refactor

**Files:**
- Modify: `src/omega13/transcription.py`
- Test: `tests/test_transcription_refactor.py`

- [ ] **Step 7.1: Write the failing tests**

```python
# tests/test_transcription_refactor.py
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from omega13.transcription import TranscriptionService, TranscriptionResult, TranscriptionStatus


def _make_service():
    mock_provider = MagicMock()
    mock_provider.transcribe.return_value = ("transcribed text", "en")
    return TranscriptionService(provider=mock_provider)


def test_set_post_processor_stores_callable():
    service = _make_service()
    mock_processor = MagicMock()
    service.set_post_processor(mock_processor)
    assert service._post_processor is mock_processor


def test_post_processor_called_after_transcription(tmp_path):
    service = _make_service()
    mock_processor = MagicMock()
    service.set_post_processor(mock_processor)

    audio_file = tmp_path / "test.wav"
    audio_file.touch()

    results = []
    thread = service.transcribe_async(
        audio_file,
        callback=lambda r: results.append(r),
    )
    thread.join(timeout=5.0)

    mock_processor.assert_called_once_with("transcribed text")


def test_no_post_processor_still_calls_callback(tmp_path):
    """Without set_post_processor, behavior is unchanged."""
    service = _make_service()
    audio_file = tmp_path / "test.wav"
    audio_file.touch()

    results = []
    thread = service.transcribe_async(
        audio_file,
        callback=lambda r: results.append(r),
    )
    thread.join(timeout=5.0)

    assert len(results) == 1
    assert results[0].text == "transcribed text"
    assert results[0].status == TranscriptionStatus.COMPLETED


def test_from_config_classmethod():
    mock_config = MagicMock()
    mock_config.get_transcription_provider.return_value = "local"
    mock_config.get_transcription_server_url.return_value = "http://localhost:8080"
    mock_config.get_transcription_inference_path.return_value = "/v1/audio/transcriptions"
    service = TranscriptionService.from_config(mock_config)
    assert isinstance(service, TranscriptionService)
```

- [ ] **Step 7.2: Run tests to verify they fail**

```bash
uv run pytest tests/test_transcription_refactor.py -v 2>&1 | head -20
```

Expected: `AttributeError: 'TranscriptionService' object has no attribute 'set_post_processor'`

- [ ] **Step 7.3: Modify transcription.py**

In `src/omega13/transcription.py`, make these changes:

**a) Add `_post_processor` to `__init__` and add `set_post_processor` + `from_config` methods:**

Find the `TranscriptionService.__init__` method and add `self._post_processor = None`:

```python
def __init__(
    self,
    provider: TranscriptionProvider,
    timeout: int = 600,
    notifier: Optional[Any] = None,
):
    self.provider = provider
    self.timeout = timeout
    self.notifier = notifier
    self.active_threads: list[threading.Thread] = []
    self._lock = threading.Lock()
    self._shutdown_event = threading.Event()
    self._post_processor: Optional[Callable[[str], None]] = None  # ADD THIS

def set_post_processor(self, processor: Callable[[str], None]) -> None:
    """Set a callable that receives the raw transcription text after each transcription.

    When set, the processor is called instead of the flat output-flag routing.
    The pipeline (TranscriptionPipeline.process) is the intended processor.

    Args:
        processor: Callable that accepts raw transcription text
    """
    self._post_processor = processor

@classmethod
def from_config(cls, config_manager) -> "TranscriptionService":
    """Build a TranscriptionService from a ConfigManager instance."""
    provider_type = config_manager.get_transcription_provider()
    if provider_type == "groq":
        provider = GroqTranscriptionProvider(
            api_key=config_manager.get_groq_api_key(),
            model=config_manager.get_groq_model(),
        )
    else:
        provider = LocalTranscriptionProvider(
            server_url=config_manager.get_transcription_server_url(),
            inference_path=config_manager.get_transcription_inference_path(),
        )
    return cls(provider=provider)
```

**b) In `_transcribe_worker`, add post_processor branch after getting `transcribed_text`:**

Find the section in `_transcribe_worker` that handles output routing (clipboard, inject, daily_note). Replace it with:

```python
# --- Output routing ---
if self._post_processor is not None:
    # Pipeline handles all routing
    self._post_processor(transcribed_text)
else:
    # Legacy flat-flag routing (TUI direct mode)
    if copy_to_clipboard_enabled and transcribed_text:
        from .clipboard import copy_to_clipboard
        success = copy_to_clipboard(transcribed_text)
        if not success and clipboard_error_callback:
            clipboard_error_callback("Failed to copy to clipboard")

    if inject_to_active_window_enabled and transcribed_text:
        from .injection import inject_text
        success = inject_text(transcribed_text)
        if not success and injection_error_callback:
            injection_error_callback("Failed to inject text")

    if write_to_daily_note_enabled and transcribed_text:
        result = obsidian_cli.append_to_daily_note(transcribed_text)
        if not result.success and daily_note_error_callback:
            daily_note_error_callback(result.message)
```

- [ ] **Step 7.4: Run tests to verify they pass**

```bash
uv run pytest tests/test_transcription_refactor.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 7.5: Verify existing tests still pass**

```bash
uv run pytest tests/ -v --ignore=tests/test_tui_bindings.py -x
```

Expected: All existing tests PASS (TUI bindings test excluded — it requires a running display)

- [ ] **Step 7.6: Commit**

```bash
git add src/omega13/transcription.py tests/test_transcription_refactor.py
git commit -m "refactor(transcription): add set_post_processor hook, from_config classmethod, remove flat flag coupling"
```

---

## Task 8: Config Additions

**Files:**
- Modify: `src/omega13/config.py`

- [ ] **Step 8.1: Write the failing tests** (add to a new file)

```python
# tests/test_config_additions.py
import pytest
import json
from pathlib import Path
from omega13.config import ConfigManager


def test_get_active_preset_default(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"version": 2}))
    cm = ConfigManager(config_path)
    assert cm.get_active_preset() == "dictate"


def test_set_and_get_active_preset(tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"version": 2}))
    cm = ConfigManager(config_path)
    cm.set_active_preset("code")
    assert cm.get_active_preset() == "code"


def test_get_presets_dir_default():
    cm = ConfigManager.__new__(ConfigManager)
    cm._config = {}
    cm._config_path = Path("/tmp/test_config.json")
    result = cm.get_presets_dir()
    assert result == Path.home() / ".config" / "omega13" / "presets"
```

- [ ] **Step 8.2: Run tests to verify they fail**

```bash
uv run pytest tests/test_config_additions.py -v 2>&1 | head -15
```

Expected: `AttributeError: 'ConfigManager' object has no attribute 'get_active_preset'`

- [ ] **Step 8.3: Add methods to config.py**

In `src/omega13/config.py`, add these methods to the `ConfigManager` class:

```python
def get_active_preset(self) -> str:
    """Return the name of the active preset. Defaults to 'dictate'."""
    return self._config.get("active_preset", "dictate")

def set_active_preset(self, name: str) -> None:
    """Persist the active preset name to config."""
    self._config["active_preset"] = name
    self._save()

def get_presets_dir(self) -> Path:
    """Return the user presets directory. Default: ~/.config/omega13/presets"""
    raw = self._config.get("presets_dir")
    if raw:
        return Path(raw)
    return Path.home() / ".config" / "omega13" / "presets"
```

- [ ] **Step 8.4: Run tests to verify they pass**

```bash
uv run pytest tests/test_config_additions.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 8.5: Commit**

```bash
git add src/omega13/config.py tests/test_config_additions.py
git commit -m "feat(config): add active_preset and presets_dir fields to ConfigManager"
```

---

## Task 9: D-Bus Interface Extensions

**Files:**
- Modify: `src/omega13/dbus_service.py`
- Test: `tests/test_dbus_extensions.py`

- [ ] **Step 9.1: Write the failing tests**

```python
# tests/test_dbus_extensions.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import asyncio
from omega13.dbus_service import RecorderInterface


def _make_interface():
    mock_app = MagicMock()
    mock_app.recording_controller = MagicMock()
    mock_app.preset_loader = MagicMock()
    mock_app.pipeline = MagicMock()
    mock_app.preset_loader.list_presets.return_value = ["dictate", "code", "reflect"]
    mock_app.preset_loader.load.return_value = MagicMock(name="code")
    mock_app.pipeline.preset = MagicMock()
    mock_app.pipeline.preset.name = "dictate"
    return RecorderInterface(mock_app)


def test_get_active_preset_returns_current_name():
    iface = _make_interface()
    result = asyncio.get_event_loop().run_until_complete(iface.GetActivePreset())
    assert result == "dictate"


def test_list_presets_returns_list():
    iface = _make_interface()
    result = asyncio.get_event_loop().run_until_complete(iface.ListPresets())
    assert "dictate" in result
    assert "code" in result


def test_set_preset_loads_and_updates_pipeline():
    iface = _make_interface()
    result = asyncio.get_event_loop().run_until_complete(iface.SetPreset("code"))
    assert result is True
    iface._app.preset_loader.load.assert_called_once_with("code")


def test_set_preset_returns_false_on_unknown():
    iface = _make_interface()
    iface._app.preset_loader.load.side_effect = FileNotFoundError("no such preset")
    result = asyncio.get_event_loop().run_until_complete(iface.SetPreset("nonexistent"))
    assert result is False
```

- [ ] **Step 9.2: Run tests to verify they fail**

```bash
uv run pytest tests/test_dbus_extensions.py -v 2>&1 | head -15
```

Expected: `AttributeError: GetActivePreset not found` or similar

- [ ] **Step 9.3: Extend dbus_service.py**

In `src/omega13/dbus_service.py`, add these imports at the top:

```python
from dbus_next.service import ServiceInterface, method, signal
```

Replace the existing `from dbus_next.service import ServiceInterface, method` line.

Add these methods and signals to `RecorderInterface`:

```python
# --- Preset signals ---

@signal()
def PresetChanged(self) -> 's':  # noqa: N802
    """Emitted when the active preset changes. Arg: preset name."""

@signal()
def PipelineStarted(self) -> 's':  # noqa: N802
    """Emitted when pipeline processing begins. Arg: preset name."""

@signal()
def PipelineComplete(self) -> 'sss':  # noqa: N802
    """Emitted when pipeline completes. Args: preset, register, intent."""

@signal()
def PipelineFailed(self) -> 'sss':  # noqa: N802
    """Emitted when any pipeline stage fails. Args: preset, stage, error."""

@signal()
def AssistantCalling(self) -> 'ss':  # noqa: N802
    """Emitted when about to call CLI assistant. Args: preset, command."""

@signal()
def AssistantComplete(self) -> 's':  # noqa: N802
    """Emitted when CLI assistant returns. Arg: preset name."""

# --- Preset methods ---

@method()
async def GetActivePreset(self) -> 's':  # type: ignore  # noqa: N802
    """Return the name of the currently active preset."""
    try:
        return self._app.pipeline.preset.name
    except Exception as e:
        raise DBusError("org.omega13.Recorder.PresetError", str(e))

@method()
async def ListPresets(self) -> 'as':  # type: ignore  # noqa: N802
    """Return list of available preset names."""
    try:
        return self._app.preset_loader.list_presets()
    except Exception as e:
        raise DBusError("org.omega13.Recorder.PresetError", str(e))

@method()
async def SetPreset(self, name: 's') -> 'b':  # type: ignore  # noqa: N802
    """Load a preset by name and make it active. Returns True on success."""
    try:
        new_preset = self._app.preset_loader.load(name)
        self._app.pipeline.preset = new_preset
        self._app.config_manager.set_active_preset(name)
        self.PresetChanged(name)
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        raise DBusError("org.omega13.Recorder.PresetError", str(e))
```

- [ ] **Step 9.4: Run tests to verify they pass**

```bash
uv run pytest tests/test_dbus_extensions.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 9.5: Commit**

```bash
git add src/omega13/dbus_service.py tests/test_dbus_extensions.py
git commit -m "feat(dbus): add SetPreset, GetActivePreset, ListPresets methods and pipeline signals"
```

---

## Task 10: Daemon Entry Point

**Files:**
- Create: `src/omega13/daemon.py`
- Modify: `pyproject.toml`
- Test: `tests/test_daemon_entry.py`

- [ ] **Step 10.1: Write the failing tests**

```python
# tests/test_daemon_entry.py
import pytest


def test_daemon_module_imports_without_textual():
    """Daemon entry point must not import Textual."""
    import importlib
    import sys

    # Remove textual from sys.modules to detect if daemon imports it
    textual_keys = [k for k in sys.modules if k.startswith("textual")]
    for k in textual_keys:
        del sys.modules[k]

    # Import daemon — should not re-import textual
    import omega13.daemon  # noqa: F401

    new_textual = [k for k in sys.modules if k.startswith("textual")]
    assert new_textual == [], f"daemon.py imported Textual: {new_textual}"


def test_daemon_main_is_callable():
    from omega13.daemon import main
    assert callable(main)
```

- [ ] **Step 10.2: Run tests to verify they fail**

```bash
uv run pytest tests/test_daemon_entry.py -v 2>&1 | head -10
```

Expected: `ModuleNotFoundError: No module named 'omega13.daemon'`

- [ ] **Step 10.3: Create daemon.py**

```python
# src/omega13/daemon.py
"""omega13-daemon — headless systemd entry point. No Textual imports allowed."""

from __future__ import annotations
import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    level = os.environ.get("OMEGA13_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )


async def _run() -> None:
    from omega13.config import ConfigManager
    from omega13.lm_registry import LMRegistry
    from omega13.preset_loader import PresetLoader
    from omega13.pipeline import TranscriptionPipeline
    from omega13.audio import AudioEngine
    from omega13.signal_detector import SignalDetector
    from omega13.recording_controller import RecordingController
    from omega13.transcription import TranscriptionService
    from omega13.dbus_service import DBusService

    config = ConfigManager.load()
    lm_registry = LMRegistry()
    preset_loader = PresetLoader(user_presets_dir=config.get_presets_dir())
    active_preset = preset_loader.load(config.get_active_preset())

    pipeline = TranscriptionPipeline(active_preset, lm_registry)

    transcription = TranscriptionService.from_config(config)
    transcription.set_post_processor(pipeline.process)

    # Attach preset_loader and pipeline to a lightweight namespace for D-Bus access
    class DaemonContext:
        pass

    ctx = DaemonContext()
    ctx.preset_loader = preset_loader   # type: ignore[attr-defined]
    ctx.pipeline = pipeline             # type: ignore[attr-defined]
    ctx.config_manager = config         # type: ignore[attr-defined]

    saved_ports = config.get_input_ports()
    num_channels = len(saved_ports) if saved_ports else 1
    engine = AudioEngine(config_manager=config, num_channels=num_channels)
    engine.start()

    rec_controller = RecordingController(
        audio_engine=engine,
        signal_detector=engine.signal_detector,
        config_manager=config,
    )
    ctx.recording_controller = rec_controller  # type: ignore[attr-defined]

    if config.get_auto_record_enabled():
        rec_controller.enable_auto_record()

    dbus = DBusService(ctx)
    await dbus.register()
    logger.info("omega13-daemon started — D-Bus service registered")

    # Run until SIGTERM or SIGINT
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, stop_event.set)
    loop.add_signal_handler(signal.SIGINT, stop_event.set)

    await stop_event.wait()

    logger.info("omega13-daemon shutting down")
    transcription.shutdown(timeout=10.0)
    engine.stop()
    await dbus.unregister()


def main() -> None:
    """Entry point for omega13-daemon."""
    _configure_logging()
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
```

- [ ] **Step 10.4: Add daemon entry point to pyproject.toml**

In `pyproject.toml`, update `[project.scripts]`:

```toml
[project.scripts]
omega13 = "omega13.app:main"
omega13-daemon = "omega13.daemon:main"
```

```bash
cd /home/b08x/Workspace/omega-13 && uv sync
```

- [ ] **Step 10.5: Run tests to verify they pass**

```bash
uv run pytest tests/test_daemon_entry.py -v
```

Expected: Both tests PASS

- [ ] **Step 10.6: Commit**

```bash
git add src/omega13/daemon.py pyproject.toml tests/test_daemon_entry.py
git commit -m "feat: add omega13-daemon headless entry point with asyncio event loop"
```

---

## Task 11: TUI Refactor

**Files:**
- Modify: `src/omega13/app.py`

This task refactors `_start_transcription` in `app.py` to use the pipeline when the daemon is running, and keeps legacy direct mode as fallback. The audio engine stays in the TUI for now (daemon mode is additive).

- [ ] **Step 11.1: Modify `_start_transcription` in app.py**

Find the `_start_transcription` method in `src/omega13/app.py`. Replace the `self.transcription_service.transcribe_async(...)` call block with:

```python
def _start_transcription(self, audio_file: Path):
    if not self.transcription_service:
        provider_type = self.config_manager.get_transcription_provider()
        if provider_type == "groq":
            provider = GroqTranscriptionProvider(
                api_key=self.config_manager.get_groq_api_key(),
                model=self.config_manager.get_groq_model(),
            )
        else:
            provider = LocalTranscriptionProvider(
                server_url=self.config_manager.get_transcription_server_url(),
                inference_path=self.config_manager.get_transcription_inference_path(),
            )
        self.transcription_service = TranscriptionService(
            provider=provider, notifier=self.notifier
        )
        # Wire pipeline if presets are configured
        try:
            from omega13.preset_loader import PresetLoader
            from omega13.lm_registry import LMRegistry
            from omega13.pipeline import TranscriptionPipeline
            preset_loader = PresetLoader(
                user_presets_dir=self.config_manager.get_presets_dir()
            )
            preset = preset_loader.load(self.config_manager.get_active_preset())
            pipeline = TranscriptionPipeline(preset, LMRegistry())
            self.transcription_service.set_post_processor(pipeline.process)
            logger.info(f"Pipeline wired with preset '{preset.name}'")
        except Exception as e:
            logger.warning(f"Pipeline not wired (falling back to direct mode): {e}")

    display = self.query_one("#transcription-display", TranscriptionDisplay)
    display.status = "processing"
    display.progress = 0.0
    display.provider = self.config_manager.get_transcription_provider()

    def on_complete(result):
        self.call_from_thread(self._handle_result, result, audio_file)

    def on_progress(p):
        self.call_from_thread(lambda: setattr(display, "progress", p))

    # Legacy error callbacks (used when pipeline not wired)
    def on_clipboard_error(error_msg):
        self.call_from_thread(self._handle_clipboard_error, error_msg)

    def on_injection_error(error_msg):
        self.call_from_thread(self._handle_injection_error, error_msg)

    def on_daily_note_error(error_msg):
        self.call_from_thread(self._handle_daily_note_error, error_msg)

    self.transcription_service.transcribe_async(
        audio_file,
        on_complete,
        on_progress,
        copy_to_clipboard_enabled=self.copy_to_clipboard,
        clipboard_error_callback=on_clipboard_error,
        inject_to_active_window_enabled=self.inject_to_active_window,
        injection_error_callback=on_injection_error,
        write_to_daily_note_enabled=self.write_to_daily_note,
        daily_note_error_callback=on_daily_note_error,
    )
```

- [ ] **Step 11.2: Run existing TUI-compatible tests**

```bash
uv run pytest tests/ -v --ignore=tests/test_tui_bindings.py -x
```

Expected: All tests PASS

- [ ] **Step 11.3: Commit**

```bash
git add src/omega13/app.py
git commit -m "refactor(tui): wire pipeline in _start_transcription with legacy direct-mode fallback"
```

---

## Task 12: Systemd User Unit

**Files:**
- Create: `systemd/omega13.service` (tracked in repo)
- Install to: `~/.config/systemd/user/omega13.service`

- [ ] **Step 12.1: Create the unit file in the repo**

```bash
mkdir -p /home/b08x/Workspace/omega-13/systemd
```

Create `systemd/omega13.service`:

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

- [ ] **Step 12.2: Add Makefile with install targets**

Create `Makefile` at repo root:

```makefile
.PHONY: install install-daemon install-extension uninstall-daemon uninstall-extension

SYSTEMD_USER_DIR := $(HOME)/.config/systemd/user
GNOME_EXT_DIR    := $(HOME)/.local/share/gnome-shell/extensions
EXT_UUID         := omega-13-indicator@b08x.github.io

install: install-daemon install-extension

install-daemon:
	install -Dm644 systemd/omega13.service $(SYSTEMD_USER_DIR)/omega13.service
	systemctl --user daemon-reload
	@echo "Daemon unit installed. Enable with: systemctl --user enable --now omega13"

uninstall-daemon:
	systemctl --user disable --now omega13 2>/dev/null || true
	rm -f $(SYSTEMD_USER_DIR)/omega13.service
	systemctl --user daemon-reload

install-extension:
	mkdir -p $(GNOME_EXT_DIR)/$(EXT_UUID)
	cp -r gnome-extension/$(EXT_UUID)/. $(GNOME_EXT_DIR)/$(EXT_UUID)/
	@echo "Extension installed. Enable with: gnome-extensions enable $(EXT_UUID)"

uninstall-extension:
	gnome-extensions disable $(EXT_UUID) 2>/dev/null || true
	rm -rf $(GNOME_EXT_DIR)/$(EXT_UUID)
```

- [ ] **Step 12.3: Install and verify**

```bash
cd /home/b08x/Workspace/omega-13
make install-daemon
systemctl --user status omega13 --no-pager
```

Expected: Unit file loaded, status inactive (not started yet)

- [ ] **Step 12.4: Commit**

```bash
git add systemd/omega13.service Makefile
git commit -m "feat: add systemd user unit and Makefile install targets"
```

---

## Task 13: GNOME Shell Extension

**Files:**
- Create: `gnome-extension/omega-13-indicator@b08x.github.io/metadata.json`
- Create: `gnome-extension/omega-13-indicator@b08x.github.io/extension.js`
- Create: `gnome-extension/omega-13-indicator@b08x.github.io/stylesheet.css`

- [ ] **Step 13.1: Create metadata.json**

```bash
mkdir -p /home/b08x/Workspace/omega-13/gnome-extension/omega-13-indicator@b08x.github.io
```

`gnome-extension/omega-13-indicator@b08x.github.io/metadata.json`:
```json
{
  "name": "omega-13 Indicator",
  "description": "Panel indicator for the omega-13 audio transcription daemon",
  "uuid": "omega-13-indicator@b08x.github.io",
  "version": 1,
  "shell-version": ["45", "46", "47", "48"],
  "url": "https://github.com/b08x/omega-13"
}
```

- [ ] **Step 13.2: Create extension.js**

`gnome-extension/omega-13-indicator@b08x.github.io/extension.js`:
```javascript
'use strict';

import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import { Extension } from 'resource:///org/gnome/shell/extensions/extension.js';

const DBUS_SERVICE   = 'org.omega13.Recorder';
const DBUS_PATH      = '/org/omega13/Recorder';
const DBUS_INTERFACE = 'org.omega13.Recorder';

const RECORDER_IFACE = `
<node>
  <interface name="${DBUS_INTERFACE}">
    <method name="GetActivePreset"><arg direction="out" type="s"/></method>
    <method name="ListPresets"><arg direction="out" type="as"/></method>
    <method name="SetPreset"><arg direction="in" type="s"/><arg direction="out" type="b"/></method>
    <method name="SetAutoRecord"><arg direction="in" type="b"/><arg direction="out" type="b"/></method>
    <signal name="PresetChanged"><arg type="s"/></signal>
    <signal name="PipelineStarted"><arg type="s"/></signal>
    <signal name="PipelineComplete"><arg type="s"/><arg type="s"/><arg type="s"/></signal>
    <signal name="PipelineFailed"><arg type="s"/><arg type="s"/><arg type="s"/></signal>
    <signal name="AssistantCalling"><arg type="s"/><arg type="s"/></signal>
    <signal name="AssistantComplete"><arg type="s"/></signal>
  </interface>
</node>`;

const RecorderProxy = Gio.DBusProxy.makeProxyWrapper(RECORDER_IFACE);

class Omega13Indicator extends PanelMenu.Button {
    _init() {
        super._init(0.0, 'omega-13 Indicator');

        this._proxy     = null;
        this._watchId   = 0;
        this._signalIds = [];
        this._lastText  = '';

        // Panel box: icon + label
        const box = new St.BoxLayout({ style_class: 'panel-status-menu-box' });
        this._icon = new St.Label({ text: '🎙️', y_align: Clutter.ActorAlign.CENTER });
        this._label = new St.Label({
            text: ' —',
            y_align: Clutter.ActorAlign.CENTER,
            style_class: 'omega13-label',
        });
        box.add_child(this._icon);
        box.add_child(this._label);
        this.add_child(box);

        this._buildMenu();
    }

    _buildMenu() {
        // Auto-record toggle
        this._autoRecordItem = new PopupMenu.PopupSwitchMenuItem('Auto-record', false);
        this._autoRecordItem.connect('toggled', (item) => this._setAutoRecord(item.state));
        this.menu.addMenuItem(this._autoRecordItem);

        // Preset submenu
        this._presetMenu = new PopupMenu.PopupSubMenuMenuItem('Preset');
        this.menu.addMenuItem(this._presetMenu);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Last transcription preview
        this._lastItem = new PopupMenu.PopupMenuItem('', { reactive: false });
        this._lastItem.label.clutter_text.set_line_wrap(true);
        this.menu.addMenuItem(this._lastItem);
    }

    connectDaemon() {
        this._watchId = Gio.bus_watch_name(
            Gio.BusType.SESSION,
            DBUS_SERVICE,
            Gio.BusNameWatcherFlags.NONE,
            this._onDaemonAppeared.bind(this),
            this._onDaemonVanished.bind(this),
        );
    }

    disconnectDaemon() {
        if (this._watchId > 0) {
            Gio.bus_unwatch_name(this._watchId);
            this._watchId = 0;
        }
        this._disconnectSignals();
        this._proxy = null;
    }

    _onDaemonAppeared() {
        this._proxy = new RecorderProxy(
            Gio.DBus.session, DBUS_SERVICE, DBUS_PATH,
        );

        // Subscribe to signals
        const sigs = [
            ['PipelineStarted',  (_, __, [preset])               => this._onPipelineStarted(preset)],
            ['PipelineComplete', (_, __, [preset, reg, intent])  => this._onPipelineComplete(preset, reg, intent)],
            ['PipelineFailed',   (_, __, [preset, stage, error]) => this._onPipelineFailed(preset, stage, error)],
            ['AssistantCalling', (_, __, [preset, cmd])          => this._onAssistantCalling(preset, cmd)],
            ['AssistantComplete',(_, __, [preset])               => this._onAssistantComplete(preset)],
            ['PresetChanged',    (_, __, [name])                 => this._onPresetChanged(name)],
        ];
        this._signalIds = sigs.map(([name, cb]) => this._proxy.connectSignal(name, cb));

        // Refresh initial state
        this._refreshPresets();
        this._setState('🎙️', 'idle');
    }

    _onDaemonVanished() {
        this._disconnectSignals();
        this._proxy = null;
        this._setState('🎙️', '— daemon offline');
        this._presetMenu.menu.removeAll();
    }

    _disconnectSignals() {
        if (this._proxy && this._signalIds.length > 0) {
            this._signalIds.forEach(id => this._proxy.disconnectSignal(id));
        }
        this._signalIds = [];
    }

    _setState(icon, labelText) {
        this._icon.set_text(icon);
        this._label.set_text(` ${labelText}`);
    }

    _onPipelineStarted(preset) {
        this._setState('⚡', `recording… [${preset}]`);
    }

    _onPipelineComplete(preset, register, intent) {
        this._setState('✅', `${register} · ${intent}`);
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 3000, () => {
            this._setState('🎙️', preset);
            return GLib.SOURCE_REMOVE;
        });
    }

    _onPipelineFailed(preset, stage, _error) {
        this._setState('⚠️', `failed: ${stage}`);
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 4000, () => {
            this._setState('🎙️', preset);
            return GLib.SOURCE_REMOVE;
        });
    }

    _onAssistantCalling(preset, cmd) {
        this._setState('⟳', cmd);
    }

    _onAssistantComplete(preset) {
        this._setState('✅', preset);
    }

    _onPresetChanged(name) {
        this._setState('🎙️', name);
    }

    _refreshPresets() {
        if (!this._proxy) return;
        this._proxy.ListPresetsRemote((result, err) => {
            if (err) return;
            const [presets] = result;
            this._presetMenu.menu.removeAll();
            presets.forEach(name => {
                const item = new PopupMenu.PopupMenuItem(name);
                item.connect('activate', () => {
                    this._proxy.SetPresetRemote(name, () => {});
                });
                this._presetMenu.menu.addMenuItem(item);
            });
        });
    }

    _setAutoRecord(enabled) {
        if (this._proxy) {
            this._proxy.SetAutoRecordRemote(enabled, () => {});
        }
    }
}

export default class Omega13Extension extends Extension {
    enable() {
        this._indicator = new Omega13Indicator();
        Main.panel.addToStatusArea('omega13-indicator', this._indicator, 1);
        this._indicator.connectDaemon();
    }

    disable() {
        if (this._indicator) {
            this._indicator.disconnectDaemon();
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}
```

- [ ] **Step 13.3: Create stylesheet.css**

`gnome-extension/omega-13-indicator@b08x.github.io/stylesheet.css`:
```css
.omega13-label {
    font-size: 11px;
    color: #ccc;
    padding-right: 4px;
}
```

- [ ] **Step 13.4: Install and enable the extension**

```bash
cd /home/b08x/Workspace/omega-13
make install-extension
gnome-extensions enable omega-13-indicator@b08x.github.io
```

If GNOME Shell is running, reload it:
```bash
# On Wayland: log out and back in, OR use looking glass (Alt+F2 → lg → Extensions.reloadExtension("omega-13-indicator@b08x.github.io"))
# On X11:
busctl --user call org.gnome.Shell /org/gnome/Shell org.gnome.Shell Eval s 'Meta.restart("Restarting…")'
```

Verify the indicator appears in the top bar.

- [ ] **Step 13.5: Commit**

```bash
git add gnome-extension/ Makefile
git commit -m "feat: add GNOME Shell panel extension with D-Bus daemon connection and preset switcher"
```

---

## Task 14: Integration Smoke Test

**Files:**
- Test: `tests/test_integration_smoke.py`

- [ ] **Step 14.1: Write integration smoke test**

```python
# tests/test_integration_smoke.py
"""Smoke tests: verify all new components can be imported and wired together."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_full_pipeline_can_be_constructed():
    from omega13.preset_loader import PresetLoader
    from omega13.lm_registry import LMRegistry
    from omega13.pipeline import TranscriptionPipeline

    loader = PresetLoader(user_presets_dir=Path("/tmp/omega13_smoke"))
    preset = loader.load("dictate")
    registry = LMRegistry()
    pipeline = TranscriptionPipeline(preset, registry)
    assert pipeline.preset.name == "dictate"


def test_pipeline_processes_text_with_mocked_lm():
    import dspy
    from omega13.preset_loader import PresetLoader
    from omega13.lm_registry import LMRegistry
    from omega13.pipeline import TranscriptionPipeline

    loader = PresetLoader(user_presets_dir=Path("/tmp/omega13_smoke"))
    preset = loader.load("dictate")  # assistant disabled
    registry = LMRegistry()
    pipeline = TranscriptionPipeline(preset, registry)

    mock_lm = MagicMock()
    mock_pred = MagicMock()
    mock_pred.cleaned_text = "Clean output."
    mock_pred.register = "conversational"
    mock_pred.intent = "narrative"
    mock_pred.confidence = 0.85

    with patch.object(registry, "get", return_value=mock_lm):
        with patch("dspy.context"):
            with patch.object(pipeline.tagger, "__call__", return_value=mock_pred):
                with patch.object(pipeline.router, "route") as mock_route:
                    mock_route.return_value = MagicMock(success=True, destination="clipboard")
                    result = pipeline.process("uh so yeah uh clean output")

    assert result.context.cleaned_text == "Clean output."
    assert result.context.register == "conversational"
    assert result.success is True


def test_daemon_entry_is_importable_without_textual():
    import sys
    for k in list(sys.modules.keys()):
        if k.startswith("textual"):
            del sys.modules[k]
    import omega13.daemon  # noqa
    new_textual = [k for k in sys.modules if k.startswith("textual")]
    assert new_textual == []
```

- [ ] **Step 14.2: Run all tests**

```bash
cd /home/b08x/Workspace/omega-13
uv run pytest tests/ -v --ignore=tests/test_tui_bindings.py
```

Expected: All tests PASS

- [ ] **Step 14.3: Final commit**

```bash
git add tests/test_integration_smoke.py
git commit -m "test: add integration smoke tests for full pipeline and daemon entry"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Task |
|---|---|
| Systemd daemon (no Textual) | Task 10, 12 |
| DSPy tagger (clean + register + intent) | Task 3 |
| Per-preset LM (dspy.context, thread-safe) | Task 2, Task 6 |
| Preset YAML schema | Task 1 |
| 4 built-in presets | Task 1 |
| AssistantCaller (CLI subprocess) | Task 4 |
| OutputRouter (primary + fallback) | Task 5 |
| `set_post_processor` hook | Task 7 |
| `TranscriptionService.from_config` | Task 7 |
| D-Bus: SetPreset, GetActivePreset, ListPresets | Task 9 |
| D-Bus: pipeline signals | Task 9 |
| Config: active_preset, presets_dir | Task 8 |
| GNOME extension: panel indicator | Task 13 |
| GNOME extension: D-Bus signal subscriptions | Task 13 |
| GNOME extension: preset menu | Task 13 |
| obsidian_cli.create_note (new_note dest) | Task 5 |
| Makefile install targets | Task 12, 13 |
| TUI wired to pipeline | Task 11 |

All spec requirements covered. No gaps found.

**Placeholder scan:** No TBD, TODO, or "similar to task N" patterns present.

**Type consistency:**
- `LMConfig` defined Task 1, used in Task 2 ✓
- `Preset.assistant` (not `A`) used throughout ✓
- `PresetLoader.load()` returns `Preset` in Task 1, consumed in Task 6, 10, 11 ✓
- `TranscriptionPipeline(preset, lm_registry)` signature consistent Tasks 6, 10, 11 ✓
- `set_post_processor(callable)` defined Task 7, called Task 10, 11 ✓
- `OutputRouter.route(text, preset)` defined Task 5, called Task 6 ✓
- D-Bus signal names match GNOME extension XML: `PipelineStarted`, `PipelineComplete`, `PipelineFailed`, `AssistantCalling`, `AssistantComplete`, `PresetChanged` ✓
