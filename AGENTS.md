# Development Commands

**Setup**: `uv sync` | **Run**: `uv run python -m omega13` | **Dev mode**: `textual run --dev src/omega13/app.py`
**Single test**: `cd tests && python -c "import sys; sys.path.append('../src'); import test_incremental_save; test_incremental_save.test_incremental_save()"`

# Code Style Guidelines

- **Imports**: stdlib → third-party → relative imports; use absolute imports from project root
- **Types**: Use type hints (PEP 695 style: `list[str] | None`); `Optional[Path]` for Optional
- **Naming**: `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE_CASE` constants
- **Docstrings**: On classes and public methods only
- **Textual**: `on_*` for event handlers, `action_*` for keybindings; CSS in class docstrings
- **Logging**: `logger = logging.getLogger(__name__)` at module top
- **Error handling**: JACK process callback must never block; swallow exceptions for stability
- **Threading**: File writer uses `daemon=False` for data integrity; `queue.Queue()` for thread-safe data
- **Python**: 3.12+ required; no code comments unless explicitly requested

# Critical Architecture Patterns

See CLAUDE.md for detailed architecture patterns including:

- Multi-threading safety model (JACK callback must never block)
- Session management lifecycle (temporary-then-permanent storage)
- Rolling buffer implementation (13-second circular buffer)
- Configuration & state management (JSON config with versioning)
- JACK client lifecycle (activation/deactivation patterns)
- Transcription async pattern (background threads with callbacks)
