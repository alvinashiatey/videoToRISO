# VideoToRISO

VideoToRISO is a Python application designed for artists and printmakers. It converts video files into contact sheets and automatically separates them into color channels (RGB) prepared for RISO printing. It also includes various dithering effects to simulate halftone screens and other textures.

## Features

- **Video Frame Extraction**: Automatically extract frames from video files at set intervals.
- **Contact Sheet Generation**: Arranges frames into a customizable grid layout.
- **RISO Color Separation**: Splits full-color sheets into separate Red, Green, and Blue channel layers.
- **Dithering Effects**: Apply creative effects to your layers:
  - Floyd-Steinberg
  - Threshold
  - Halftone
  - Pixelate
  - Scanlines
- **PDF Output**: Generates a single, labeled PDF containing the composite image and all separated color layers.
- **Modern GUI**: Clean, dark-themed interface built with CustomTkinter.

## Installation

### Option 1: Homebrew (macOS)

If you have set up the tap (as described in the `homebrew/` directory):

```bash
brew tap alvinashiatey/tap
brew install --cask videotoriso
```

### Option 2: Run from Source

1. **Clone the repository:**

   ```bash
   git clone https://github.com/alvinashiatey/videoToRISO.git
   cd videoToRISO
   ```

2. **Set up a virtual environment:**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**
   ```bash
   python app/app.py
   ```

## Usage

1. **Select Video**: Choose the video file you want to process.
2. **Select Output**: Choose where you want the generated PDF to be saved.
3. **Configure**:
   - **Columns**: Number of thumbnails per row.
   - **Interval**: Time in seconds between captured frames.
   - **Effect**: Choose a dither effect for the separated layers.
   - **Channels**: Select which color channels (Red, Green, Blue) to generate.
4. **Generate**: Click "Generate Sheets". The application will process the video and automatically open the resulting PDF when finished.

## Building for macOS

To create a standalone `.app` bundle:

```bash
./build.sh
```

The application will be built to `dist/VideoToRISO.app`.

## License

MIT License
