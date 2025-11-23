import cv2
import numpy as np
from PIL import Image
import os


class VideoProcessor:
    def __init__(self, video_path):
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        self.video_path = video_path
        self.cap = cv2.VideoCapture(video_path)

        if not self.cap.isOpened():
            raise ValueError(f"Could not open video file: {video_path}")

        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.frame_count / self.fps if self.fps > 0 else 0
        self.aspect_ratio = self.width / self.height if self.height > 0 else 0

    def get_metadata(self):
        return {
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "frame_count": self.frame_count,
            "duration": self.duration,
            "aspect_ratio": self.aspect_ratio
        }

    def extract_frames(self, interval_seconds=None, num_frames=None):
        """
        Extract frames from the video.

        Args:
            interval_seconds (float): Extract one frame every X seconds.
            num_frames (int): Extract a specific total number of frames evenly spaced.

        Returns:
            list: List of PIL Image objects.
        """
        frames = []
        indices = []

        if num_frames:
            if num_frames <= 0:
                return []
            # Use linspace to get evenly spaced indices
            indices = np.linspace(0, self.frame_count -
                                  1, num_frames, dtype=int)
            # Remove duplicates and sort
            indices = sorted(list(set(indices)))
        elif interval_seconds:
            step_frames = int(interval_seconds * self.fps)
            if step_frames < 1:
                step_frames = 1
            indices = range(0, self.frame_count, step_frames)
        else:
            # Default: extract every second (approx)
            step_frames = int(self.fps) if self.fps > 0 else 30
            indices = range(0, self.frame_count, step_frames)

        for frame_idx in indices:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = self.cap.read()
            if ret:
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Convert to PIL Image
                pil_image = Image.fromarray(frame_rgb)
                frames.append(pil_image)

        return frames

    def close(self):
        self.cap.release()

    def __del__(self):
        if hasattr(self, 'cap') and self.cap.isOpened():
            self.cap.release()
