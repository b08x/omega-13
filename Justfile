model_dir := "$HOME/.local/share/omega13/models"

# Developer task runner — not the installer.
# To install: ./install.sh
# To uninstall: ./uninstall.sh

# Run test suite
test:
    pytest

# Run omega13 in foreground (dev mode)
dev:
    uv run omega13 --no-daemon

# Run omega13 and toggle recording
toggle:
    uv run omega13 --toggle

# Download/manage whisper models
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
