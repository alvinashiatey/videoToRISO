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
rm -rf build dist *.spec *.icns

# Generate ICNS file for macOS
echo "🎨 Generating App Icon..."
ICON_SOURCE="icons/Assets.xcassets/AppIcon.appiconset/1024-mac.png"

if [ -f "$ICON_SOURCE" ]; then
    mkdir VideoToRISO.iconset
    sips -z 16 16     "$ICON_SOURCE" --out VideoToRISO.iconset/icon_16x16.png > /dev/null
    sips -z 32 32     "$ICON_SOURCE" --out VideoToRISO.iconset/icon_16x16@2x.png > /dev/null
    sips -z 32 32     "$ICON_SOURCE" --out VideoToRISO.iconset/icon_32x32.png > /dev/null
    sips -z 64 64     "$ICON_SOURCE" --out VideoToRISO.iconset/icon_32x32@2x.png > /dev/null
    sips -z 128 128   "$ICON_SOURCE" --out VideoToRISO.iconset/icon_128x128.png > /dev/null
    sips -z 256 256   "$ICON_SOURCE" --out VideoToRISO.iconset/icon_128x128@2x.png > /dev/null
    sips -z 256 256   "$ICON_SOURCE" --out VideoToRISO.iconset/icon_256x256.png > /dev/null
    sips -z 512 512   "$ICON_SOURCE" --out VideoToRISO.iconset/icon_256x256@2x.png > /dev/null
    sips -z 512 512   "$ICON_SOURCE" --out VideoToRISO.iconset/icon_512x512.png > /dev/null
    sips -z 1024 1024 "$ICON_SOURCE" --out VideoToRISO.iconset/icon_512x512@2x.png > /dev/null
    
    iconutil -c icns VideoToRISO.iconset
    rm -rf VideoToRISO.iconset
    ICON_CMD="--icon=VideoToRISO.icns"
    echo "✅ Icon generated."
else
    echo "⚠️  $ICON_SOURCE not found. Skipping icon generation."
    ICON_CMD=""
fi

# Build with PyInstaller
echo "🔨 Building application..."

# --windowed: No console window (macOS .app)
# --onedir: Create a directory bundle
# --noconfirm: Overwrite output directory
# --clean: Clean PyInstaller cache
# --collect-all customtkinter: Include all customtkinter assets
# --paths app: Add app directory to python path so imports work
# --add-data "icons:icons": Include icons folder in the bundle

pyinstaller --noconfirm --onedir --windowed --clean \
    --name "$APP_NAME" \
    --collect-all customtkinter \
    --paths app \
    --add-data "icons:icons" \
    $ICON_CMD \
    "$MAIN_SCRIPT"

echo "✅ Build complete!"
echo "📁 Application is located at: dist/$APP_NAME.app"
