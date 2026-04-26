#!/usr/bin/env bash
# build_installer.sh — Build the OnTrack Python installer binary.
#
# Usage:
#   cd ontrack/installer
#   bash build_installer.sh
#
# Output:
#   dist/OnTrackInstaller       (Linux)
#   dist/OnTrackInstaller.exe   (Windows, run from MSYS2/Git Bash or natively)

set -euo pipefail
cd "$(dirname "$0")"

echo "=== OnTrack Installer Build ==="

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.9+ and try again." >&2
    exit 1
fi

# Create/activate a temporary build venv
VENV="$(mktemp -d)/installer_build_venv"
python3 -m venv "$VENV"
source "$VENV/bin/activate"

pip install --quiet --upgrade pip
pip install --quiet customtkinter Pillow pyinstaller

echo "Building installer binary with PyInstaller…"
pyinstaller installer.spec --noconfirm --clean

echo ""
echo "=== Build complete ==="
ls -lh dist/OnTrackInstaller* 2>/dev/null || true
deactivate
