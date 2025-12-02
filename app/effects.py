from PIL import Image, ImageDraw, ImageStat, ImageFilter, ImageEnhance


class ImageEffects:
    OPTIONS = ["None", "Floyd-Steinberg", "Threshold",
               "Halftone", "Pixelate", "Scanlines",
               "High Contrast", "Stochastic", "Surprise Me"]

    # Minimum dot/line size in inches that will be visible when printed
    # RISO can reliably print details down to about 1/150 inch (0.17mm)
    # But for safety and visibility, we target larger minimums
    MIN_DOT_INCHES = 0.02  # ~1/50 inch - clearly visible
    MIN_LINE_INCHES = 0.015  # ~1/65 inch for line spacing

    @staticmethod
    def _calculate_print_params(image, thumb_size_pixels, dpi=300):
        """
        Calculate effect parameters based on physical print size.

        Args:
            image: The full-page image being processed
            thumb_size_pixels: (width, height) of one thumbnail cell in pixels
            dpi: Print resolution

        Returns:
            dict with calculated parameters for effects
        """
        if thumb_size_pixels is None:
            # Fallback: assume image is full page
            thumb_width_inches = image.width / dpi
        else:
            thumb_width_inches = thumb_size_pixels[0] / dpi

        # Calculate minimum feature sizes in pixels
        min_dot_pixels = max(2, int(ImageEffects.MIN_DOT_INCHES * dpi))
        min_line_pixels = max(2, int(ImageEffects.MIN_LINE_INCHES * dpi))

        # For halftone: we want visible dots that still show the image
        # More dots = smaller individual dots (higher = finer detail)
        dots_per_thumb = 28
        halftone_cell = max(min_dot_pixels, int(
            thumb_size_pixels[0] / dots_per_thumb) if thumb_size_pixels else 12)

        # For scanlines: visible line spacing
        scanline_spacing = max(min_line_pixels, int(
            thumb_size_pixels[1] / 30) if thumb_size_pixels else 4)

        # For pixelate: chunky visible pixels
        pixels_per_thumb = 8
        pixel_size = max(
            3, int(thumb_size_pixels[0] / pixels_per_thumb) if thumb_size_pixels else 12)

        return {
            'halftone_cell': halftone_cell,
            'scanline_spacing': scanline_spacing,
            'pixel_size': pixel_size,
            'thumb_width_inches': thumb_width_inches,
            'is_small': thumb_width_inches < 1.5  # Less than 1.5 inches wide
        }

    @staticmethod
    def apply_effect(image, effect_name, return_bitmap=True, thumb_size_pixels=None, dpi=300):
        """
        Applies a dither/halftone effect to a grayscale image.
        Effects are automatically scaled based on physical print size for optimal
        visibility at the printed thumbnail scale.

        Args:
            image: PIL Image (grayscale or RGB)
            effect_name: Name of the effect to apply
            return_bitmap: If True, returns 1-bit image for sharp edges in PDF.
                          If False, returns grayscale (L) for preview.
            thumb_size_pixels: (width, height) of thumbnail cell in pixels
            dpi: Print resolution (default 300)

        Returns:
            PIL Image in mode '1' (bitmap) or 'L' (grayscale)
        """
        if effect_name == "None":
            return image

        # Ensure grayscale
        if image.mode != 'L':
            img = image.convert('L')
        else:
            img = image.copy()

        # Calculate print-aware parameters
        params = ImageEffects._calculate_print_params(
            img, thumb_size_pixels, dpi)

        # Helper to return in correct mode
        def finalize(result_img, use_dither=False):
            """Convert to 1-bit bitmap if requested, otherwise grayscale."""
            if return_bitmap:
                if result_img.mode != '1':
                    if use_dither:
                        return result_img.convert('1')
                    else:
                        # Threshold conversion for sharp edges (no dithering)
                        return result_img.convert('1', dither=Image.Dither.NONE)
                return result_img
            else:
                if result_img.mode == '1':
                    return result_img.convert('L')
                return result_img

        if effect_name == "Floyd-Steinberg":
            # Floyd-Steinberg works well at any size
            # But for very small thumbnails, boost contrast first
            if params['is_small']:
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.4)
            return finalize(img.convert('1'))

        elif effect_name == "Threshold":
            # Adaptive threshold based on thumbnail size
            # For small thumbnails, use a slightly higher threshold to reduce blobbing
            if params['is_small']:
                threshold = 145  # More white, less blobby
            else:
                threshold = 128
            return finalize(img.point(lambda x: 255 if x > threshold else 0, '1'))

        elif effect_name == "Halftone":
            return finalize(ImageEffects._halftone(img, params['halftone_cell']), use_dither=False)

        elif effect_name == "Pixelate":
            # Use print-aware pixel size
            pixel_size = params['pixel_size']
            w, h = img.size
            small = img.resize(
                (max(1, w // pixel_size), max(1, h // pixel_size)),
                Image.Resampling.NEAREST)
            result = small.resize((w, h), Image.Resampling.NEAREST)
            # Threshold the pixelated result for sharp edges
            return finalize(result.point(lambda x: 255 if x > 128 else 0, '1'))

        elif effect_name == "Scanlines":
            # Use print-aware line spacing
            line_spacing = params['scanline_spacing']
            line_width = max(1, line_spacing // 3)  # Lines are 1/3 of spacing

            # First threshold the image
            thresholded = img.point(lambda x: 255 if x > 128 else 0)
            out = thresholded.copy()
            draw = ImageDraw.Draw(out)
            width, height = img.size

            for y in range(0, height, line_spacing):
                draw.line([(0, y), (width, y)], fill=255, width=line_width)

            return finalize(out, use_dither=False)

        elif effect_name == "High Contrast":
            # Best for small prints - maximizes clarity
            # Adjust contrast boost based on thumbnail size
            contrast_boost = 1.8 if params['is_small'] else 1.5
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(contrast_boost)
            # Sharpen more aggressively for small thumbnails
            img = img.filter(ImageFilter.SHARPEN)
            if params['is_small']:
                img = img.filter(ImageFilter.SHARPEN)  # Double sharpen
            # Apply threshold - higher for small to reduce blobbing
            threshold = 130 if params['is_small'] else 120
            return finalize(img.point(lambda x: 255 if x > threshold else 0, '1'))

        elif effect_name == "Stochastic":
            # Organic metaball-like stochastic dithering
            # Uses smooth noise field + clustering for organic blob shapes
            return finalize(ImageEffects._organic_stochastic(img, params['halftone_cell']), use_dither=False)

        elif effect_name == "Surprise Me":
            # Random shapes at random angles!
            return finalize(ImageEffects._surprise_me(img, params['halftone_cell']), use_dither=False)

        return image

    @staticmethod
    def _organic_stochastic(img, cell_size):
        """
        Create organic metaball-like stochastic dithering.
        Uses smooth noise combined with image brightness for organic blob shapes.
        Optimized with numpy for fast processing.

        Args:
            img: Grayscale PIL Image
            cell_size: Controls the scale of organic blobs
        """
        import numpy as np

        width, height = img.size

        # Convert image to numpy array
        img_array = np.array(img, dtype=np.float32) / 255.0

        # Blob scale - smaller value = smaller blobs
        # Use cell_size * 0.4 for finer organic texture
        blob_scale = max(4, cell_size * 0.4)

        # Create coordinate grids
        y_coords, x_coords = np.mgrid[0:height, 0:width]

        # Generate smooth noise using vectorized operations
        # Use multiple sine waves at different frequencies for organic look
        seed = np.random.randint(0, 1000)

        # Primary noise layer - large organic blobs
        noise1 = np.sin(x_coords / blob_scale + seed) * \
            np.cos(y_coords / blob_scale + seed * 0.7)

        # Secondary layer - medium detail
        noise2 = np.sin(x_coords / (blob_scale * 0.5) + seed * 1.3) * \
            np.cos(y_coords / (blob_scale * 0.5) + seed * 0.5)

        # Third layer - fine detail
        noise3 = np.sin(x_coords / (blob_scale * 0.25) + seed * 2.1) * \
            np.cos(y_coords / (blob_scale * 0.25) + seed * 1.7)

        # Combine layers with decreasing weights (FBM-like)
        noise = noise1 * 0.5 + noise2 * 0.3 + noise3 * 0.2

        # Normalize to 0-1 range
        noise = (noise + 1) / 2

        # Create threshold based on noise
        # Where noise is high, threshold is high (more likely to be white)
        threshold = noise

        # Apply threshold: darker image areas become black based on noise field
        result = np.where(img_array < threshold, 0, 255).astype(np.uint8)

        # Convert back to PIL Image
        out = Image.fromarray(result, mode='L')

        # Slight blur + re-threshold for smoother blob edges
        out = out.filter(ImageFilter.GaussianBlur(radius=0.8))
        out = out.point(lambda x: 0 if x < 128 else 255)

        return out

    @staticmethod
    def _halftone(img, cell_size):
        """
        Create halftone effect with specified cell size.

        Args:
            img: Grayscale PIL Image
            cell_size: Size of each halftone cell in pixels
        """
        out = Image.new('L', img.size, 255)
        draw = ImageDraw.Draw(out)
        width, height = img.size

        sample = max(2, cell_size)

        for x in range(0, width, sample):
            for y in range(0, height, sample):
                # Get average brightness of the block
                box = img.crop(
                    (x, y, min(x + sample, width), min(y + sample, height)))
                stat = ImageStat.Stat(box)
                avg = stat.mean[0]

                # Calculate radius: Darker (lower avg) -> Larger radius
                # Max radius allows dots to touch/slightly overlap for bold effect
                max_radius = sample / 2 * 1.1

                radius = (1 - (avg / 255)) * max_radius

                # Minimum visible dot (at least 1 pixel)
                if radius >= 1:
                    cx, cy = x + sample / 2, y + sample / 2
                    draw.ellipse((cx - radius, cy - radius,
                                 cx + radius, cy + radius), fill=0)

        return out

    @staticmethod
    def _surprise_me(img, cell_size):
        """
        Create a dither effect using a single randomly chosen shape consistently.
        Picks one shape from the list and uses it for all cells with random angles.

        Args:
            img: Grayscale PIL Image
            cell_size: Size of each cell in pixels
        """
        import random
        import math

        out = Image.new('L', img.size, 255)
        draw = ImageDraw.Draw(out)
        width, height = img.size

        sample = max(4, cell_size)
        shapes = ['circle', 'square', 'triangle', 'diamond', 'star', 'cross']

        # Pick ONE shape to use for the entire image
        chosen_shape = random.choice(shapes)

        for x in range(0, width, sample):
            for y in range(0, height, sample):
                # Get average brightness of the block
                box = img.crop(
                    (x, y, min(x + sample, width), min(y + sample, height)))
                stat = ImageStat.Stat(box)
                avg = stat.mean[0]

                # Calculate size based on darkness
                max_size = sample * 0.9
                size = (1 - (avg / 255)) * max_size

                if size < 2:
                    continue

                cx, cy = x + sample / 2, y + sample / 2

                # Use the chosen shape with a random angle
                shape = chosen_shape
                angle = random.uniform(0, 360)

                if shape == 'circle':
                    r = size / 2
                    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)

                elif shape == 'square':
                    # Rotated square
                    r = size / 2
                    rad = math.radians(angle)
                    cos_a, sin_a = math.cos(rad), math.sin(rad)
                    points = []
                    for dx, dy in [(-r, -r), (r, -r), (r, r), (-r, r)]:
                        rx = dx * cos_a - dy * sin_a
                        ry = dx * sin_a + dy * cos_a
                        points.append((cx + rx, cy + ry))
                    draw.polygon(points, fill=0)

                elif shape == 'triangle':
                    # Rotated triangle
                    r = size / 2
                    rad = math.radians(angle)
                    points = []
                    for i in range(3):
                        a = rad + i * 2 * math.pi / 3
                        points.append(
                            (cx + r * math.cos(a), cy + r * math.sin(a)))
                    draw.polygon(points, fill=0)

                elif shape == 'diamond':
                    # Diamond (rotated square at 45 + random angle)
                    r = size / 2
                    rad = math.radians(angle + 45)
                    cos_a, sin_a = math.cos(rad), math.sin(rad)
                    points = []
                    for dx, dy in [(-r, 0), (0, -r), (r, 0), (0, r)]:
                        rx = dx * cos_a - dy * sin_a
                        ry = dx * sin_a + dy * cos_a
                        points.append((cx + rx, cy + ry))
                    draw.polygon(points, fill=0)

                elif shape == 'star':
                    # 5-pointed star
                    r_outer = size / 2
                    r_inner = r_outer * 0.4
                    rad = math.radians(angle)
                    points = []
                    for i in range(10):
                        a = rad + i * math.pi / 5
                        r = r_outer if i % 2 == 0 else r_inner
                        points.append(
                            (cx + r * math.cos(a), cy + r * math.sin(a)))
                    draw.polygon(points, fill=0)

                elif shape == 'cross':
                    # Plus/cross shape
                    r = size / 2
                    thickness = max(2, size / 4)
                    rad = math.radians(angle)
                    cos_a, sin_a = math.cos(rad), math.sin(rad)
                    # Horizontal bar
                    t = thickness / 2
                    points1 = []
                    for dx, dy in [(-r, -t), (r, -t), (r, t), (-r, t)]:
                        rx = dx * cos_a - dy * sin_a
                        ry = dx * sin_a + dy * cos_a
                        points1.append((cx + rx, cy + ry))
                    draw.polygon(points1, fill=0)
                    # Vertical bar
                    points2 = []
                    for dx, dy in [(-t, -r), (t, -r), (t, r), (-t, r)]:
                        rx = dx * cos_a - dy * sin_a
                        ry = dx * sin_a + dy * cos_a
                        points2.append((cx + rx, cy + ry))
                    draw.polygon(points2, fill=0)

        return out
