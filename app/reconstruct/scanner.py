"""
Scan Preprocessing Module

Handles loading and preprocessing of scanned RISO contact sheets,
including auto-rotation, cropping, and color normalization.
Also supports QR code metadata detection for automatic settings extraction.
"""

import os
from PIL import Image, ImageOps, ExifTags
import numpy as np
from typing import List, Optional, Union, Tuple, Dict, Any

from .metadata import MetadataDecoder, SheetMetadata


class ScanProcessor:
    """
    Load and preprocess scanned images of printed RISO contact sheets.

    Supports:
    - Single image files (PNG, TIFF, JPG)
    - Multi-page PDF (requires pdf2image)
    - Folder of scanned pages
    """

    SUPPORTED_EXTENSIONS = {'.png', '.jpg',
                            '.jpeg', '.tiff', '.tif', '.bmp', '.pdf'}

    def __init__(self, scan_path: str):
        """
        Initialize the scan processor.

        Args:
            scan_path: Path to scan file, PDF, or folder of scans
        """
        self.scan_path = scan_path
        self.images: List[Image.Image] = []
        self.filenames: List[str] = []
        # QR metadata per page
        self.metadata: List[Optional[SheetMetadata]] = []
        self._metadata_decoder = MetadataDecoder()

        self._load_scans()

    def _load_scans(self):
        """Load scans from the provided path."""
        if os.path.isdir(self.scan_path):
            self._load_from_folder()
        elif os.path.isfile(self.scan_path):
            ext = os.path.splitext(self.scan_path)[1].lower()
            if ext == '.pdf':
                self._load_from_pdf()
            elif ext in self.SUPPORTED_EXTENSIONS:
                self._load_single_image()
            else:
                raise ValueError(f"Unsupported file type: {ext}")
        else:
            raise FileNotFoundError(f"Path not found: {self.scan_path}")

    def _load_single_image(self):
        """Load a single image file."""
        img = Image.open(self.scan_path)
        self.images.append(img)
        self.filenames.append(os.path.basename(self.scan_path))
        # Try to detect QR metadata
        self.metadata.append(self._detect_qr_metadata(img))

    def _load_from_folder(self):
        """Load all supported images from a folder."""
        files = sorted(os.listdir(self.scan_path))
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in self.SUPPORTED_EXTENSIONS and ext != '.pdf':
                filepath = os.path.join(self.scan_path, filename)
                try:
                    img = Image.open(filepath)
                    self.images.append(img)
                    self.filenames.append(filename)
                    # Try to detect QR metadata
                    self.metadata.append(self._detect_qr_metadata(img))
                except Exception as e:
                    print(f"Warning: Could not load {filename}: {e}")

    def _load_from_pdf(self):
        """Load pages from a PDF file."""
        try:
            from pdf2image import convert_from_path
            pages = convert_from_path(self.scan_path, dpi=300)
            for i, page in enumerate(pages):
                self.images.append(page)
                self.filenames.append(f"page_{i+1}.png")
                # Try to detect QR metadata
                self.metadata.append(self._detect_qr_metadata(page))
        except ImportError:
            raise ImportError(
                "pdf2image is required for PDF support. "
                "Install with: pip install pdf2image"
            )

    def _detect_qr_metadata(self, image: Image.Image) -> Optional[SheetMetadata]:
        """
        Attempt to detect and decode QR metadata from an image.

        Args:
            image: PIL Image to scan for QR codes

        Returns:
            SheetMetadata if QR code found and decoded, None otherwise
        """
        try:
            return self._metadata_decoder.decode_qr(image)
        except Exception as e:
            print(f"Warning: Could not decode QR metadata: {e}")
            return None

    def get_detected_metadata(self) -> List[Optional[SheetMetadata]]:
        """
        Return the list of detected metadata for each loaded image.

        Returns:
            List of SheetMetadata objects (or None for pages without QR)
        """
        return self.metadata

    def get_combined_settings(self) -> Optional[Dict[str, Any]]:
        """
        Extract combined settings from all detected QR metadata.
        Uses the first valid metadata found and validates consistency.

        Returns:
            Dict with extracted settings or None if no metadata found
        """
        valid_metadata = [m for m in self.metadata if m is not None]

        if not valid_metadata:
            return None

        # Use first valid metadata as base
        first = valid_metadata[0]

        settings = {
            'rows': first.rows,
            'cols': first.cols,
            'fps': first.fps,
            'total_pages': first.total_pages,
            'original_resolution': first.original_resolution,
            'video_hash': first.video_hash,
        }

        # Sort metadata by page number for proper frame ordering
        sorted_metadata = sorted(
            [m for m in valid_metadata if m.page_number is not None],
            key=lambda m: m.page_number
        )

        if sorted_metadata:
            # Calculate total expected frames
            total_frames = sum(m.frame_count for m in sorted_metadata)
            settings['total_frames'] = total_frames
            settings['page_order'] = [m.page_number for m in sorted_metadata]

        return settings

    def has_metadata(self) -> bool:
        """Check if any QR metadata was detected."""
        return any(m is not None for m in self.metadata)

    @staticmethod
    def load_folder(folder_path: str) -> List[Image.Image]:
        """
        Convenience method to load all scans from a folder.

        Args:
            folder_path: Path to folder containing scanned images

        Returns:
            List of preprocessed PIL Images
        """
        processor = ScanProcessor(folder_path)
        return processor.get_preprocessed_images()

    def get_images(self) -> List[Image.Image]:
        """Return the raw loaded images."""
        return self.images

    def get_preprocessed_images(self,
                                auto_rotate: bool = True,
                                auto_crop: bool = True,
                                normalize_white: bool = False) -> List[Image.Image]:
        """
        Return preprocessed versions of all loaded images.

        Args:
            auto_rotate: Auto-rotate based on EXIF or content
            auto_crop: Crop to paper bounds
            normalize_white: Normalize white balance

        Returns:
            List of preprocessed PIL Images
        """
        processed = []
        for img in self.images:
            result = self.preprocess(
                img,
                auto_rotate=auto_rotate,
                auto_crop=auto_crop,
                normalize_white=normalize_white
            )
            processed.append(result)
        return processed

    def preprocess(self,
                   image: Image.Image,
                   auto_rotate: bool = True,
                   auto_crop: bool = True,
                   normalize_white: bool = False) -> Image.Image:
        """
        Preprocess a single scanned image.

        Args:
            image: Input PIL Image
            auto_rotate: Rotate based on EXIF or content analysis
            auto_crop: Crop to paper bounds
            normalize_white: Normalize white balance (careful: may affect RISO colors)

        Returns:
            Preprocessed PIL Image
        """
        result = image.copy()

        # Step 1: Auto-rotate based on EXIF
        if auto_rotate:
            result = self._apply_exif_rotation(result)

        # Step 2: Crop scanner artifacts (black borders, etc.)
        if auto_crop:
            result = self._auto_crop(result)

        # Step 3: Normalize white balance (optional)
        if normalize_white:
            result = self._normalize_white_balance(result)

        return result

    def _apply_exif_rotation(self, image: Image.Image) -> Image.Image:
        """Apply rotation based on EXIF orientation tag."""
        try:
            exif = image._getexif()
            if exif:
                for tag, value in exif.items():
                    if ExifTags.TAGS.get(tag) == 'Orientation':
                        if value == 3:
                            return image.rotate(180, expand=True)
                        elif value == 6:
                            return image.rotate(270, expand=True)
                        elif value == 8:
                            return image.rotate(90, expand=True)
        except (AttributeError, KeyError, TypeError):
            pass
        return image

    def _auto_crop(self, image: Image.Image,
                   threshold: int = 240,
                   margin: int = 10) -> Image.Image:
        """
        Crop out scanner lid artifacts (black borders, shadows).

        Args:
            image: Input image
            threshold: Brightness threshold for detecting paper
            margin: Extra margin to add around detected bounds

        Returns:
            Cropped image
        """
        # Convert to grayscale for analysis
        if image.mode != 'L':
            gray = image.convert('L')
        else:
            gray = image

        # Convert to numpy array
        arr = np.array(gray)

        # Find rows and columns that are mostly bright (paper)
        row_means = np.mean(arr, axis=1)
        col_means = np.mean(arr, axis=0)

        # Find bounds where content starts (paper area)
        # Lower threshold for more aggressive cropping
        content_threshold = threshold * 0.7

        rows_with_content = np.where(row_means < content_threshold)[0]
        cols_with_content = np.where(col_means < content_threshold)[0]

        if len(rows_with_content) == 0 or len(cols_with_content) == 0:
            # No clear content detected, return original
            return image

        # Get bounding box
        top = max(0, rows_with_content[0] - margin)
        bottom = min(arr.shape[0], rows_with_content[-1] + margin)
        left = max(0, cols_with_content[0] - margin)
        right = min(arr.shape[1], cols_with_content[-1] + margin)

        # Only crop if it makes sense (not removing too much)
        original_area = arr.shape[0] * arr.shape[1]
        new_area = (bottom - top) * (right - left)

        if new_area < original_area * 0.5:
            # Would crop too much, skip
            return image

        return image.crop((left, top, right, bottom))

    def _normalize_white_balance(self, image: Image.Image,
                                 percentile: float = 99) -> Image.Image:
        """
        Normalize white balance by stretching histogram.

        Note: Use cautiously as this may alter RISO ink colors.

        Args:
            image: Input image
            percentile: Percentile for white point

        Returns:
            White-balanced image
        """
        if image.mode != 'RGB':
            image = image.convert('RGB')

        arr = np.array(image, dtype=np.float32)

        # Process each channel
        for i in range(3):
            channel = arr[:, :, i]
            low = np.percentile(channel, 100 - percentile)
            high = np.percentile(channel, percentile)

            if high > low:
                channel = (channel - low) / (high - low) * 255
                arr[:, :, i] = np.clip(channel, 0, 255)

        return Image.fromarray(arr.astype(np.uint8))

    def detect_page_order(self) -> List[int]:
        """
        Attempt to detect page ordering from filenames.

        Returns:
            List of indices representing the correct order
        """
        import re

        # Try to extract numbers from filenames
        order = []
        for i, filename in enumerate(self.filenames):
            # Look for patterns like "001", "page_1", "scan1", etc.
            numbers = re.findall(r'\d+', filename)
            if numbers:
                # Use the last number found (often the page number)
                order.append((int(numbers[-1]), i))
            else:
                order.append((i, i))

        # Sort by extracted number
        order.sort(key=lambda x: x[0])

        return [idx for _, idx in order]

    def get_ordered_images(self) -> List[Image.Image]:
        """
        Return images in detected page order.

        Returns:
            List of PIL Images in page order
        """
        order = self.detect_page_order()
        return [self.images[i] for i in order]
