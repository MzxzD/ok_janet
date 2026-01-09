#!/bin/bash

# Bootstrap script for Janet Mesh Network
# Detects device capabilities and starts appropriate services

set -e

echo "🌐 Bootstrapping Janet Mesh Network..."

# Detect device type
detect_device() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        if [[ $(uname -m) == "arm64" ]]; then
            echo "mac_arm"
        else
            echo "mac_intel"
        fi
    elif [[ "$OSTYPE" == "linux"* ]]; then
        if [[ -f /etc/rpi-issue ]] || [[ -f /proc/device-tree/model ]]; then
            echo "raspberry_pi"
        else
            echo "linux"
        fi
    else
        echo "unknown"
    fi
}

# Get local IP
get_local_ip() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        ipconfig getifaddr en0 || ipconfig getifaddr en1 || echo "127.0.0.1"
    else
        hostname -I | awk '{print $1}' || echo "127.0.0.1"
    fi
}

# Detect capabilities
detect_capabilities() {
    local device=$(detect_device)
    local caps=()
    
    # Check RAM
    if [[ "$OSTYPE" == "darwin"* ]]; then
        ram_gb=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024/1024)}')
    else
        ram_gb=$(free -g | awk '/^Mem:/{print $2}')
    fi
    
    # Check for GPU
    if command -v nvidia-smi &> /dev/null; then
        caps+=("gpu" "cuda")
    fi
    
    if [[ "$device" == "mac_arm" ]]; then
        caps+=("metal" "coreml")
    fi
    
    if [[ $ram_gb -ge 16 ]]; then
        caps+=("large_models" "multiple_models")
    elif [[ $ram_gb -ge 8 ]]; then
        caps+=("large_models")
    fi
    
    echo "${caps[@]}"
}

# Main
DEVICE=$(detect_device)
LOCAL_IP=$(get_local_ip)
CAPABILITIES=$(detect_capabilities)

echo "Device: $DEVICE"
echo "Local IP: $LOCAL_IP"
echo "Capabilities: $CAPABILITIES"

# Determine role
ROLE=${1:-"brain"}

case $ROLE in
    "brain")
        echo "Starting as BRAIN node..."
        cd "$(dirname "$0")/.."
        python -m server.main --host 0.0.0.0 --port 8765 --service-name "janet-brain-$HOSTNAME"
        ;;
    "stt-node")
        echo "Starting as STT node..."
        # Start STT service
        python -m server.services.stt_service --port 8766
        ;;
    "tts-node")
        echo "Starting as TTS node..."
        # Start TTS service
        python -m server.services.tts_service --port 8767
        ;;
    "client")
        echo "Starting as CLIENT..."
        if [[ "$DEVICE" == "mac"* ]]; then
            # Launch macOS client
            if [[ -f "clients/mac/JanetMeshClient.app" ]]; then
                open clients/mac/JanetMeshClient.app
            else
                echo "macOS client not found. Build it first."
            fi
        else
            echo "Client mode not yet implemented for this platform"
        fi
        ;;
    *)
        echo "Unknown role: $ROLE"
        echo "Usage: $0 [brain|stt-node|tts-node|client]"
        exit 1
        ;;
esac
