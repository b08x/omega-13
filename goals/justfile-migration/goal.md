# Justfile Migration and Installer Update

## Goal
The objective is to replace the existing bash setup scripts with a `justfile` that robustly handles installing `transcribe-cpp` via `uv pip install` with dynamic hardware-specific CMake flags (CUDA, Vulkan), provides an interactive model download menu via `gum`, and ensures `ydotool` is properly installed and debuggable.

## Shared Understanding
See [facts.md](./facts.md) for the agreed-upon facts and constraints that govern this goal.

## Execution Plan
See [plan.md](./plan.md) for the detailed step-by-step execution plan.

## Done Condition
- A single `Justfile` replaces `install.sh`, `uninstall.sh`, and `bootstrap.sh`.
- Running `just install` automatically evaluates hardware support (CUDA, Vulkan) using `ldconfig`/`nvidia-smi` and passes the correct `CMAKE_ARGS` to the build.
- Warnings are emitted if `cpulimit` or `taskset` are missing.
- `ydotool` is built from source and installed as a user service if not already present.
- Detailed debug logging is added to the `ydotool` calls in the application code.
- `just model dl` opens a `gum choose` interface and successfully downloads the selected model to `~/.local/share/omega13/models`.
- The old bash scripts are deleted from the repository.
