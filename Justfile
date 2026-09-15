model_dir := "$HOME/.local/share/omega13/models"

install:
    #!/usr/bin/env bash
    set -e
    
    if ! command -v cpulimit >/dev/null; then
        echo "WARNING: cpulimit not found. Build may consume excessive resources."
    fi
    if ! command -v taskset >/dev/null; then
        echo "WARNING: taskset not found. Build may consume excessive resources."
    fi

    CMAKE_ARGS="-DTRANSCRIBE_BUILD_SHARED=ON"
    
    if ldconfig -p | grep -q 'libcuda\.so' && command -v nvidia-smi >/dev/null; then
        echo "CUDA hardware detected."
        CMAKE_ARGS="$CMAKE_ARGS -DTRANSCRIBE_CUDA=ON -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc"
    fi
    
    if ldconfig -p | grep -q 'libvulkan\.so'; then
        echo "Vulkan runtime detected."
        CMAKE_ARGS="$CMAKE_ARGS -DTRANSCRIBE_VULKAN=ON"
    fi
    
    export CMAKE_ARGS
    echo "Building transcribe-cpp with CMAKE_ARGS: $CMAKE_ARGS"
    
    if command -v cpulimit >/dev/null && command -v taskset >/dev/null && command -v nice >/dev/null; then
        nice -n 19 taskset -c 0-3 cpulimit -l 150 -- uv pip install transcribe-cpp
    else
        uv pip install transcribe-cpp
    fi

    if ! systemctl --user is-enabled --quiet ydotoold 2>/dev/null; then
        echo "ydotool user service not found. Installing from source..."
        mkdir -p ~/.local/src
        if [ ! -d ~/.local/src/ydotool ]; then
            git clone https://github.com/ReimuNotMoe/ydotool.git ~/.local/src/ydotool
        fi
        cd ~/.local/src/ydotool
        cmake -B build -DSYSTEMD_USER_SERVICE=ON
        if command -v cpulimit >/dev/null && command -v taskset >/dev/null && command -v ionice >/dev/null; then
            nice -n 19 ionice -c 3 taskset -c 0-3 cpulimit -l 150 -- make -C build -j4
        else
            make -C build -j4
        fi
        sudo make -C build install
        systemctl --user enable --now ydotoold
    fi

model ACTION="dl":
    #!/usr/bin/env bash
    set -e
    
    if ! command -v gum >/dev/null; then
        echo "WARNING: 'gum' is not installed. Please install 'gum' for interactive model downloads."
        exit 1
    fi
    
    if [ "{{ACTION}}" = "dl" ]; then
        mkdir -p "{{model_dir}}"
        echo "Select models to download (Space to select, Enter to confirm):"
        DOWNLOAD_MODELS=$(gum choose --no-limit "nemotron-3.5-asr-streaming-0.6b" "parakeet-unified-en-0.6b" "whisper-large-v3-turbo")
        
        if [ -n "$DOWNLOAD_MODELS" ]; then
            for model in $DOWNLOAD_MODELS; do
                MODEL_FILE="${model}-Q8_0.gguf"
                MODEL_URL="https://huggingface.co/handy-computer/${model}-gguf/resolve/main/${MODEL_FILE}"
                MODEL_PATH="{{model_dir}}/${MODEL_FILE}"
                
                if [ ! -f "$MODEL_PATH" ]; then
                    gum spin --title "Downloading $MODEL_FILE..." -- curl -L -o "$MODEL_PATH" "$MODEL_URL"
                    gum style --foreground 76 "✅ Downloaded $MODEL_FILE to $MODEL_PATH"
                else
                    gum style --foreground 76 "✅ $MODEL_FILE is already downloaded at $MODEL_PATH"
                fi
            done
            
            gum style --foreground 212 "Select the default model to use:"
            FILE_LIST=""
            for model in $DOWNLOAD_MODELS; do
                FILE_LIST="$FILE_LIST ${model}-Q8_0.gguf"
            done
            DEFAULT_MODEL=$(gum choose $FILE_LIST)
            THREADS=$(gum input --prompt "Number of threads (e.g. 4): " --placeholder "4" --value "4")
            
            CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/omega13"
            mkdir -p "$CONFIG_DIR"
            CONFIG_FILE="$CONFIG_DIR/config.json"
            
            python3 -c "import json, os; config_file='$CONFIG_FILE'; data=json.load(open(config_file)) if os.path.exists(config_file) else {}; data.setdefault('transcription', {})['local_model_path']='{{model_dir}}'; data['transcription']['local_model_name']='$DEFAULT_MODEL'; data['transcription']['local_model_threads']=int('$THREADS'); json.dump(data, open(config_file, 'w'), indent=2)"
            gum style --foreground 76 "✅ Saved default model ($DEFAULT_MODEL) and thread settings to config.json"
        fi
    fi

check:
    #!/usr/bin/env bash
    set -e
    
    echo "Omega-13 Dependency Check"
    echo "========================="
    
    missing=0
    
    check_cmd() {
        if command -v "$1" >/dev/null 2>&1; then
            echo "✅ $1 is installed ($(command -v "$1"))"
        else
            echo "❌ $1 is MISSING (required)"
            missing=$((missing + 1))
        fi
    }
    
    check_lib() {
        if ldconfig -p | grep -q "$2" || pkg-config --exists "$3" 2>/dev/null; then
            echo "✅ $1 is installed"
        else
            echo "❌ $1 is MISSING (required system library)"
            missing=$((missing + 1))
        fi
    }
    
    echo "Checking executables..."
    check_cmd "python3"
    check_cmd "uv"
    check_cmd "ffmpeg"
    check_cmd "sox"
    check_cmd "ydotool"
    check_cmd "gum"
    check_cmd "pytest"
    
    echo ""
    echo "Checking shared libraries..."
    check_lib "JACK/PipeWire-JACK" "libjack\.so" "jack"
    check_lib "GTK4 Layer Shell" "libgtk4-layer-shell\.so" "gtk4-layer-shell-0"
    check_lib "Cairo" "libcairo\.so" "cairo"
    check_lib "GObject Introspection" "libgirepository" "gobject-introspection-1.0"
    
    echo ""
    if [ "$missing" -eq 0 ]; then
        echo "🎉 All dependencies are satisfied!"
    else
        echo "⚠️  Found $missing missing dependencies. Please install them to ensure Omega-13 operates correctly."
        exit 1
    fi

test:
    #!/usr/bin/env bash
    set -e
    echo "Running tests..."
    pytest

