# Plan: Justfile Migration

## Solution Approach
We will replace the existing bash installation scripts (`install.sh`, `bootstrap.sh`, `uninstall.sh`) with a single `Justfile`. The Justfile will use shell backticks and bash shebang recipes to dynamically evaluate hardware dependencies (CUDA, Vulkan) via `ldconfig` and pass the correct `CMAKE_ARGS` to the `uv pip install` command. We will also implement a `model` recipe to handle downloading models interactively using `gum choose`, and add a step to install `ydotool` from source if it isn't already installed, along with adding detailed debug logging for `ydotool` calls in the application code.

## Ordered Steps
1. **Create the Justfile**:
   - Define global variables for the model directory: `model_dir := "~/.local/share/omega13/models"`.
   - Define variables checking for CUDA and Vulkan using `ldconfig -p`.
2. **Add the `install` recipe**:
   - Use a `#!/usr/bin/env bash` block.
   - Add checks for `cpulimit` and `taskset`. If absent, display warnings that these are used to prevent the host from being consumed by the build.
   - Construct `CMAKE_ARGS` dynamically based on the hardware variables.
   - Execute the `nice ... cpulimit ... uv pip install` command.
3. **Add the `ydotool` compilation check in the Justfile**:
   - If `ydotool` is not installed as a user service, execute the provided bash sequence:
     - Clone `https://github.com/ReimuNotMoe/ydotool.git` to `~/.local/src/ydotool`.
     - Run `cmake -B build -DSYSTEMD_USER_SERVICE=ON`
     - Run `nice -n 19 ionice -c 3 taskset -c 0-3 cpulimit -l 150 -- make -j4 && sudo make install`
     - Run `systemctl --user enable --now ydotoold`
4. **Implement Detailed Debug Logging for `ydotool`**:
   - Locate the `ydotool` calls within the application codebase (e.g., in `src/omega13/injection.py`).
   - Add detailed `logger.debug` statements around the execution of `ydotool` to capture arguments, environment variables, execution timing, and output.
5. **Add the `model` recipe**:
   - Define a recipe `model ACTION="dl"`.
   - Inside, if the action is `dl`, use `gum choose` to present the Whisper and Parakeet models.
   - Download the chosen model to `~/.local/share/omega13/models`.
6. **Remove old bash scripts**:
   - Delete `install.sh`, `uninstall.sh`, and `bootstrap.sh`.

## Verification
- **Automated Verification**: Run `just --list` to verify the syntax is valid. Run `just --evaluate` to ensure dynamic variables compile.
- **Manual Verification**: Run `just install` and observe the hardware warnings/installations (such as the ydotool build and resource constraints). Run `just model dl` to verify the `gum` UI renders.

## Risks & Open Questions
- `gum` must be installed on the system for `just model dl` to work. We can add a quick check inside the recipe to warn the user if `gum` is missing.
- Building `ydotool` requires `sudo` for `make install`. This will prompt the user for their password during the `just install` step.
