"""
Video Assembly Module

Assembles extracted frames from scanned contact sheets back into
video files, handling multi-page assembly and timing.
"""

import os
import cv2
import numpy as np
from PIL import Image
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass


@dataclass
class VideoSettings:
    """Settings for video output."""
    fps: float = 24.0
    codec: str = 'mp4v'  # 'mp4v', 'avc1', 'XVID', etc.
    quality: int = 95  # For JPEG-based codecs
    frame_duration: Optional[float] = None  # Hold each frame for X seconds
    resolution: Optional[Tuple[int, int]] = None  # Output resolution
    maintain_aspect: bool = True


class MultiPageAssembler:
    """
    Handle reconstruction from multiple scanned contact sheets.
    Manages page ordering and frame sequence assembly.
    """

    def __init__(self):
        self.pages: Dict[int, List[Image.Image]] = {}
        self.metadata: Dict[int, dict] = {}

    def add_page(self,
                 frames: List[Image.Image],
                 page_number: Optional[int] = None,
                 metadata: Optional[dict] = None) -> int:
        """
        Add a page of extracted frames.

        Args:
            frames: List of PIL Images from this page
            page_number: Page number (auto-assigned if None)
            metadata: Optional metadata dict

        Returns:
            Assigned page number
        """
        if page_number is None:
            # Auto-assign next page number
            page_number = max(self.pages.keys(), default=0) + 1

        self.pages[page_number] = frames
        if metadata:
            self.metadata[page_number] = metadata

        return page_number

    def get_page_count(self) -> int:
        """Return number of pages added."""
        return len(self.pages)

    def get_frame_count(self) -> int:
        """Return total number of frames across all pages."""
        return sum(len(frames) for frames in self.pages.values())

    def validate_continuity(self) -> Tuple[bool, List[int]]:
        """
        Check if pages form a continuous sequence.

        Returns:
            Tuple of (is_valid, missing_pages)
        """
        if not self.pages:
            return True, []

        page_nums = sorted(self.pages.keys())
        expected = list(range(page_nums[0], page_nums[-1] + 1))
        missing = [p for p in expected if p not in page_nums]

        return len(missing) == 0, missing

    def assemble(self) -> List[Image.Image]:
        """
        Combine all pages into a single frame sequence.

        Returns:
            List of all frames in order
        """
        if not self.pages:
            return []

        # Sort by page number and concatenate
        all_frames = []
        for page_num in sorted(self.pages.keys()):
            all_frames.extend(self.pages[page_num])

        return all_frames

    def clear(self):
        """Clear all pages."""
        self.pages.clear()
        self.metadata.clear()


class VideoAssembler:
    """
    Assemble extracted frames into video files.
    Supports various output formats and timing options.
    """

    # Codec mappings for different formats
    CODECS = {
        'mp4': 'mp4v',
        'avi': 'XVID',
        'mov': 'mp4v',
        'mkv': 'mp4v',
    }

    def __init__(self,
                 frames: Optional[List[Image.Image]] = None,
                 settings: Optional[VideoSettings] = None):
        """
        Initialize the video assembler.

        Args:
            frames: List of PIL Images to assemble
            settings: VideoSettings for output
        """
        self.frames = frames or []
        self.settings = settings or VideoSettings()
        self._page_assembler = MultiPageAssembler()

    def add_frames(self, frames: List[Image.Image]):
        """Add frames to the assembly queue."""
        self.frames.extend(frames)

    def add_page(self,
                 frames: List[Image.Image],
                 page_number: Optional[int] = None) -> int:
        """
        Add a page of frames (for multi-page assembly).

        Args:
            frames: Frames from this page
            page_number: Optional page number

        Returns:
            Assigned page number
        """
        return self._page_assembler.add_page(frames, page_number)

    def assemble_pages(self):
        """Combine all added pages into the frame list."""
        self.frames = self._page_assembler.assemble()

    def set_fps(self, fps: float):
        """Set output frame rate."""
        self.settings.fps = fps

    def set_frame_duration(self, duration: float):
        """
        Set how long each frame should be held.

        Args:
            duration: Duration in seconds per frame
        """
        self.settings.frame_duration = duration

    def export(self,
               output_path: str,
               fps: Optional[float] = None,
               audio_path: Optional[str] = None) -> str:
        """
        Export frames to video file.

        Args:
            output_path: Path for output video file
            fps: Frames per second (overrides settings)
            audio_path: Optional path to audio file to add

        Returns:
            Path to created video file
        """
        if not self.frames:
            raise ValueError("No frames to export")

        fps = fps or self.settings.fps

        # Determine output format and codec
        ext = os.path.splitext(output_path)[1].lower().lstrip('.')
        codec = self.CODECS.get(ext, 'mp4v')

        # Get frame dimensions
        first_frame = self.frames[0]
        if self.settings.resolution:
            width, height = self.settings.resolution
        else:
            width, height = first_frame.size

        # Calculate effective FPS based on frame duration
        if self.settings.frame_duration:
            effective_fps = 1.0 / self.settings.frame_duration
        else:
            effective_fps = fps

        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*codec)
        writer = cv2.VideoWriter(
            output_path, fourcc, effective_fps, (width, height))

        if not writer.isOpened():
            raise RuntimeError(
                f"Could not open video writer for {output_path}")

        try:
            for frame in self.frames:
                # Resize if needed
                if frame.size != (width, height):
                    frame = self._resize_frame(frame, width, height)

                # Convert to BGR for OpenCV
                cv_frame = self._pil_to_cv(frame)

                # Write frame (possibly multiple times for frame duration)
                if self.settings.frame_duration and fps:
                    # Hold frame for specified duration
                    repeat_count = int(fps * self.settings.frame_duration)
                    repeat_count = max(1, repeat_count)
                    for _ in range(repeat_count):
                        writer.write(cv_frame)
                else:
                    writer.write(cv_frame)
        finally:
            writer.release()

        # Add audio if provided
        if audio_path and os.path.exists(audio_path):
            output_path = self._add_audio(output_path, audio_path)

        return output_path

    def export_gif(self,
                   output_path: str,
                   fps: Optional[float] = None,
                   optimize: bool = True,
                   loop: int = 0) -> str:
        """
        Export frames as animated GIF.

        Args:
            output_path: Path for output GIF file
            fps: Frames per second
            optimize: Optimize GIF palette
            loop: Number of loops (0 = infinite)

        Returns:
            Path to created GIF file
        """
        if not self.frames:
            raise ValueError("No frames to export")

        fps = fps or self.settings.fps
        duration = int(1000 / fps)  # Duration per frame in ms

        if self.settings.frame_duration:
            duration = int(self.settings.frame_duration * 1000)

        # Resize frames if needed
        frames_to_save = []
        for frame in self.frames:
            if self.settings.resolution:
                frame = self._resize_frame(frame, *self.settings.resolution)

            # Convert to RGB if needed
            if frame.mode != 'RGB':
                frame = frame.convert('RGB')

            # Convert to palette mode for GIF
            frame = frame.convert('P', palette=Image.ADAPTIVE, colors=256)
            frames_to_save.append(frame)

        # Save GIF
        frames_to_save[0].save(
            output_path,
            save_all=True,
            append_images=frames_to_save[1:],
            duration=duration,
            loop=loop,
            optimize=optimize
        )

        return output_path

    def export_image_sequence(self,
                              output_dir: str,
                              prefix: str = "frame",
                              format: str = "png",
                              start_number: int = 1) -> List[str]:
        """
        Export frames as image sequence.

        Args:
            output_dir: Directory for output images
            prefix: Filename prefix
            format: Image format (png, jpg, tiff)
            start_number: Starting frame number

        Returns:
            List of created file paths
        """
        if not self.frames:
            raise ValueError("No frames to export")

        os.makedirs(output_dir, exist_ok=True)

        paths = []
        num_digits = len(str(len(self.frames) + start_number))

        for i, frame in enumerate(self.frames):
            frame_num = start_number + i
            filename = f"{prefix}_{frame_num:0{num_digits}d}.{format}"
            filepath = os.path.join(output_dir, filename)

            # Resize if needed
            if self.settings.resolution:
                frame = self._resize_frame(frame, *self.settings.resolution)

            frame.save(filepath)
            paths.append(filepath)

        return paths

    def _resize_frame(self,
                      frame: Image.Image,
                      width: int,
                      height: int) -> Image.Image:
        """Resize frame to target dimensions."""
        if self.settings.maintain_aspect:
            # Calculate scaling to fit within bounds
            scale = min(width / frame.width, height / frame.height)
            new_w = int(frame.width * scale)
            new_h = int(frame.height * scale)

            # Resize
            resized = frame.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Create canvas and paste centered
            canvas = Image.new('RGB', (width, height), (0, 0, 0))
            x = (width - new_w) // 2
            y = (height - new_h) // 2
            canvas.paste(resized, (x, y))

            return canvas
        else:
            return frame.resize((width, height), Image.Resampling.LANCZOS)

    def _pil_to_cv(self, image: Image.Image) -> np.ndarray:
        """Convert PIL Image to OpenCV BGR format."""
        if image.mode != 'RGB':
            image = image.convert('RGB')
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    def _add_audio(self,
                   video_path: str,
                   audio_path: str) -> str:
        """
        Add audio track to video using ffmpeg.

        Args:
            video_path: Path to video file
            audio_path: Path to audio file

        Returns:
            Path to output file with audio
        """
        try:
            import subprocess

            # Create output path
            base, ext = os.path.splitext(video_path)
            output_path = f"{base}_with_audio{ext}"

            # Run ffmpeg
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                '-shortest',
                output_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                # Remove original without audio
                os.remove(video_path)
                os.rename(output_path, video_path)
                return video_path
            else:
                print(f"FFmpeg error: {result.stderr}")
                return video_path

        except FileNotFoundError:
            print("FFmpeg not found. Audio will not be added.")
            return video_path
        except Exception as e:
            print(f"Error adding audio: {e}")
            return video_path

    def preview_frame(self,
                      index: int = 0,
                      max_size: Tuple[int, int] = (800, 600)) -> Image.Image:
        """
        Get a preview of a specific frame.

        Args:
            index: Frame index
            max_size: Maximum preview dimensions

        Returns:
            PIL Image for preview
        """
        if not self.frames or index >= len(self.frames):
            raise IndexError("Frame index out of range")

        frame = self.frames[index]

        # Scale down for preview
        scale = min(max_size[0] / frame.width, max_size[1] / frame.height, 1.0)
        if scale < 1.0:
            new_size = (int(frame.width * scale), int(frame.height * scale))
            frame = frame.resize(new_size, Image.Resampling.LANCZOS)

        return frame

    def get_info(self) -> dict:
        """
        Get information about the assembled video.

        Returns:
            Dict with frame count, dimensions, duration, etc.
        """
        if not self.frames:
            return {'frame_count': 0}

        first_frame = self.frames[0]

        if self.settings.frame_duration:
            duration = len(self.frames) * self.settings.frame_duration
        else:
            duration = len(self.frames) / self.settings.fps

        return {
            'frame_count': len(self.frames),
            'width': first_frame.width,
            'height': first_frame.height,
            'fps': self.settings.fps,
            'duration': duration,
            'duration_formatted': self._format_duration(duration)
        }

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to MM:SS.ms format."""
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes:02d}:{secs:05.2f}"
