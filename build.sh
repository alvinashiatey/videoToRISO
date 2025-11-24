#!/bin/bash

# Exit on error
set -e

APP_NAME="VideoToRISO"
MAIN_SCRIPT="app/app.py"

echo "🚀 Starting build process for $APP_NAME..."

# Check if virtual environment exists, if not create it
if [ ! -d ".venv" ] && [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
else
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    else
        source venv/bin/activate
    fi
fi

# Install dependencies
echo "⬇️  Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Clean previous builds
echo "🧹 Cleaning up previous builds..."
rm -rf build dist *.spec

# Build with PyInstaller
echo "🔨 Building application..."

# --windowed: No console window (macOS .app)
# --onedir: Create a directory bundle
# --noconfirm: Overwrite output directory
# --clean: Clean PyInstaller cache
# --collect-all customtkinter: Include all customtkinter assets
# --paths app: Add app directory to python path so imports work

pyinstaller --noconfirm --onedir --windowed --clean \
    --name "$APP_NAME" \
    --collect-all customtkinter \
    --paths app \
    "$MAIN_SCRIPT"

echo "✅ Build complete!"
echo "📁 Application is located at: dist/$APP_NAME.app"
