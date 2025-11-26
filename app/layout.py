from PIL import Image, ImageOps, ImageDraw, ImageFont
import platform


class LayoutEngine:
    PAPER_SIZES = {
        "LETTER": (8.5, 11),
        "A4": (8.27, 11.69),
        "TABLOID": (11, 17)
    }

    def __init__(self, paper_size="LETTER", dpi=300, margin_inches=0.5, spacing_inches=0.1):
        self.dpi = dpi
        if paper_size not in self.PAPER_SIZES:
            raise ValueError(
                f"Unknown paper size: {paper_size}. Available: {list(self.PAPER_SIZES.keys())}")

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
            # Convert to CMYK
            cmyk_image = sheet_image.convert("CMYK")
            c, m, y, k = cmyk_image.split()

            # In PIL CMYK: 0 = No Ink, 255 = Full Ink.
            # For RISO Master (Grayscale): 255 = White (No Ink), 0 = Black (Full Ink).
            # So we need to invert the channels.
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
        """
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

        return img_labeled
