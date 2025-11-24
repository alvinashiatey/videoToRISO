from PIL import Image, ImageDraw, ImageStat


class ImageEffects:
    OPTIONS = ["None", "Floyd-Steinberg", "Threshold",
               "Halftone", "Pixelate", "Scanlines"]

    @staticmethod
    def apply_effect(image, effect_name):
        """
        Applies a dither/halftone effect to a grayscale image.
        Returns a grayscale (L) image.
        """
        if effect_name == "None":
            return image

        # Ensure grayscale
        if image.mode != 'L':
            img = image.convert('L')
        else:
            img = image.copy()

        if effect_name == "Floyd-Steinberg":
            # Convert to 1-bit using Floyd-Steinberg dithering
            return img.convert('1').convert('L')

        elif effect_name == "Threshold":
            # Simple threshold at 128
            return img.point(lambda x: 255 if x > 128 else 0, '1').convert('L')

        elif effect_name == "Halftone":
            # Dot halftone simulation
            # Create a new white image
            out = Image.new('L', img.size, 255)
            draw = ImageDraw.Draw(out)
            width, height = img.size
            sample = 8  # Grid size

            for x in range(0, width, sample):
                for y in range(0, height, sample):
                    # Get average brightness of the block
                    box = img.crop(
                        (x, y, min(x + sample, width), min(y + sample, height)))
                    stat = ImageStat.Stat(box)
                    avg = stat.mean[0]

                    # Calculate radius: Darker (lower avg) -> Larger radius
                    # 0 -> max radius, 255 -> 0 radius
                    max_radius = sample / 2 * 1.3  # 1.3 for slight overlap/boldness
                    radius = (1 - (avg / 255)) * max_radius

                    if radius > 0.5:
                        cx, cy = x + sample / 2, y + sample / 2
                        draw.ellipse((cx - radius, cy - radius,
                                     cx + radius, cy + radius), fill=0)

            return out

        elif effect_name == "Pixelate":
            # Downscale and upscale
            pixel_size = 12
            w, h = img.size
            small = img.resize(
                (max(1, w // pixel_size), max(1, h // pixel_size)), Image.Resampling.NEAREST)
            return small.resize((w, h), Image.Resampling.NEAREST)

        elif effect_name == "Scanlines":
            # Horizontal scanlines
            out = img.copy()
            draw = ImageDraw.Draw(out)
            width, height = img.size
            line_spacing = 4

            for y in range(0, height, line_spacing):
                # Draw a white line (erasing ink)
                draw.line([(0, y), (width, y)], fill=255, width=1)

            return out

        return image
