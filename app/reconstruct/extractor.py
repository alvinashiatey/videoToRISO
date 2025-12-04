"""
Frame Extraction Module

Extracts individual frames from detected grid cells in scanned
contact sheets, with optional perspective correction and
RISO aesthetic preservation.
"""

import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from typing import List, Optional, Tuple
from .grid_detect import DetectedGrid, GridCell


class FrameExtractor:
    """
    Extract individual frames from a scanned contact sheet grid.

    Handles perspective correction, border removal, and optional
    enhancement to counteract print degradation while preserving
    RISO characteristics.
    """

    def __init__(self,
                 border_crop: int = 0,
                 sharpen: bool = False,
                 preserve_riso_colors: bool = True):
        """
        Initialize the frame extractor.

        Args:
            border_crop: Pixels to crop from each edge of extracted frames
            sharpen: Apply slight sharpening to counteract print softening
            preserve_riso_colors: Avoid aggressive color correction
        """
        self.border_crop = border_crop
        self.sharpen = sharpen
        self.preserve_riso_colors = preserve_riso_colors
        self._perspective_matrix = None
        self._corrected_image = None

    def extract_frames(self,
                       image: Image.Image,
                       grid: DetectedGrid,
                       perspective_corners: Optional[List[Tuple[int, int]]] = None
                       ) -> List[Image.Image]:
        """
        Extract all frames from a scanned image using detected grid.

        Args:
            image: PIL Image of scanned contact sheet
            grid: DetectedGrid with cell information
            perspective_corners: Optional corner points for perspective correction

        Returns:
            List of PIL Images (extracted frames) in reading order
        """
        # Apply perspective correction if corners provided
        if perspective_corners:
            image = self._correct_perspective(image, perspective_corners, grid)

        frames = []
        cells_ordered = grid.get_cells_in_order()

        for cell in cells_ordered:
            frame = self._extract_cell(image, cell)

            # Apply post-processing
            frame = self._post_process(frame)

            frames.append(frame)

        return frames

    def extract_single_frame(self,
                             image: Image.Image,
                             cell: GridCell) -> Image.Image:
        """
        Extract a single frame from a specific grid cell.

        Args:
            image: PIL Image of scanned contact sheet
            cell: GridCell specifying the location

        Returns:
            Extracted PIL Image
        """
        frame = self._extract_cell(image, cell)
        return self._post_process(frame)

    def _extract_cell(self,
                      image: Image.Image,
                      cell: GridCell) -> Image.Image:
        """
        Crop a single cell from the image.

        Args:
            image: Source image
            cell: GridCell with bounds

        Returns:
            Cropped PIL Image
        """
        left, top, right, bottom = cell.bounds

        # Apply border crop
        if self.border_crop > 0:
            left += self.border_crop
            top += self.border_crop
            right -= self.border_crop
            bottom -= self.border_crop

        # Ensure bounds are valid
        left = max(0, left)
        top = max(0, top)
        right = min(image.width, right)
        bottom = min(image.height, bottom)

        # Validate that we have a valid crop region
        if right <= left:
            right = left + 1
        if bottom <= top:
            bottom = top + 1

        # Final safety check - ensure we're within image bounds
        if left >= image.width or top >= image.height:
            # Return a small placeholder image
            return Image.new('RGB', (10, 10), color=(128, 128, 128))

        return image.crop((left, top, right, bottom))

    def _correct_perspective(self,
                             image: Image.Image,
                             corners: List[Tuple[int, int]],
                             grid: DetectedGrid) -> Image.Image:
        """
        Apply perspective correction to the image.

        Args:
            image: Source image
            corners: Four corner points (TL, TR, BR, BL)
            grid: DetectedGrid for target dimensions

        Returns:
            Perspective-corrected PIL Image
        """
        cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

        # Source points
        src_points = np.float32(corners)

        # Calculate target dimensions from grid
        width = grid.cols * (grid.cell_width + grid.spacing_x) - grid.spacing_x
        height = grid.rows * (grid.cell_height +
                              grid.spacing_y) - grid.spacing_y

        # Add margins
        margin = grid.origin[0] if grid.origin else 0
        width += 2 * margin
        height += 2 * margin

        # Destination points
        dst_points = np.float32([
            [0, 0],
            [width, 0],
            [width, height],
            [0, height]
        ])

        # Compute and apply transform
        matrix = cv2.getPerspectiveTransform(src_points, dst_points)
        corrected = cv2.warpPerspective(
            cv_image, matrix, (int(width), int(height)))

        # Convert back to PIL
        return Image.fromarray(cv2.cvtColor(corrected, cv2.COLOR_BGR2RGB))

    def _post_process(self, frame: Image.Image) -> Image.Image:
        """
        Apply post-processing to extracted frame.

        Args:
            frame: Extracted frame

        Returns:
            Post-processed PIL Image
        """
        result = frame

        # Optional sharpening (counteracts print softening)
        if self.sharpen:
            result = result.filter(ImageFilter.UnsharpMask(
                radius=1,
                percent=50,
                threshold=3
            ))

        # If preserving RISO colors, skip aggressive normalization
        if not self.preserve_riso_colors:
            # Apply subtle contrast enhancement
            enhancer = ImageEnhance.Contrast(result)
            result = enhancer.enhance(1.1)

        return result

    def set_target_size(self,
                        width: int,
                        height: int,
                        maintain_aspect: bool = True) -> None:
        """
        Set target size for extracted frames.

        Args:
            width: Target width in pixels
            height: Target height in pixels
            maintain_aspect: If True, maintain aspect ratio
        """
        self._target_size = (width, height)
        self._maintain_aspect = maintain_aspect

    def resize_frame(self,
                     frame: Image.Image,
                     target_size: Optional[Tuple[int, int]] = None) -> Image.Image:
        """
        Resize a frame to target dimensions.

        Args:
            frame: Source frame
            target_size: (width, height) or None to use preset

        Returns:
            Resized PIL Image
        """
        if target_size is None:
            target_size = getattr(self, '_target_size', None)

        if target_size is None:
            return frame

        target_w, target_h = target_size

        if getattr(self, '_maintain_aspect', True):
            # Calculate scaling factor
            scale = min(target_w / frame.width, target_h / frame.height)
            new_w = int(frame.width * scale)
            new_h = int(frame.height * scale)
        else:
            new_w, new_h = target_w, target_h

        return frame.resize((new_w, new_h), Image.Resampling.LANCZOS)


class RISOColorPreserver:
    """
    Algorithms to analyze and preserve authentic RISO aesthetic
    in reconstructed video frames.
    """

    # Common RISO ink colors (approximate RGB values)
    RISO_COLORS = {
        'black': (0, 0, 0),
        'blue': (0, 120, 191),
        'green': (0, 169, 92),
        'burgundy': (145, 78, 114),
        'medium_blue': (50, 85, 164),
        'bright_red': (241, 80, 96),
        'risofederal_blue': (61, 85, 136),
        'purple': (118, 91, 167),
        'teal': (0, 131, 138),
        'flat_gold': (187, 139, 65),
        'hunter_green': (64, 112, 96),
        'red': (255, 102, 94),
        'brown': (146, 95, 82),
        'yellow': (255, 232, 0),
        'marine_red': (210, 81, 94),
        'orange': (255, 108, 47),
        'fluorescent_pink': (255, 72, 176),
        'light_gray': (136, 137, 138),
        'metallic_gold': (172, 147, 110),
        'crimson': (228, 93, 80),
        'fluorescent_orange': (255, 116, 119),
        'cornflower': (98, 168, 229),
        'sky_blue': (73, 130, 207),
        'sea_blue': (0, 116, 162),
        'lake': (35, 91, 168),
        'indigo': (67, 80, 96),
        'midnight': (67, 80, 96),
        'mist': (213, 228, 192),
        'granite': (165, 170, 168),
        'charcoal': (112, 116, 124),
        'smoky_teal': (95, 130, 137),
        'steel': (55, 94, 119),
        'slate': (94, 105, 94),
        'turquoise': (0, 170, 147),
        'emerald': (25, 151, 93),
        'grass': (57, 126, 88),
        'forest': (81, 110, 90),
        'spruce': (74, 99, 93),
        'moss': (104, 114, 77),
        'seafoam': (98, 194, 177),
        'kelly_green': (103, 179, 70),
        'light_teal': (0, 157, 165),
        'ivy': (22, 155, 98),
        'pine': (35, 126, 116),
        'lagoon': (47, 97, 101),
        'violet': (157, 122, 210),
        'orchid': (170, 96, 191),
        'plum': (132, 89, 145),
        'raisin': (119, 93, 122),
        'grape': (108, 93, 128),
        'scarlet': (246, 80, 88),
        'tomato': (210, 81, 94),
        'cranberry': (209, 81, 122),
        'maroon': (158, 76, 110),
        'raspberry_red': (209, 81, 122),
        'brick': (167, 81, 84),
        'light_lime': (227, 237, 85),
        'sunflower': (255, 181, 17),
        'melon': (255, 174, 59),
        'apricot': (246, 160, 77),
        'paprika': (238, 127, 75),
        'pumpkin': (255, 111, 76),
        'bright_olive_green': (180, 159, 41),
        'bright_gold': (186, 128, 50),
        'copper': (189, 100, 57),
        'mahogany': (142, 89, 90),
        'bisque': (242, 205, 207),
        'bubble_gum': (249, 132, 202),
        'light_mauve': (230, 181, 201),
        'dark_mauve': (189, 140, 166),
        'wine': (145, 78, 114),
        'gray': (146, 141, 136),
        'coral': (255, 142, 145),
        'white': (255, 255, 255),
        'aqua': (94, 200, 229),
        'mint': (130, 216, 213),
        'fluorescent_yellow': (255, 233, 22),
        'fluorescent_red': (255, 76, 101),
        'fluorescent_green': (68, 214, 44),
    }

    def __init__(self):
        self.detected_colors = []

    def analyze_ink_colors(self,
                           frames: List[Image.Image],
                           sample_count: int = 5) -> List[str]:
        """
        Detect which RISO ink colors were likely used.

        Args:
            frames: List of extracted frames
            sample_count: Number of frames to sample

        Returns:
            List of detected RISO color names
        """
        # Sample frames evenly
        step = max(1, len(frames) // sample_count)
        samples = [frames[i]
                   for i in range(0, len(frames), step)][:sample_count]

        # Collect dominant colors
        all_colors = []
        for frame in samples:
            colors = self._extract_dominant_colors(frame)
            all_colors.extend(colors)

        # Match to RISO colors
        matched = set()
        for color in all_colors:
            match = self._match_riso_color(color)
            if match:
                matched.add(match)

        self.detected_colors = list(matched)
        return self.detected_colors

    def _extract_dominant_colors(self,
                                 image: Image.Image,
                                 num_colors: int = 5) -> List[Tuple[int, int, int]]:
        """Extract dominant colors from an image."""
        # Resize for faster processing
        small = image.resize((100, 100), Image.Resampling.NEAREST)

        if small.mode != 'RGB':
            small = small.convert('RGB')

        # Get colors and counts
        colors = small.getcolors(maxcolors=10000)
        if not colors:
            return []

        # Sort by frequency
        colors.sort(key=lambda x: x[0], reverse=True)

        # Return top colors (excluding very light/dark)
        result = []
        for count, color in colors[:num_colors * 2]:
            # Skip near-white and near-black
            if all(c > 240 for c in color) or all(c < 15 for c in color):
                continue
            result.append(color)
            if len(result) >= num_colors:
                break

        return result

    def _match_riso_color(self,
                          color: Tuple[int, int, int],
                          threshold: float = 50) -> Optional[str]:
        """
        Match a color to the closest RISO ink color.

        Args:
            color: RGB tuple
            threshold: Maximum distance for a match

        Returns:
            RISO color name or None
        """
        min_dist = float('inf')
        best_match = None

        for name, riso_color in self.RISO_COLORS.items():
            dist = np.sqrt(sum((c1 - c2) ** 2 for c1,
                           c2 in zip(color, riso_color)))
            if dist < min_dist:
                min_dist = dist
                best_match = name

        return best_match if min_dist < threshold else None

    def enhance_riso_characteristics(self,
                                     frame: Image.Image,
                                     saturation_boost: float = 1.1,
                                     add_grain: bool = False,
                                     grain_amount: float = 0.02) -> Image.Image:
        """
        Optionally enhance RISO aesthetic characteristics.

        Args:
            frame: Input frame
            saturation_boost: Saturation multiplier (1.0 = no change)
            add_grain: Whether to add film grain
            grain_amount: Grain intensity (0-1)

        Returns:
            Enhanced PIL Image
        """
        result = frame

        # Boost saturation slightly (RISO inks are vibrant)
        if saturation_boost != 1.0:
            enhancer = ImageEnhance.Color(result)
            result = enhancer.enhance(saturation_boost)

        # Add subtle grain if requested
        if add_grain:
            result = self._add_grain(result, grain_amount)

        return result

    def _add_grain(self,
                   image: Image.Image,
                   amount: float = 0.02) -> Image.Image:
        """Add film grain to an image."""
        arr = np.array(image, dtype=np.float32)

        # Generate noise
        noise = np.random.randn(*arr.shape) * 255 * amount

        # Add noise
        arr = arr + noise
        arr = np.clip(arr, 0, 255).astype(np.uint8)

        return Image.fromarray(arr)
