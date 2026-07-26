#!/usr/bin/env bash
# setup.sh — one-time setup for Linux and macOS
# Installs ffmpeg (if missing) and creates a Python virtual environment
# with the required packages.

set -e

echo "=== Phone Media Organizer — Setup ==="

OS="$(uname -s)"

# --- 1. ffmpeg / ffprobe -----------------------------------------------
if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
    echo "[ok] ffmpeg / ffprobe already installed."
else
    echo "[..] ffmpeg not found, installing..."
    if [ "$OS" = "Darwin" ]; then
        if ! command -v brew >/dev/null 2>&1; then
            echo "Homebrew not found. Install it first: https://brew.sh"
            exit 1
        fi
        brew install ffmpeg
    elif [ "$OS" = "Linux" ]; then
        if command -v apt >/dev/null 2>&1; then
            sudo apt update && sudo apt install -y ffmpeg
        elif command -v pacman >/dev/null 2>&1; then
            sudo pacman -S --noconfirm ffmpeg
        elif command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y ffmpeg
        else
            echo "Could not detect package manager. Please install ffmpeg manually."
            exit 1
        fi
    else
        echo "Unsupported OS: $OS. This tool supports Linux and macOS only."
        exit 1
    fi
fi

# --- 2. Python virtual environment --------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "[..] Creating virtual environment..."
    python3 -m venv venv
fi

echo "[..] Installing Python packages..."
./venv/bin/pip install --upgrade pip >/dev/null
./venv/bin/pip install -r requirements.txt

echo ""
echo "=== Setup complete ==="
echo ""
echo "Usage:"
echo "  ./venv/bin/python3 scan_index.py \"/path/to/RAW\""
echo "  ./venv/bin/python3 organize.py \"/path/to/RAW\"           # dry run"
echo "  ./venv/bin/python3 organize.py \"/path/to/RAW\" --apply    # actually copy"
echo ""
echo "See README.md for the full guide."
