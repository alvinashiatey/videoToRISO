"""
Grid Detection Module

Detects thumbnail grid boundaries in scanned RISO contact sheets.
Primary method uses QR metadata for reliable grid calculation.
Fallback uses edge detection and content analysis.
"""

import cv2
import numpy as np
from PIL import Image
from typing import List, Tuple, Optional, Dict
from dataclasses import dataclass


@dataclass
class GridCell:
    """Represents a single cell in the detected grid."""
    x: int
    y: int
    width: int
    height: int
    row: int
    col: int

    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        """Return (left, top, right, bottom) bounds."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    @property
    def center(self) -> Tuple[int, int]:
        """Return center point of the cell."""
        return (self.x + self.width // 2, self.y + self.height // 2)


@dataclass
class DetectedGrid:
    """Represents a detected grid with all its cells."""
    cells: List[GridCell]
    rows: int
    cols: int
    cell_width: int
    cell_height: int
    origin: Tuple[int, int]  # Top-left corner of grid
    spacing_x: int
    spacing_y: int
    # Actual number of frames (from QR metadata)
    frame_count: Optional[int] = None

    def get_cell(self, row: int, col: int) -> Optional[GridCell]:
        """Get a specific cell by row and column."""
        for cell in self.cells:
            if cell.row == row and cell.col == col:
                return cell
        return None

    def get_cells_in_order(self) -> List[GridCell]:
        """Return cells in reading order (left-to-right, top-to-bottom)."""
        ordered = sorted(self.cells, key=lambda c: (c.row, c.col))
        # If we know the actual frame count, limit to that
        if self.frame_count is not None:
            return ordered[:self.frame_count]
        return ordered


class GridDetector:
    """
    Detect thumbnail grids in scanned contact sheet images.

    Primary method: Use QR metadata for precise grid calculation
    Fallback methods: Content-based detection
    """

    def __init__(self,
                 min_cell_size: int = 50,
                 max_cell_size: int = 2000):
        """
        Initialize the grid detector.

        Args:
            min_cell_size: Minimum cell dimension in pixels
            max_cell_size: Maximum cell dimension in pixels
        """
        self.min_cell_size = min_cell_size
        self.max_cell_size = max_cell_size

    @staticmethod
    def detect(image: Image.Image,
               method: str = "auto",
               rows: Optional[int] = None,
               cols: Optional[int] = None,
               frame_count: Optional[int] = None,
               cell_width: Optional[int] = None,
               cell_height: Optional[int] = None,
               margin: Optional[int] = None,
               spacing: Optional[int] = None,
               margin_percent: float = 0.045,
               spacing_percent: float = 0.012) -> 'DetectedGrid':
        """
        Detect grid in an image.

        Args:
            image: PIL Image of scanned contact sheet
            method: Detection method ("auto", "manual")
            rows: Number of rows (for manual mode)
            cols: Number of columns (for manual mode)
            frame_count: Actual number of frames (to avoid including QR as frame)
            cell_width: Exact cell width in pixels (from QR metadata)
            cell_height: Exact cell height in pixels (from QR metadata)
            margin: Exact margin in pixels (from QR metadata)
            spacing: Exact spacing in pixels (from QR metadata)
            margin_percent: Fallback margin as percentage of page size
            spacing_percent: Fallback spacing as percentage of page size

        Returns:
            DetectedGrid object with cell information
        """
        detector = GridDetector()

        if method == "manual" and rows and cols:
            # If we have exact cell dimensions from QR, use them directly
            if cell_width and cell_height and margin is not None and spacing is not None:
                return detector.detect_from_exact_layout(
                    image, rows, cols, frame_count,
                    cell_width, cell_height, margin, spacing
                )
            else:
                return detector.detect_from_metadata(
                    image, rows, cols, frame_count, margin_percent, spacing_percent
                )
        else:
            return detector.detect_by_content(image)

    def detect_from_metadata(self,
                             image: Image.Image,
                             rows: int,
                             cols: int,
                             frame_count: Optional[int] = None,
                             margin_percent: float = 0.045,
                             spacing_percent: float = 0.012) -> 'DetectedGrid':
        """
        Create grid based on known rows/cols (from QR metadata).
        Calculates cell positions using standard layout parameters.
        This is the FALLBACK when exact cell dimensions are not available.

        Args:
            image: PIL Image
            rows: Number of rows in grid
            cols: Number of columns in grid
            frame_count: Actual number of frames (avoids including QR)
            margin_percent: Margin as percentage of page dimension
            spacing_percent: Spacing between cells as percentage

        Returns:
            DetectedGrid with calculated cells
        """
        width, height = image.size

        # Calculate margins and spacing based on image size
        # These match the LayoutEngine defaults (~0.5 inch margin, ~0.1 inch spacing at 300dpi)
        margin_x = int(width * margin_percent)
        margin_y = int(height * margin_percent)

        # First, find the content bounds by detecting where thumbnails actually are
        content_bounds = self._detect_content_bounds(image)
        if content_bounds:
            margin_x = content_bounds[0]
            margin_y = content_bounds[1]
            content_width = content_bounds[2] - content_bounds[0]
            content_height = content_bounds[3] - content_bounds[1]
        else:
            content_width = width - (2 * margin_x)
            content_height = height - (2 * margin_y)

        # Calculate spacing
        spacing_x = int(width * spacing_percent)
        spacing_y = int(height * spacing_percent)

        # Calculate cell dimensions
        # cell_width * cols + spacing * (cols-1) = content_width
        cell_width = (content_width - spacing_x * (cols - 1)) // cols
        cell_height = (content_height - spacing_y * (rows - 1)) // rows

        cells = []
        for row in range(rows):
            for col in range(cols):
                x = margin_x + col * (cell_width + spacing_x)
                y = margin_y + row * (cell_height + spacing_y)

                cells.append(GridCell(
                    x=x, y=y,
                    width=cell_width, height=cell_height,
                    row=row, col=col
                ))

        initial_grid = DetectedGrid(
            cells=cells,
            rows=rows,
            cols=cols,
            cell_width=cell_width,
            cell_height=cell_height,
            origin=(margin_x, margin_y),
            spacing_x=spacing_x,
            spacing_y=spacing_y,
            frame_count=frame_count
        )

        return self.refine_grid_with_contours(image, initial_grid)

    def detect_from_exact_layout(self,
                                 image: Image.Image,
                                 rows: int,
                                 cols: int,
                                 frame_count: Optional[int],
                                 cell_width: int,
                                 cell_height: int,
                                 margin: int,
                                 spacing: int) -> 'DetectedGrid':
        """
        Create grid using EXACT layout values from QR metadata.
        This is the most reliable method - no guessing required.

        The scanned image may be at a different resolution than the original,
        so we scale the layout values proportionally.

        Args:
            image: PIL Image (scanned)
            rows: Number of rows in grid
            cols: Number of columns in grid
            frame_count: Actual number of frames
            cell_width: Original cell width in pixels
            cell_height: Original cell height in pixels
            margin: Original margin in pixels
            spacing: Original spacing in pixels

        Returns:
            DetectedGrid with precisely calculated cells
        """
        img_width, img_height = image.size

        # Calculate the original page dimensions from the layout values
        # Original width = margin * 2 + cols * cell_width + (cols - 1) * spacing
        original_width = margin * 2 + cols * cell_width + (cols - 1) * spacing
        original_height = margin * 2 + rows * \
            cell_height + (rows - 1) * spacing

        # Calculate scale factors (scanned image may be different size)
        scale_x = img_width / original_width
        scale_y = img_height / original_height

        # Use the average scale if aspect ratio is preserved, otherwise use individual scales
        # This handles slight scanning distortions
        if abs(scale_x - scale_y) < 0.1:  # Less than 10% difference
            scale = (scale_x + scale_y) / 2
            scale_x = scale_y = scale

        # Scale all layout values
        scaled_margin_x = int(margin * scale_x)
        scaled_margin_y = int(margin * scale_y)
        scaled_cell_width = int(cell_width * scale_x)
        scaled_cell_height = int(cell_height * scale_y)
        scaled_spacing_x = int(spacing * scale_x)
        scaled_spacing_y = int(spacing * scale_y)

        print(f"[GridDetect] Exact layout: scale={scale_x:.3f}x{scale_y:.3f}, "
              f"cell={scaled_cell_width}x{scaled_cell_height}, "
              f"margin={scaled_margin_x}, spacing={scaled_spacing_x}")

        cells = []
        for row in range(rows):
            for col in range(cols):
                x = scaled_margin_x + col * \
                    (scaled_cell_width + scaled_spacing_x)
                y = scaled_margin_y + row * \
                    (scaled_cell_height + scaled_spacing_y)

                cells.append(GridCell(
                    x=x, y=y,
                    width=scaled_cell_width, height=scaled_cell_height,
                    row=row, col=col
                ))

        initial_grid = DetectedGrid(
            cells=cells,
            rows=rows,
            cols=cols,
            cell_width=scaled_cell_width,
            cell_height=scaled_cell_height,
            origin=(scaled_margin_x, scaled_margin_y),
            spacing_x=scaled_spacing_x,
            spacing_y=scaled_spacing_y,
            frame_count=frame_count
        )

        # Refine the grid by snapping to actual content contours
        return self.refine_grid_with_contours(image, initial_grid)

    def refine_grid_with_contours(self, image: Image.Image, grid: 'DetectedGrid') -> 'DetectedGrid':
        """
        Refine the detected grid by snapping cells to actual content contours.
        This improves cropping accuracy by adapting to slight misalignments.
        """
        try:
            cv_image = self._pil_to_cv(image)
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

            # Adaptive threshold to find content
            binary = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 25, 10
            )

            # Clean up noise
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            cleaned = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

            contours, _ = cv2.findContours(
                cleaned, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            refined_cells = []

            for cell in grid.cells:
                # Define search window (expand cell slightly)
                pad_x = int(cell.width * 0.2)
                pad_y = int(cell.height * 0.2)

                search_x = max(0, cell.x - pad_x)
                search_y = max(0, cell.y - pad_y)
                search_w = cell.width + 2 * pad_x
                search_h = cell.height + 2 * pad_y

                best_contour = None
                max_overlap = 0

                cell_area = cell.width * cell.height

                for cnt in contours:
                    x, y, w, h = cv2.boundingRect(cnt)

                    # Check if contour center is roughly in the search window
                    cx = x + w // 2
                    cy = y + h // 2

                    if (cx >= search_x and cy >= search_y and
                        cx <= search_x + search_w and
                            cy <= search_y + search_h):

                        # Check size similarity (allow some variation)
                        area = w * h
                        if 0.5 * cell_area < area < 1.5 * cell_area:
                            # Calculate overlap with original cell
                            overlap_x = max(
                                0, min(cell.x + cell.width, x + w) - max(cell.x, x))
                            overlap_y = max(
                                0, min(cell.y + cell.height, y + h) - max(cell.y, y))
                            overlap_area = overlap_x * overlap_y

                            if overlap_area > max_overlap:
                                max_overlap = overlap_area
                                best_contour = (x, y, w, h)

                if best_contour:
                    # Use the found contour
                    bx, by, bw, bh = best_contour
                    refined_cells.append(GridCell(
                        x=bx, y=by, width=bw, height=bh,
                        row=cell.row, col=cell.col
                    ))
                else:
                    # Keep original if no good match found
                    refined_cells.append(cell)

            # Return new grid with refined cells
            return DetectedGrid(
                cells=refined_cells,
                rows=grid.rows,
                cols=grid.cols,
                cell_width=grid.cell_width,
                cell_height=grid.cell_height,
                origin=grid.origin,
                spacing_x=grid.spacing_x,
                spacing_y=grid.spacing_y,
                frame_count=grid.frame_count
            )
        except Exception as e:
            print(f"[GridDetect] Refinement failed: {e}")
            return grid

    def _detect_content_bounds(self, image: Image.Image) -> Optional[Tuple[int, int, int, int]]:
        """
        Detect where the actual content (thumbnails) starts and ends.

        Returns:
            (left, top, right, bottom) bounds or None
        """
        try:
            cv_image = self._pil_to_cv(image)
            gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

            # Threshold to find content
            _, binary = cv2.threshold(gray, 250, 255, cv2.THRESH_BINARY_INV)

            # Find rows and columns with content
            row_sums = np.sum(binary, axis=1)
            col_sums = np.sum(binary, axis=0)

            # Find first and last rows/cols with significant content
            threshold = binary.shape[1] * 10  # At least 10 pixels of content

            rows_with_content = np.where(row_sums > threshold)[0]
            cols_with_content = np.where(col_sums > threshold)[0]

            if len(rows_with_content) == 0 or len(cols_with_content) == 0:
                return None

            top = rows_with_content[0]
            bottom = rows_with_content[-1]
            left = cols_with_content[0]
            right = cols_with_content[-1]

            # Add small padding
            padding = 5
            return (
                max(0, left - padding),
                max(0, top - padding),
                min(image.width, right + padding),
                min(image.height, bottom + padding)
            )
        except Exception as e:
            print(f"[GridDetect] Content bounds detection failed: {e}")
            return None

    def detect_by_content(self, image: Image.Image) -> 'DetectedGrid':
        """
        Detect grid by analyzing content patterns.
        Used as fallback when no metadata is available.

        Args:
            image: PIL Image of scanned contact sheet

        Returns:
            DetectedGrid with detected cells
        """
        cv_image = self._pil_to_cv(image)
        gray = cv2.cvtColor(cv_image, cv2.COLOR_BGR2GRAY)

        # Binarize and clean to separate thumbnails from labels
        binary = cv2.adaptiveThreshold(
            gray, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            25, 10
        )
        # Close gaps inside thumbnails, remove thin text/lines
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        cleaned = cv2.morphologyEx(
            binary, cv2.MORPH_CLOSE, kernel, iterations=2)

        # Find the largest contiguous region (the grid) to avoid capturing header text
        grid_bounds = self._find_grid_region(cleaned)

        if grid_bounds:
            left, top, right, bottom = grid_bounds
            gray_content = cleaned[top:bottom, left:right]
        else:
            # Fallback to previous content bound approach
            content_bounds = self._detect_content_bounds(image)
            if content_bounds:
                left, top, right, bottom = content_bounds
                gray_content = gray[top:bottom, left:right]
            else:
                gray_content = cleaned
                left, top = 0, 0

        # Use projection profiles on cleaned binary map to find grid lines
        rows, cols, cell_h, cell_w = self._analyze_projection_profiles(
            gray_content)

        if rows == 0 or cols == 0:
            # Last resort: assume common grid sizes
            rows, cols = 6, 5
            cell_w = gray_content.shape[1] // cols
            cell_h = gray_content.shape[0] // rows

        # Build cells
        cells = []
        spacing_x = 0
        spacing_y = 0

        for row in range(rows):
            for col in range(cols):
                x = left + col * cell_w
                y = top + row * cell_h

                cells.append(GridCell(
                    x=x, y=y,
                    width=cell_w, height=cell_h,
                    row=row, col=col
                ))

        return DetectedGrid(
            cells=cells,
            rows=rows,
            cols=cols,
            cell_width=cell_w,
            cell_height=cell_h,
            origin=(left, top),
            spacing_x=spacing_x,
            spacing_y=spacing_y
        )

    def _analyze_projection_profiles(self, gray: np.ndarray) -> Tuple[int, int, int, int]:
        """
        Analyze horizontal and vertical projection profiles to find grid structure.

        Returns:
            (rows, cols, cell_height, cell_width)
        """
        # Calculate projection profiles
        h_profile = np.mean(gray, axis=1)  # Horizontal profile (rows)
        v_profile = np.mean(gray, axis=0)  # Vertical profile (cols)

        # Find valleys (gaps between cells) in profiles
        h_valleys = self._find_profile_valleys(h_profile)
        v_valleys = self._find_profile_valleys(v_profile)

        rows = len(h_valleys) + 1 if h_valleys else 0
        cols = len(v_valleys) + 1 if v_valleys else 0

        cell_h = gray.shape[0] // max(rows, 1)
        cell_w = gray.shape[1] // max(cols, 1)

        return rows, cols, cell_h, cell_w

    def _find_grid_region(self, binary: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """
        Find the dominant rectangular region corresponding to the thumbnail grid.
        """
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        # Pick the largest contour by area
        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)

        # Discard obviously too-small regions
        if w < self.min_cell_size or h < self.min_cell_size:
            return None

        # Add small padding to avoid clipping edges
        pad = max(5, int(min(w, h) * 0.01))
        left = max(0, x - pad)
        top = max(0, y - pad)
        right = min(binary.shape[1], x + w + pad)
        bottom = min(binary.shape[0], y + h + pad)
        return (left, top, right, bottom)

    def _find_profile_valleys(self, profile: np.ndarray, min_distance: int = 50) -> List[int]:
        """Find valleys (local maxima in brightness = gaps) in projection profile."""
        # Smooth the profile
        kernel_size = min(21, len(profile) // 10)
        if kernel_size % 2 == 0:
            kernel_size += 1
        if kernel_size < 3:
            return []

        smoothed = cv2.GaussianBlur(
            profile.reshape(-1, 1), (1, kernel_size), 0).flatten()

        # Find peaks (bright areas = gaps between cells)
        threshold = np.mean(smoothed) + np.std(smoothed) * 0.5
        peaks = np.where(smoothed > threshold)[0]

        if len(peaks) == 0:
            return []

        # Cluster peaks
        valleys = []
        current_start = peaks[0]
        current_end = peaks[0]

        for p in peaks[1:]:
            if p - current_end < min_distance:
                current_end = p
            else:
                valleys.append((current_start + current_end) // 2)
                current_start = p
                current_end = p

        valleys.append((current_start + current_end) // 2)

        # Filter valleys that are too close to edges
        margin = len(profile) // 20
        valleys = [v for v in valleys if margin < v < len(profile) - margin]

        return valleys

    def _pil_to_cv(self, image: Image.Image) -> np.ndarray:
        """Convert PIL Image to OpenCV format."""
        if image.mode != 'RGB':
            image = image.convert('RGB')
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    def visualize_grid(self,
                       image: Image.Image,
                       grid: 'DetectedGrid',
                       color: Tuple[int, int, int] = (255, 0, 0),
                       thickness: int = 2) -> Image.Image:
        """
        Draw detected grid overlay on image for visualization.

        Args:
            image: Original PIL Image
            grid: DetectedGrid to visualize
            color: Line color (R, G, B)
            thickness: Line thickness in pixels

        Returns:
            PIL Image with grid overlay
        """
        cv_image = self._pil_to_cv(image)
        cv_color = (color[2], color[1], color[0])  # BGR

        cells_to_draw = grid.get_cells_in_order()

        for i, cell in enumerate(cells_to_draw):
            x, y, w, h = cell.x, cell.y, cell.width, cell.height
            cv2.rectangle(cv_image, (x, y), (x + w, y + h),
                          cv_color, thickness)

            # Add cell index
            label = f"{i}"
            cv2.putText(cv_image, label, (x + 5, y + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, cv_color, 1)

        # Convert back to PIL
        return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))
