# Facts

- A new `justfile` handles project installation, replacing the old bash scripts.
- The `transcribe-cpp` dependency is installed via `uv pip install` with explicit CMake flags.
- The CMake flags always include `-DTRANSCRIBE_BUILD_SHARED=ON`.
- The installer dynamically checks for CUDA support using `ldconfig -p | grep -q 'libcuda.so'` and `command -v nvidia-smi`.
- If CUDA is detected, `-DTRANSCRIBE_CUDA=ON` and `-DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc` are appended to the CMake flags.
- The installer dynamically checks for Vulkan support using `ldconfig -p | grep -q 'libvulkan.so'`.
- If Vulkan hardware is detected, `-DTRANSCRIBE_VULKAN=ON` is dynamically appended to the CMake flags.
- A `just model dl` recipe provides an interactive selection menu using `gum choose`.
- Selected models are downloaded to the `~/.local/share/omega13/models` directory.
- The old bash scripts (`install.sh`, `uninstall.sh`, `bootstrap.sh`) are completely removed from the repository.
