# Video to RISO Thumbnail Generator - Implementation Plan

This document outlines the approach to building a Python application that converts a video file into contact sheets (thumbnail sheets) formatted for Letter-size paper (8.5" x 11"), suitable for RISO printing.

## 1. Project Overview

**Goal**: Take a video file as input, extract frames at regular intervals, and arrange them on a printable sheet while preserving the video's aspect ratio.

**Key Features**:

- Support for common video formats (.mp4, .mov).
- Automatic calculation of thumbnail sizes based on grid layout.
- Output high-resolution images (300 DPI) ready for printing.
- **Channel Separation**: Split final sheets into separate grayscale files (e.g., C, M, Y, K) for RISO drum printing.
- **GUI**: A user-friendly interface for selecting files and adjusting settings.

## 2. Technical Stack

- **Language**: Python 3
- **Libraries**:
  - `opencv-python` (`cv2`): For reading video files and extracting frames.
  - `Pillow` (`PIL`): For image manipulation, resizing, and creating the final sheet layout.
  - `numpy`: For efficient array handling (often used with OpenCV).
  - `customtkinter`: For a modern, dark-mode supported GUI (wrapper around `tkinter`).

## 3. Implementation Steps

### Step 1: Environment Setup

Create a virtual environment and install necessary packages.

```bash
python3 -m venv venv
source venv/bin/activate
pip install opencv-python Pillow numpy
```

### Step 2: Video Processing (`VideoProcessor`)

We need a component to handle the video input.

- **Input**: Video file path.
- **Operations**:
  - Open video using `cv2.VideoCapture`.
  - Retrieve metadata: Width, Height, FPS, Total Frame Count.
  - Calculate Aspect Ratio ($Width / Height$).
  - **Frame Extraction**: Define a strategy to extract frames (e.g., "Extract 1 frame every 2 seconds" or "Extract exactly 24 frames total").

### Step 3: Layout Calculation (`LayoutEngine`)

This is the core logic for the "RISO" part—formatting for print.

- **Constants**:
  - Paper Size: Letter (8.5 x 11 inches).
  - DPI: 300 (Standard for print).
  - Canvas Size (Pixels): $2550 \times 3300$ px.
  - Margins: e.g., 0.5 inches ($150$ px).
- **Grid Logic**:
  - Determine how many columns and rows fit on a page.
  - Calculate the width of a single thumbnail:
    $$ \text{ThumbWidth} = \frac{\text{PrintableWidth} - (\text{Spacing} \times (\text{Cols} - 1))}{\text{Cols}} $$
  - Calculate height based on the video's aspect ratio.

### Step 4: Image Composition

- Create a blank white canvas using `PIL.Image.new()`.
- Iterate through extracted frames:
  1. Convert OpenCV image (BGR) to PIL image (RGB).
  2. Resize image to calculated thumbnail dimensions (using high-quality resampling).
  3. Paste into the correct $(x, y)$ coordinates on the canvas.
- If the grid fills up, save the current page and start a new one.

### Step 5: Channel Separation (RISO Prep)

RISO printers require separate master files for each ink color.

- Convert the final composed sheet to CMYK (or keep as RGB if doing 3-color RISO).
- Split the image into individual channels.
- Convert each channel to a Grayscale image (Black = Heavy Ink, White = No Ink).

### Step 6: Output

- Save the generated sheets and their separated channels.
- Naming convention: `sheet_0_cyan.png`, `sheet_0_magenta.png`, etc.

### Step 7: User Interface (GUI)

Build a GUI using `customtkinter` to make the tool easy to use.

- **Components**:
  - **File Selector**: Button to choose the input video file.
  - **Settings**: Inputs for Columns, Rows (optional), Margins, and Output Directory.
  - **Channel Toggles**: Checkboxes to select which RISO channels to generate (Cyan, Magenta, Yellow, Black).
  - **Run Button**: Triggers the processing.
  - **Progress Bar**: Visual feedback during frame extraction and sheet generation.

## 4. Proposed Code Structure

```text
videoToRISO/
├── app/
│   ├── main.py           # Main entry point (GUI launch)
│   ├── gui.py            # GUI implementation
│   ├── processor.py      # Handles video frame extraction
│   └── layout.py         # Handles sheet calculation and image pasting
├── output/               # Generated sheets go here
├── requirements.txt
└── README.md
```

## 5. Example Usage

```python
# Pseudo-code for main.py
video = VideoProcessor("input_video.mp4")
frames = video.extract_frames(interval_seconds=1)

layout = SheetLayout(paper_size="LETTER", dpi=300)
pages = layout.create_sheets(frames, columns=3)

for i, page in enumerate(pages):
    page.save(f"output/sheet_{i}.png")
```
