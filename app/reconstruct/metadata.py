"""
Metadata Encoding/Decoding Module

Provides tools for encoding metadata (page numbers, grid info, etc.)
into contact sheets via QR codes, and decoding them from scans.
"""

import json
import hashlib
from PIL import Image, ImageDraw
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass, asdict
import base64


@dataclass
class SheetMetadata:
    """Metadata structure for a contact sheet."""
    page_number: int
    total_pages: int
    rows: int
    cols: int
    frame_start: int  # First frame index on this page
    frame_count: int  # Number of frames on this page
    fps: Optional[float] = None
    # Cell layout info for precise grid reconstruction
    cell_width: Optional[int] = None
    cell_height: Optional[int] = None
    margin: Optional[int] = None  # Margin from edge in pixels
    spacing: Optional[int] = None  # Spacing between cells in pixels
    video_hash: Optional[str] = None
    original_resolution: Optional[Tuple[int, int]] = None
    created_at: Optional[str] = None

    def to_json(self) -> str:
        """Convert to JSON string."""
        data = asdict(self)
        return json.dumps(data, separators=(',', ':'))

    @classmethod
    def from_json(cls, json_str: str) -> 'SheetMetadata':
        """Create from JSON string."""
        data = json.loads(json_str)
        return cls(**data)

    def to_compact(self) -> str:
        """
        Convert to a compact string format for small QR codes.
        Format: p{page}/{total}|g{rows}x{cols}|f{start}+{count}|c{w}x{h}|m{margin}s{spacing}|@{fps}
        """
        parts = [
            f"p{self.page_number}/{self.total_pages}",
            f"g{self.rows}x{self.cols}",
            f"f{self.frame_start}+{self.frame_count}"
        ]
        # Add cell dimensions if available
        if self.cell_width and self.cell_height:
            parts.append(f"c{self.cell_width}x{self.cell_height}")
        # Add margin and spacing if available
        if self.margin is not None and self.spacing is not None:
            parts.append(f"m{self.margin}s{self.spacing}")
        if self.fps:
            parts.append(f"@{self.fps:.1f}")
        return "|".join(parts)

    @classmethod
    def from_compact(cls, compact_str: str) -> 'SheetMetadata':
        """Parse compact string format."""
        parts = compact_str.split("|")

        # Parse page info: p1/5
        page_part = parts[0]
        page_num, total = page_part[1:].split("/")

        # Parse grid: g4x6
        grid_part = parts[1]
        rows, cols = grid_part[1:].split("x")

        # Parse frames: f0+24
        frame_part = parts[2]
        frame_start, frame_count = frame_part[1:].split("+")

        # Parse optional parts
        fps = None
        cell_width = None
        cell_height = None
        margin = None
        spacing = None

        for part in parts[3:]:
            if part.startswith("@"):
                # FPS: @24.0
                fps = float(part[1:])
            elif part.startswith("c"):
                # Cell dimensions: c400x300
                dims = part[1:].split("x")
                cell_width = int(dims[0])
                cell_height = int(dims[1])
            elif part.startswith("m"):
                # Margin and spacing: m150s30
                # Split on 's' to get margin and spacing
                ms_parts = part[1:].split("s")
                margin = int(ms_parts[0])
                spacing = int(ms_parts[1])

        return cls(
            page_number=int(page_num),
            total_pages=int(total),
            rows=int(rows),
            cols=int(cols),
            frame_start=int(frame_start),
            frame_count=int(frame_count),
            fps=fps,
            cell_width=cell_width,
            cell_height=cell_height,
            margin=margin,
            spacing=spacing
        )


class MetadataEncoder:
    """
    Encode metadata into contact sheets via QR codes or other markers.
    """

    def __init__(self,
                 qr_size: int = 100,
                 position: str = "bottom-right",
                 margin: int = 20):
        """
        Initialize the metadata encoder.

        Args:
            qr_size: Size of QR code in pixels
            position: QR code position (top-left, top-right, bottom-left, bottom-right)
            margin: Margin from edge in pixels
        """
        self.qr_size = qr_size
        self.position = position
        self.margin = margin
        self._qr_available = self._check_qr_available()

    def _check_qr_available(self) -> bool:
        """Check if QR code libraries are available."""
        try:
            import qrcode
            return True
        except ImportError:
            return False

    def add_qr_code(self,
                    image: Image.Image,
                    metadata: SheetMetadata,
                    use_compact: bool = True) -> Image.Image:
        """
        Add a QR code with metadata to the image.

        Args:
            image: PIL Image to add QR code to
            metadata: SheetMetadata to encode
            use_compact: Use compact format for smaller QR

        Returns:
            Image with QR code added
        """
        if not self._qr_available:
            print("Warning: qrcode library not available. Skipping QR code.")
            return image

        import qrcode

        # Generate data string
        if use_compact:
            data = metadata.to_compact()
        else:
            data = metadata.to_json()

        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=2
        )
        qr.add_data(data)
        qr.make(fit=True)

        qr_image = qr.make_image(fill_color="black", back_color="white")
        qr_image = qr_image.resize(
            (self.qr_size, self.qr_size), Image.Resampling.NEAREST)

        # Calculate position
        x, y = self._calculate_position(image.size, qr_image.size)

        # Paste QR code
        result = image.copy()
        if result.mode != 'RGB':
            result = result.convert('RGB')

        # Convert QR to RGB if needed
        if qr_image.mode != 'RGB':
            qr_image = qr_image.convert('RGB')

        result.paste(qr_image, (x, y))

        return result

    def add_corner_markers(self,
                           image: Image.Image,
                           marker_size: int = 30) -> Image.Image:
        """
        Add corner registration markers for perspective correction.

        Args:
            image: PIL Image
            marker_size: Size of corner markers

        Returns:
            Image with corner markers
        """
        result = image.copy()
        if result.mode != 'RGB':
            result = result.convert('RGB')

        draw = ImageDraw.Draw(result)
        width, height = result.size

        # Define corner positions
        corners = [
            (0, 0),  # Top-left
            (width - marker_size, 0),  # Top-right
            (width - marker_size, height - marker_size),  # Bottom-right
            (0, height - marker_size)  # Bottom-left
        ]

        # Draw L-shaped markers at each corner
        line_width = max(2, marker_size // 10)

        for cx, cy in corners:
            # Draw filled corner rectangle
            draw.rectangle(
                [cx, cy, cx + marker_size, cy + marker_size],
                fill='black'
            )
            # Add white inner square
            inner_margin = marker_size // 4
            draw.rectangle(
                [cx + inner_margin, cy + inner_margin,
                 cx + marker_size - inner_margin, cy + marker_size - inner_margin],
                fill='white'
            )

        return result

    def add_page_number(self,
                        image: Image.Image,
                        page_number: int,
                        total_pages: int,
                        position: str = "bottom-center") -> Image.Image:
        """
        Add visible page number text to the image.

        Args:
            image: PIL Image
            page_number: Current page number
            total_pages: Total number of pages
            position: Text position

        Returns:
            Image with page number
        """
        result = image.copy()
        if result.mode != 'RGB':
            result = result.convert('RGB')

        draw = ImageDraw.Draw(result)
        text = f"Page {page_number} of {total_pages}"

        # Calculate text size and position
        try:
            from PIL import ImageFont
            font = ImageFont.truetype("Arial", 24)
        except:
            font = ImageFont.load_default()

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        width, height = result.size

        if position == "bottom-center":
            x = (width - text_width) // 2
            y = height - text_height - self.margin
        elif position == "bottom-left":
            x = self.margin
            y = height - text_height - self.margin
        else:  # bottom-right
            x = width - text_width - self.margin
            y = height - text_height - self.margin

        # Draw with background for visibility
        padding = 5
        draw.rectangle(
            [x - padding, y - padding, x + text_width +
                padding, y + text_height + padding],
            fill='white'
        )
        draw.text((x, y), text, fill='black', font=font)

        return result

    def _calculate_position(self,
                            image_size: Tuple[int, int],
                            element_size: Tuple[int, int]) -> Tuple[int, int]:
        """Calculate position for an element based on position setting."""
        img_w, img_h = image_size
        elem_w, elem_h = element_size

        if self.position == "top-left":
            return (self.margin, self.margin)
        elif self.position == "top-right":
            return (img_w - elem_w - self.margin, self.margin)
        elif self.position == "bottom-left":
            return (self.margin, img_h - elem_h - self.margin)
        else:  # bottom-right
            return (img_w - elem_w - self.margin, img_h - elem_h - self.margin)


class MetadataDecoder:
    """
    Decode metadata from scanned contact sheets.
    Uses OpenCV's built-in QR detector (no external dependencies).
    """

    def __init__(self):
        self._cv2_available = self._check_cv2()

    def _check_cv2(self) -> bool:
        """Check if OpenCV is available for QR decoding."""
        try:
            import cv2
            # Check if QRCodeDetector is available (OpenCV 4.0+)
            _ = cv2.QRCodeDetector()
            return True
        except (ImportError, AttributeError):
            return False

    def decode_qr(self, image: Image.Image, debug: bool = True) -> Optional[SheetMetadata]:
        """
        Attempt to decode QR code metadata from an image using OpenCV.

        Args:
            image: Scanned PIL Image
            debug: Print debug information

        Returns:
            SheetMetadata if found, None otherwise
        """
        if not self._cv2_available:
            print("[QR DEBUG] OpenCV QR detector not available")
            return None

        import cv2
        import numpy as np

        if debug:
            print(
                f"[QR DEBUG] Starting QR detection on image: {image.size}, mode: {image.mode}")

        # Convert PIL Image to OpenCV format
        if image.mode != 'RGB':
            image = image.convert('RGB')

        cv_image = np.array(image)
        cv_image = cv2.cvtColor(cv_image, cv2.COLOR_RGB2BGR)

        # Create QR detector
        detector = cv2.QRCodeDetector()

        # First, try scanning specific corner regions where QR code is likely to be
        # QR code is placed in bottom-right corner with margin
        height, width = cv_image.shape[:2]

        # Define corner regions to check (bottom-right, bottom-left, top-right, top-left)
        # Check 1/3 of the image in each corner
        corner_size = min(width, height) // 3
        corners = [
            ("bottom-right", cv_image[height -
             corner_size:, width-corner_size:]),
            ("bottom-left", cv_image[height-corner_size:, :corner_size]),
            ("top-right", cv_image[:corner_size, width-corner_size:]),
            ("top-left", cv_image[:corner_size, :corner_size]),
        ]

        for corner_name, corner_img in corners:
            data, points, _ = detector.detectAndDecode(corner_img)
            if data:
                if debug:
                    print(
                        f"[QR DEBUG] Found QR in {corner_name} corner: '{data}'")
                metadata = self._parse_metadata(data)
                if debug:
                    print(f"[QR DEBUG] Parsed metadata: {metadata}")
                return metadata

            # Try grayscale on corner
            gray_corner = cv2.cvtColor(corner_img, cv2.COLOR_BGR2GRAY)
            data, points, _ = detector.detectAndDecode(gray_corner)
            if data:
                if debug:
                    print(
                        f"[QR DEBUG] Found QR in {corner_name} corner (grayscale): '{data}'")
                metadata = self._parse_metadata(data)
                return metadata

        # Fall back to full image scan with various preprocessing
        if debug:
            print("[QR DEBUG] Corner scan failed, trying full image...")

        # Try decoding directly
        data, points, _ = detector.detectAndDecode(cv_image)
        if debug:
            print(
                f"[QR DEBUG] Direct decode result: '{data}' (points: {points is not None})")

        if not data:
            # Try with grayscale
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            data, points, _ = detector.detectAndDecode(gray)
            if debug:
                print(f"[QR DEBUG] Grayscale decode result: '{data}'")

        if not data:
            # Try with threshold preprocessing
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            _, thresh = cv2.threshold(
                gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            data, points, _ = detector.detectAndDecode(thresh)
            if debug:
                print(f"[QR DEBUG] Otsu threshold decode result: '{data}'")

        if not data:
            # Try with adaptive threshold
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)
            adaptive = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
            )
            data, points, _ = detector.detectAndDecode(adaptive)
            if debug:
                print(f"[QR DEBUG] Adaptive threshold decode result: '{data}'")

        if data:
            if debug:
                print(f"[QR DEBUG] Successfully decoded QR data: '{data}'")
            metadata = self._parse_metadata(data)
            if debug:
                print(f"[QR DEBUG] Parsed metadata: {metadata}")
            return metadata

        if debug:
            print("[QR DEBUG] No QR code found in image")
        return None

    def _parse_metadata(self, data: str) -> Optional[SheetMetadata]:
        """
        Parse metadata from decoded string.

        Args:
            data: Decoded QR code data

        Returns:
            SheetMetadata or None
        """
        try:
            # Try compact format first
            if data.startswith('p') and '|' in data:
                return SheetMetadata.from_compact(data)

            # Try JSON format
            if data.startswith('{'):
                return SheetMetadata.from_json(data)

            return None
        except Exception as e:
            print(f"Error parsing metadata: {e}")
            return None

    def detect_corner_markers(self,
                              image: Image.Image) -> Optional[list]:
        """
        Detect corner registration markers in an image.

        Args:
            image: Scanned PIL Image

        Returns:
            List of 4 corner coordinates or None
        """
        import cv2
        import numpy as np

        # Convert to grayscale
        if image.mode != 'L':
            gray = image.convert('L')
        else:
            gray = image

        cv_image = np.array(gray)

        # Threshold to find dark markers
        _, binary = cv2.threshold(cv_image, 50, 255, cv2.THRESH_BINARY_INV)

        # Find contours
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Filter to find square-ish markers in corners
        candidates = []
        img_h, img_w = cv_image.shape

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect = w / h if h > 0 else 0

            # Should be roughly square
            if 0.8 < aspect < 1.2:
                # Should be in a corner region
                in_corner = (
                    (x < img_w * 0.15 or x > img_w * 0.85) and
                    (y < img_h * 0.15 or y > img_h * 0.85)
                )
                if in_corner:
                    center_x = x + w // 2
                    center_y = y + h // 2
                    candidates.append((center_x, center_y))

        if len(candidates) >= 4:
            # Sort to get corners in order: TL, TR, BR, BL
            # First sort by y to get top/bottom
            candidates.sort(key=lambda p: p[1])
            top = sorted(candidates[:2], key=lambda p: p[0])
            bottom = sorted(candidates[-2:], key=lambda p: p[0])

            return [top[0], top[1], bottom[1], bottom[0]]

        return None

    def scan_for_all_metadata(self,
                              image: Image.Image) -> Dict[str, Any]:
        """
        Attempt to extract all available metadata from a scan.

        Args:
            image: Scanned PIL Image

        Returns:
            Dict with all found metadata
        """
        result = {
            'qr_metadata': None,
            'corner_markers': None,
            'detected_grid': None
        }

        # Try QR code
        result['qr_metadata'] = self.decode_qr(image)

        # Try corner markers
        result['corner_markers'] = self.detect_corner_markers(image)

        return result


def generate_video_hash(video_path: str) -> str:
    """
    Generate a short hash to identify the source video.

    Args:
        video_path: Path to video file

    Returns:
        Short hash string
    """
    with open(video_path, 'rb') as f:
        # Read first and last 64KB for speed
        data = f.read(65536)
        f.seek(-65536, 2)
        data += f.read()

    full_hash = hashlib.sha256(data).hexdigest()
    return full_hash[:12]  # Short hash for QR compactness
