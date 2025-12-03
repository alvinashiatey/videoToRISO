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

    # Cache for blue noise threshold matrices (void-and-cluster)
    _blue_noise_cache = {}

    @staticmethod
    def _generate_void_and_cluster_matrix(size, cluster_size=3):
        """
        Generate a blue-noise threshold matrix using the void-and-cluster algorithm.
        Based on Ostromoukhov & Hersch's "Stochastic Clustered-Dot Dithering" (1999).

        The algorithm:
        1. Start with initial binary pattern with blue noise distribution
        2. Find the "tightest cluster" (densest area of minority pixels)
        3. Find the "largest void" (sparsest area of minority pixels)
        4. Swap cluster and void pixels, assign threshold ranks
        5. Repeat until all pixels are ranked

        Args:
            size: Size of the square threshold matrix
            cluster_size: Controls dot clustering (higher = larger clusters)

        Returns:
            numpy array with threshold values 0-255
        """
        import numpy as np
        from scipy import ndimage

        n = size

        # Gaussian filter sigma for finding voids and clusters
        # Larger sigma = more clustering (as per the paper)
        sigma = cluster_size * 0.7

        # Initialize with ~10% ones (minority pixels) in random positions
        initial_density = 0.1
        pattern = np.zeros((n, n), dtype=np.float32)
        num_ones = int(n * n * initial_density)

        # Place initial points with some spacing (proto-blue-noise)
        indices = np.random.permutation(n * n)[:num_ones]
        pattern.flat[indices] = 1

        # Threshold matrix to build
        threshold = np.zeros((n, n), dtype=np.float32)
        rank = 0

        # Phase 1: Remove ones (tightest cluster first) until none left
        # This builds the first half of the threshold matrix (dark to mid)
        ones_mask = pattern.copy()
        ones_indices = []

        while np.sum(ones_mask) > 0:
            # Convolve to find cluster density
            # Wrap mode for tileable pattern
            density = ndimage.gaussian_filter(
                ones_mask, sigma=sigma, mode='wrap')

            # Find tightest cluster (highest density among ones)
            density_ones = np.where(ones_mask > 0, density, -np.inf)
            cluster_idx = np.unravel_index(np.argmax(density_ones), (n, n))

            # Remove this pixel and record its rank
            ones_mask[cluster_idx] = 0
            ones_indices.append(cluster_idx)

        # Assign ranks in reverse (first removed = highest threshold in this phase)
        for i, idx in enumerate(reversed(ones_indices)):
            threshold[idx] = i

        # Phase 2: Add ones (largest void first) until all filled
        # This builds the second half (mid to light)
        zeros_mask = 1 - pattern  # Start with the complement
        current = pattern.copy()

        phase2_indices = []
        while np.sum(zeros_mask) > 0:
            # Convolve current pattern to find void density
            density = ndimage.gaussian_filter(
                current, sigma=sigma, mode='wrap')

            # Find largest void (lowest density among zeros)
            density_zeros = np.where(zeros_mask > 0, density, np.inf)
            void_idx = np.unravel_index(np.argmin(density_zeros), (n, n))

            # Add this pixel
            current[void_idx] = 1
            zeros_mask[void_idx] = 0
            phase2_indices.append(void_idx)

        # Assign remaining ranks
        base_rank = len(ones_indices)
        for i, idx in enumerate(phase2_indices):
            threshold[idx] = base_rank + i

        # Normalize to 0-255
        threshold = (threshold / (n * n - 1) * 255).astype(np.uint8)

        return threshold

    @staticmethod
    def _get_blue_noise_matrix(size, cluster_size=3):
        """
        Get or generate a cached blue noise threshold matrix.
        """
        import numpy as np

        cache_key = (size, cluster_size)
        if cache_key not in ImageEffects._blue_noise_cache:
            try:
                # Try to use scipy for proper void-and-cluster
                ImageEffects._blue_noise_cache[cache_key] = \
                    ImageEffects._generate_void_and_cluster_matrix(
                        size, cluster_size)
            except ImportError:
                # Fallback: generate approximation without scipy
                ImageEffects._blue_noise_cache[cache_key] = \
                    ImageEffects._generate_blue_noise_fallback(
                        size, cluster_size)

        return ImageEffects._blue_noise_cache[cache_key]

    @staticmethod
    def _generate_blue_noise_fallback(size, cluster_size=3):
        """
        Fallback blue noise generation without scipy.
        Uses a simpler approach based on Robert Bridson's algorithm concepts.
        """
        import numpy as np

        n = size
        threshold = np.zeros((n, n), dtype=np.float32)

        # Generate points with minimum distance constraint (Poisson disk-like)
        min_dist = cluster_size
        points = []
        grid = {}
        cell_size = min_dist / np.sqrt(2)

        def grid_key(x, y):
            return (int(x / cell_size), int(y / cell_size))

        def distance_ok(x, y):
            gx, gy = grid_key(x, y)
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    key = ((gx + dx) % int(n / cell_size + 1),
                           (gy + dy) % int(n / cell_size + 1))
                    if key in grid:
                        px, py = grid[key]
                        # Toroidal distance
                        ddx = min(abs(x - px), n - abs(x - px))
                        ddy = min(abs(y - py), n - abs(y - py))
                        if np.sqrt(ddx**2 + ddy**2) < min_dist:
                            return False
            return True

        # Place initial points
        attempts = 0
        max_attempts = n * n * 10
        while len(points) < n * n // (cluster_size * cluster_size) and attempts < max_attempts:
            x = np.random.uniform(0, n)
            y = np.random.uniform(0, n)
            if distance_ok(x, y):
                points.append((x, y))
                grid[grid_key(x, y)] = (x, y)
            attempts += 1

        # Assign threshold values based on distance from seed points
        for y in range(n):
            for x in range(n):
                min_d = float('inf')
                for px, py in points:
                    dx = min(abs(x - px), n - abs(x - px))
                    dy = min(abs(y - py), n - abs(y - py))
                    d = np.sqrt(dx**2 + dy**2)
                    min_d = min(min_d, d)
                # Closer to seed = lower threshold (prints first)
                threshold[y, x] = min_d

        # Normalize
        threshold = (threshold - threshold.min()) / \
            (threshold.max() - threshold.min()) * 255

        # Add some noise to break up patterns
        noise = np.random.uniform(-10, 10, (n, n))
        threshold = np.clip(threshold + noise, 0, 255).astype(np.uint8)

        return threshold

    @staticmethod
    def _organic_stochastic(img, cell_size):
        """
        Stochastic clustered-dot dithering based on Ostromoukhov & Hersch (1999).

        This implements FM (Frequency Modulated) screening with:
        - Blue noise threshold matrix generated via void-and-cluster algorithm
        - Clustered dots that grow from seed points (better printability)
        - No visible periodic patterns (unlike AM halftoning)

        The result mimics RISO printer stochastic screening characteristics.

        Args:
            img: Grayscale PIL Image
            cell_size: Controls cluster size and dot density
        """
        import numpy as np

        width, height = img.size

        # Convert image to numpy array
        img_array = np.array(img, dtype=np.uint8)

        # Determine matrix size and cluster parameter
        # Larger cell_size = larger clusters = coarser texture
        matrix_size = 64  # Standard size, tiles across image
        cluster_param = max(2, min(6, cell_size // 3))

        # Get the blue noise threshold matrix
        threshold_matrix = ImageEffects._get_blue_noise_matrix(
            matrix_size, cluster_param)

        # Tile the threshold matrix across the image
        tiles_x = (width + matrix_size - 1) // matrix_size
        tiles_y = (height + matrix_size - 1) // matrix_size

        tiled_threshold = np.tile(threshold_matrix, (tiles_y, tiles_x))
        tiled_threshold = tiled_threshold[:height, :width]

        # Apply threshold: pixel is black if image value < threshold
        # This creates the stochastic pattern where darker areas have more dots
        result = np.where(img_array < tiled_threshold, 0, 255).astype(np.uint8)

        # Convert back to PIL Image
        out = Image.fromarray(result, mode='L')

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
