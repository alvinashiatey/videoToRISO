from PIL import Image, ImageOps, ImageDraw, ImageFont
import platform
import numpy as np
import os

try:
    from PIL import ImageCms
except Exception:  # Pillow built without ImageCms
    ImageCms = None


class LayoutEngine:
    PAPER_SIZES = {
        "LETTER": (8.5, 11),
        "A4": (8.27, 11.69),
        "TABLOID": (11, 17)
    }

    def __init__(self, paper_size="LETTER", dpi=300, margin_inches=0.5, spacing_inches=0.1, cmyk_profile_path=None):
        self.dpi = dpi
        if paper_size not in self.PAPER_SIZES:
            raise ValueError(
                f"Unknown paper size: {paper_size}. Available: {list(self.PAPER_SIZES.keys())}")
        # Track last thumbnail size so effects can scale to the rendered cell size
        self.thumb_size = None
        # Optional CMYK ICC profile for more print-faithful separations
        self.cmyk_profile_path = cmyk_profile_path or self._find_default_cmyk_profile()

        width_in, height_in = self.PAPER_SIZES[paper_size]
        self.page_width = int(width_in * dpi)
        self.page_height = int(height_in * dpi)
        self.margin = int(margin_inches * dpi)
        self.spacing = int(spacing_inches * dpi)

    def create_sheets(self, frames, columns=3):
        """
        Arranges frames onto sheets.

        Args:
            frames (list): List of PIL Image objects.
            columns (int): Number of columns in the grid.

        Returns:
            list: List of PIL Image objects (the sheets).
        """
        if not frames:
            return []

        # Calculate thumbnail dimensions
        printable_width = self.page_width - (2 * self.margin)

        # Width of one thumbnail
        # Total width = (cols * thumb_w) + ((cols - 1) * spacing)
        # thumb_w = (Total width - ((cols - 1) * spacing)) / cols
        total_spacing_x = (columns - 1) * self.spacing
        thumb_width = int((printable_width - total_spacing_x) / columns)

        # Calculate height based on first frame's aspect ratio
        first_frame = frames[0]
        aspect_ratio = first_frame.height / first_frame.width
        thumb_height = int(thumb_width * aspect_ratio)
        self.thumb_size = (thumb_width, thumb_height)

        sheets = []
        current_sheet = self._create_blank_sheet()
        current_x = self.margin
        current_y = self.margin

        col_count = 0

        for frame in frames:
            # Resize frame
            resized_frame = frame.resize(
                (thumb_width, thumb_height), Image.Resampling.LANCZOS)

            # Check if we need a new row (height check)
            # If adding this row would exceed the bottom margin
            if current_y + thumb_height > self.page_height - self.margin:
                sheets.append(current_sheet)
                current_sheet = self._create_blank_sheet()
                current_x = self.margin
                current_y = self.margin
                col_count = 0

            # Paste image
            current_sheet.paste(resized_frame, (current_x, current_y))

            # Move cursor
            col_count += 1
            current_x += thumb_width + self.spacing

            # Check if row is full
            if col_count >= columns:
                col_count = 0
                current_x = self.margin
                current_y += thumb_height + self.spacing

        # Add the last sheet if it has content
        sheets.append(current_sheet)

        return sheets

    def _create_blank_sheet(self):
        return Image.new("RGB", (self.page_width, self.page_height), "white")

    def get_thumbnail_size(self):
        """
        Returns the most recently calculated thumbnail size (width, height).
        Useful for scaling effects to the final cell size.
        """
        return self.thumb_size

    def separate_channels(self, sheet_image, mode="RGB"):
        """
        Splits a sheet into separate grayscale channels for RISO printing.

        Args:
            sheet_image (PIL.Image): The color sheet.
            mode (str): "CMYK" or "RGB".

        Returns:
            dict: {channel_name: grayscale_image}
        """
        channels = {}

        if mode == "CMYK":
            cmyk_image = self._convert_to_cmyk(sheet_image)
            c, m, y, k = cmyk_image.split()

            # For RISO masters: 255 = White (No Ink), 0 = Black (Full Ink)
            channels['Cyan'] = ImageOps.invert(c)
            channels['Magenta'] = ImageOps.invert(m)
            channels['Yellow'] = ImageOps.invert(y)
            channels['Black'] = ImageOps.invert(k)

        elif mode == "RGB":
            # Convert to RGB
            rgb_image = sheet_image.convert("RGB")
            r, g, b = rgb_image.split()

            # In RGB: 0 = Dark (Ink needed for complementary), 255 = Light (No Ink).
            # This maps directly to RISO Master (0=Black/Ink, 255=White/No Ink).
            # Note: Red Channel is typically printed with Cyan Ink, etc.
            channels['Red'] = r
            channels['Green'] = g
            channels['Blue'] = b

        return channels

    def add_label(self, image, text):
        """
        Adds a text label to the top-left of the image.
        For 1-bit (bitmap) images, converts to grayscale first to allow
        anti-aliased text, then converts back to 1-bit.
        """
        original_mode = image.mode

        # Convert 1-bit to grayscale for text rendering
        if original_mode == '1':
            img_labeled = image.convert('L')
        else:
            img_labeled = image.copy()

        draw = ImageDraw.Draw(img_labeled)

        # Font selection - aim for ~1/8 inch height (37px at 300dpi)
        font_size = int(self.dpi / 8)
        font = None

        system = platform.system()
        try:
            if system == "Darwin":
                font = ImageFont.truetype(
                    "/System/Library/Fonts/Helvetica.ttc", font_size)
            elif system == "Windows":
                font = ImageFont.truetype("arial.ttf", font_size)
            else:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
        except:
            try:
                # Try loading without path
                font = ImageFont.truetype("Arial", font_size)
            except:
                # Fallback
                pass

        if font is None:
            font = ImageFont.load_default()

        # Position in top margin
        x = self.margin
        # Center vertically in the top margin space
        y = (self.margin // 2) - (font_size // 2)

        # Determine fill color (Black for RISO masters)
        # If mode is L (grayscale), 0 is black.
        # If mode is RGB, (0,0,0) is black.
        fill_color = 0 if img_labeled.mode == 'L' else (0, 0, 0)

        draw.text((x, y), text, fill=fill_color, font=font)

        # Convert back to 1-bit if original was bitmap
        if original_mode == '1':
            # Use thresholding (no dither) to keep text sharp
            img_labeled = img_labeled.convert('1', dither=Image.Dither.NONE)

        return img_labeled

    def _convert_to_cmyk(self, image):
        """
        Convert RGB to CMYK using an ICC profile when available for a more
        print-faithful split. Falls back to a manual GCR-based conversion if
        ImageCms or profiles are unavailable.
        """
        rgb_image = image.convert("RGB")

        if ImageCms:
            try:
                src = ImageCms.createProfile("sRGB")

                # Prefer provided profile or a system one; otherwise fall back to a generic CMYK profile.
                if self.cmyk_profile_path and os.path.exists(self.cmyk_profile_path):
                    dst = ImageCms.getOpenProfile(self.cmyk_profile_path)
                else:
                    dst = ImageCms.createProfile("CMYK")

                transform = ImageCms.buildTransform(
                    src, dst, "RGB", "CMYK", renderingIntent=0)
                return ImageCms.applyTransform(rgb_image, transform)
            except Exception:
                # Continue to manual fallback
                pass

        # Manual fallback: simple GCR approximation
        rgb_array = np.array(rgb_image, dtype=np.float32) / 255.0
        r = rgb_array[:, :, 0]
        g = rgb_array[:, :, 1]
        b = rgb_array[:, :, 2]

        # Calculate K (black) as 1 - max(R, G, B)
        k = 1 - np.maximum(np.maximum(r, g), b)
        k_inv = np.where(k < 1.0, 1.0 - k, 1.0)

        c = np.where(k < 1.0, (1 - r - k) / k_inv, 0)
        m = np.where(k < 1.0, (1 - g - k) / k_inv, 0)
        y = np.where(k < 1.0, (1 - b - k) / k_inv, 0)

        c = np.clip(c, 0, 1)
        m = np.clip(m, 0, 1)
        y = np.clip(y, 0, 1)
        k = np.clip(k, 0, 1)

        return Image.merge("CMYK", (
            Image.fromarray((c * 255).astype(np.uint8), mode='L'),
            Image.fromarray((m * 255).astype(np.uint8), mode='L'),
            Image.fromarray((y * 255).astype(np.uint8), mode='L'),
            Image.fromarray((k * 255).astype(np.uint8), mode='L'),
        ))

    def _find_default_cmyk_profile(self):
        """
        Attempt to locate a system CMYK ICC profile for more accurate separations.
        """
        common_paths = [
            "/System/Library/ColorSync/Profiles/Generic CMYK Profile.icc",  # macOS
            "/Library/ColorSync/Profiles/Generic CMYK Profile.icc",
            "/usr/share/color/icc/colord/CoatedFOGRA39.icc",
            "/usr/share/color/icc/USWebCoatedSWOP.icc",
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        return None
