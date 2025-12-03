import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import sys
import tempfile
from PIL import Image, ImageTk, ImageDraw

from processor import VideoProcessor
from layout import LayoutEngine
from effects import ImageEffects


class DesignToken:
    """Swiss/International Style Design System"""

    # Colors - Minimal, high contrast
    BLACK = "#000000"
    WHITE = "#FEFEFE"
    GRAY_100 = "#F5F5F5"
    GRAY_200 = "#E5E5E5"
    GRAY_300 = "#D4D4D4"
    GRAY_400 = "#A3A3A3"
    GRAY_500 = "#737373"
    GRAY_600 = "#525252"
    GRAY_700 = "#404040"
    GRAY_800 = "#262626"
    GRAY_900 = "#171717"

    # Greyscale dark theme
    BG = "#1A1A1A"           # Main background
    CARD = "#2A2A2A"         # Section backgrounds
    CARD_HOVER = "#333333"   # Hover state
    BORDER = "#3A3A3A"       # Borders
    BTN = "#404040"          # Button background
    BTN_HOVER = "#4A4A4A"    # Button hover
    BTN_PRIMARY = "#525252"  # Primary button
    BTN_PRIMARY_HOVER = "#5C5C5C"

    # Typography - Clean sans-serif
    FONT_FAMILY = "Helvetica Neue"
    FONT_FAMILY_FALLBACK = "Arial"

    # Spacing based on 8px grid
    SPACE_XS = 4
    SPACE_SM = 8
    SPACE_MD = 16
    SPACE_LG = 24
    SPACE_XL = 32
    SPACE_2XL = 48

    # Border radius - minimal
    RADIUS_SM = 2
    RADIUS_MD = 4

    @staticmethod
    def get_font(size=14, weight="normal"):
        """Get font tuple with fallback"""
        try:
            return (DesignToken.FONT_FAMILY, size, weight)
        except:
            return (DesignToken.FONT_FAMILY_FALLBACK, size, weight)


class IconGenerator:
    @staticmethod
    def create_arrow_icon(size=(16, 16), color="#000000"):
        """Minimal arrow icon"""
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Simple right arrow
        draw.polygon([4, 3, 12, 8, 4, 13], fill=color)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)

    @staticmethod
    def create_plus_icon(size=(16, 16), color="#000000"):
        """Minimal plus icon"""
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Cross/plus
        draw.rectangle([7, 2, 9, 14], fill=color)
        draw.rectangle([2, 7, 14, 9], fill=color)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)

    @staticmethod
    def create_folder_icon(size=(16, 16), color="#000000"):
        """Minimal folder icon"""
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([1, 4, 15, 14], fill=color)
        draw.rectangle([1, 3, 7, 5], fill=color)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)


class RisoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Set dark appearance
        ctk.set_appearance_mode("dark")

        self.title("VIDEO → RISO")
        self.geometry("520x600")
        self.resizable(False, False)
        self.configure(fg_color=DesignToken.BG)

        # Set App Icon
        try:
            icon_path = self.resource_path(
                "icons/Assets.xcassets/AppIcon.appiconset/1024-mac.png")
            if os.path.exists(icon_path):
                icon_img = Image.open(icon_path)
                self.iconphoto(True, ImageTk.PhotoImage(icon_img))
        except Exception as e:
            print(f"Failed to load icon: {e}")

        # --- Variables ---
        self.video_path = ctk.StringVar()
        self.video_name_display = ctk.StringVar(value="No file selected")

        default_out = os.path.join(tempfile.gettempdir(), "videoToRISO_output")
        self.output_path = ctk.StringVar(value=default_out)
        self.output_name_display = ctk.StringVar(
            value=os.path.basename(default_out) or default_out)

        self.columns = ctk.IntVar(value=5)
        self.columns_str = ctk.StringVar(value="5")  # For segmented button
        self.interval = ctk.StringVar(value="0.5")
        self.selected_effect = ctk.StringVar(value="None")

        self.use_cyan = ctk.BooleanVar(value=True)
        self.use_magenta = ctk.BooleanVar(value=True)
        self.use_yellow = ctk.BooleanVar(value=True)
        self.use_black = ctk.BooleanVar(value=True)

        # Icons
        self.icon_arrow = IconGenerator.create_arrow_icon(
            color=DesignToken.WHITE)
        self.icon_plus = IconGenerator.create_plus_icon(
            color=DesignToken.BLACK)
        self.icon_folder = IconGenerator.create_folder_icon(
            color=DesignToken.BLACK)

        # --- Build UI ---
        self.create_ui()

    def resource_path(self, relative_path):
        """Get absolute path to resource, works for dev and for PyInstaller"""
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def _on_columns_change(self, value):
        """Update IntVar when segmented button changes"""
        self.columns.set(int(value))

    def create_section_label(self, parent, title):
        """Create a simple section label"""
        ctk.CTkLabel(
            parent,
            text=title.upper(),
            font=DesignToken.get_font(11, "bold"),
            text_color=DesignToken.GRAY_500
        ).pack(anchor="w", pady=(0, DesignToken.SPACE_SM))

    def create_ui(self):
        # Main Container - generous padding
        self.main = ctk.CTkFrame(self, fg_color="transparent")
        self.main.pack(fill="both", expand=True,
                       padx=DesignToken.SPACE_XL, pady=DesignToken.SPACE_XL)

        # ═══════════════════════════════════════════════════════════
        # SECTION: INPUT (Single row layout)
        # ═══════════════════════════════════════════════════════════
        self.create_section_label(self.main, "Input")

        input_section = ctk.CTkFrame(
            self.main, fg_color=DesignToken.CARD, corner_radius=DesignToken.RADIUS_MD)
        input_section.pack(fill="x", pady=(0, DesignToken.SPACE_LG))

        input_inner = ctk.CTkFrame(input_section, fg_color="transparent")
        input_inner.pack(fill="x", padx=DesignToken.SPACE_MD,
                         pady=DesignToken.SPACE_MD)

        # Single row with both inputs
        input_row = ctk.CTkFrame(input_inner, fg_color="transparent")
        input_row.pack(fill="x")
        input_row.columnconfigure(1, weight=1)
        input_row.columnconfigure(3, weight=1)

        # Video button
        ctk.CTkButton(
            input_row,
            text="Video",
            width=70,
            height=32,
            command=self.browse_file,
            fg_color=DesignToken.BTN,
            hover_color=DesignToken.BTN_HOVER,
            text_color=DesignToken.WHITE,
            corner_radius=DesignToken.RADIUS_SM,
            font=DesignToken.get_font(12)
        ).grid(row=0, column=0, sticky="w")

        # Video filename
        ctk.CTkLabel(
            input_row,
            textvariable=self.video_name_display,
            font=DesignToken.get_font(11),
            text_color=DesignToken.GRAY_400,
            anchor="w"
        ).grid(row=0, column=1, sticky="ew", padx=(DesignToken.SPACE_SM, DesignToken.SPACE_MD))

        # Output button
        ctk.CTkButton(
            input_row,
            text="Output",
            width=70,
            height=32,
            command=self.browse_output,
            fg_color=DesignToken.BTN,
            hover_color=DesignToken.BTN_HOVER,
            text_color=DesignToken.WHITE,
            corner_radius=DesignToken.RADIUS_SM,
            font=DesignToken.get_font(12)
        ).grid(row=0, column=2, sticky="w")

        # Output folder name
        ctk.CTkLabel(
            input_row,
            textvariable=self.output_name_display,
            font=DesignToken.get_font(11),
            text_color=DesignToken.GRAY_400,
            anchor="w"
        ).grid(row=0, column=3, sticky="ew", padx=(DesignToken.SPACE_SM, 0))

        # ═══════════════════════════════════════════════════════════
        # SECTION: SETTINGS
        # ═══════════════════════════════════════════════════════════
        self.create_section_label(self.main, "Settings")

        settings_section = ctk.CTkFrame(
            self.main, fg_color=DesignToken.CARD, corner_radius=DesignToken.RADIUS_MD)
        settings_section.pack(fill="x", pady=(0, DesignToken.SPACE_LG))

        settings_inner = ctk.CTkFrame(settings_section, fg_color="transparent")
        settings_inner.pack(
            fill="x", padx=DesignToken.SPACE_MD, pady=DesignToken.SPACE_MD)

        # Row 1: Columns (full width)
        ctk.CTkLabel(
            settings_inner,
            text="COLUMNS",
            font=DesignToken.get_font(10, "bold"),
            text_color=DesignToken.GRAY_500
        ).pack(anchor="w")

        # Segmented button for column selection
        ctk.CTkSegmentedButton(
            settings_inner,
            values=["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
            variable=self.columns_str,
            command=self._on_columns_change,
            height=28,
            corner_radius=DesignToken.RADIUS_SM,
            fg_color=DesignToken.BORDER,
            selected_color=DesignToken.GRAY_500,
            selected_hover_color=DesignToken.GRAY_400,
            unselected_color=DesignToken.BORDER,
            unselected_hover_color=DesignToken.BTN,
            text_color=DesignToken.WHITE,
            text_color_disabled=DesignToken.GRAY_600,
            font=DesignToken.get_font(11)
        ).pack(fill="x", pady=(DesignToken.SPACE_XS, DesignToken.SPACE_MD))

        # Row 2: Interval and Effect side by side
        row2 = ctk.CTkFrame(settings_inner, fg_color="transparent")
        row2.pack(fill="x")
        row2.columnconfigure(0, weight=1)
        row2.columnconfigure(1, weight=2)

        # Interval
        int_frame = ctk.CTkFrame(row2, fg_color="transparent")
        int_frame.grid(row=0, column=0, sticky="ew",
                       padx=(0, DesignToken.SPACE_MD))

        ctk.CTkLabel(
            int_frame,
            text="INTERVAL (S)",
            font=DesignToken.get_font(10, "bold"),
            text_color=DesignToken.GRAY_500
        ).pack(anchor="w")

        ctk.CTkEntry(
            int_frame,
            textvariable=self.interval,
            height=28,
            corner_radius=DesignToken.RADIUS_SM,
            border_width=1,
            border_color=DesignToken.BORDER,
            fg_color=DesignToken.BTN,
            text_color=DesignToken.WHITE,
            font=DesignToken.get_font(12)
        ).pack(fill="x", pady=(DesignToken.SPACE_XS, 0))

        # Effect dropdown
        effect_frame = ctk.CTkFrame(row2, fg_color="transparent")
        effect_frame.grid(row=0, column=1, sticky="ew")

        ctk.CTkLabel(
            effect_frame,
            text="EFFECT",
            font=DesignToken.get_font(10, "bold"),
            text_color=DesignToken.GRAY_500
        ).pack(anchor="w")

        ctk.CTkOptionMenu(
            effect_frame,
            variable=self.selected_effect,
            values=ImageEffects.OPTIONS,
            height=28,
            corner_radius=DesignToken.RADIUS_SM,
            fg_color=DesignToken.BTN,
            button_color=DesignToken.GRAY_500,
            button_hover_color=DesignToken.GRAY_400,
            dropdown_fg_color=DesignToken.CARD,
            dropdown_hover_color=DesignToken.BTN,
            text_color=DesignToken.WHITE,
            font=DesignToken.get_font(12)
        ).pack(fill="x", pady=(DesignToken.SPACE_XS, 0))

        # ═══════════════════════════════════════════════════════════
        # SECTION: CHANNELS (Simple colored checkboxes)
        # ═══════════════════════════════════════════════════════════
        self.create_section_label(self.main, "Channels")

        channels_section = ctk.CTkFrame(
            self.main, fg_color=DesignToken.CARD, corner_radius=DesignToken.RADIUS_MD)
        channels_section.pack(fill="x", pady=(0, DesignToken.SPACE_LG))

        channels_inner = ctk.CTkFrame(channels_section, fg_color="transparent")
        channels_inner.pack(
            fill="x", padx=DesignToken.SPACE_MD, pady=DesignToken.SPACE_MD)

        # Horizontal row of colored checkboxes
        ch_row = ctk.CTkFrame(channels_inner, fg_color="transparent")
        ch_row.pack()

        channels = [
            ("C", self.use_cyan, "#00AEEF"),
            ("M", self.use_magenta, "#EC008C"),
            ("Y", self.use_yellow, "#FFF200"),
            ("K", self.use_black, "#000000"),
        ]

        for letter, var, color in channels:
            ch_frame = ctk.CTkFrame(ch_row, fg_color="transparent")
            ch_frame.pack(side="left", padx=DesignToken.SPACE_MD)

            # Colored checkbox with letter
            ctk.CTkCheckBox(
                ch_frame,
                text=letter,
                variable=var,
                width=60,
                height=28,
                checkbox_width=22,
                checkbox_height=22,
                corner_radius=DesignToken.RADIUS_SM,
                fg_color=color,
                hover_color=color,
                border_color=DesignToken.BORDER,
                text_color=DesignToken.WHITE,
                font=DesignToken.get_font(13, "bold")
            ).pack()

        # ═══════════════════════════════════════════════════════════
        # GENERATE BUTTON
        # ═══════════════════════════════════════════════════════════
        self.btn_run = ctk.CTkButton(
            self.main,
            text="GENERATE",
            command=self.start_generation,
            height=56,
            corner_radius=DesignToken.RADIUS_SM,
            fg_color=DesignToken.BTN_PRIMARY,
            hover_color=DesignToken.BTN_PRIMARY_HOVER,
            text_color=DesignToken.WHITE,
            font=DesignToken.get_font(16, "bold")
        )
        self.btn_run.pack(fill="x", pady=(
            DesignToken.SPACE_SM, DesignToken.SPACE_MD))

        # Progress bar - minimal
        self.progress = ctk.CTkProgressBar(
            self.main,
            height=4,
            corner_radius=2,
            fg_color=DesignToken.BORDER,
            progress_color=DesignToken.GRAY_500
        )
        self.progress.pack(fill="x")
        self.progress.set(0)

    def browse_file(self):
        f = filedialog.askopenfilename(
            filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv")])
        if f:
            self.video_path.set(f)
            self.video_name_display.set(os.path.basename(f))

    def browse_output(self):
        d = filedialog.askdirectory()
        if d:
            self.output_path.set(d)
            self.output_name_display.set(
                os.path.basename(d) if os.path.basename(d) else d)

    def start_generation(self):
        if not self.video_path.get():
            messagebox.showerror("Error", "Please select a video file.")
            return

        self.btn_run.configure(state="disabled", text="PROCESSING...")
        self.progress.set(0)
        self.progress.start()

        threading.Thread(target=self.run_process, daemon=True).start()

    def run_process(self):
        try:
            video_file = self.video_path.get()
            output_dir = self.output_path.get()
            cols = self.columns.get()

            try:
                interval = float(self.interval.get())
            except ValueError:
                raise ValueError("Invalid interval. Please enter a number.")

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # 1. Process Video
            processor = VideoProcessor(video_file)
            frames = processor.extract_frames(interval_seconds=interval)
            processor.close()

            if not frames:
                raise ValueError(
                    "No frames extracted. Check interval or video.")

            # 2. Layout
            dpi = 300
            layout = LayoutEngine(paper_size="LETTER", dpi=dpi)
            sheets = layout.create_sheets(frames, columns=cols)
            thumb_size = layout.get_thumbnail_size()

            self.generated_sheets = []

            # 3. Save & Separate
            composite_pages = []
            channel_pages = []
            effect_name = self.selected_effect.get()

            for i, sheet in enumerate(sheets):
                labeled_sheet = layout.add_label(
                    sheet, f"Sheet {i+1} - Composite")
                composite_pages.append(labeled_sheet)

                channels = layout.separate_channels(sheet, mode="CMYK")

                if self.use_cyan.get():
                    img_cyan = ImageEffects.apply_effect(
                        channels['Cyan'], effect_name,
                        thumb_size_pixels=thumb_size, dpi=dpi)
                    lbl_cyan = layout.add_label(
                        img_cyan, f"Sheet {i+1} - Cyan Channel")
                    channel_pages.append(lbl_cyan)

                if self.use_magenta.get():
                    img_magenta = ImageEffects.apply_effect(
                        channels['Magenta'], effect_name,
                        thumb_size_pixels=thumb_size, dpi=dpi)
                    lbl_magenta = layout.add_label(
                        img_magenta, f"Sheet {i+1} - Magenta Channel")
                    channel_pages.append(lbl_magenta)

                if self.use_yellow.get():
                    img_yellow = ImageEffects.apply_effect(
                        channels['Yellow'], effect_name,
                        thumb_size_pixels=thumb_size, dpi=dpi)
                    lbl_yellow = layout.add_label(
                        img_yellow, f"Sheet {i+1} - Yellow Channel")
                    channel_pages.append(lbl_yellow)

                if self.use_black.get():
                    img_black = ImageEffects.apply_effect(
                        channels['Black'], effect_name,
                        thumb_size_pixels=thumb_size, dpi=dpi)
                    lbl_black = layout.add_label(
                        img_black, f"Sheet {i+1} - Black Channel")
                    channel_pages.append(lbl_black)

            composite_pdf_path = None
            channels_pdf_path = None

            if composite_pages:
                composite_pdf_path = os.path.join(output_dir, "composites.pdf")
                composite_pages[0].save(
                    composite_pdf_path,
                    save_all=True,
                    append_images=composite_pages[1:] if len(
                        composite_pages) > 1 else [],
                    resolution=300.0
                )

            if channel_pages:
                channels_pdf_path = os.path.join(output_dir, "channels.pdf")
                bitmap_pages = []
                for page in channel_pages:
                    if page.mode == '1':
                        bitmap_pages.append(page)
                    else:
                        bitmap_pages.append(page.convert(
                            '1', dither=Image.Dither.NONE))

                bitmap_pages[0].save(
                    channels_pdf_path,
                    save_all=True,
                    append_images=bitmap_pages[1:] if len(
                        bitmap_pages) > 1 else [],
                    resolution=300.0
                )

            self.after(0, lambda: self.on_success(
                composite_pdf_path, channels_pdf_path))

        except Exception as e:
            self.after(0, lambda: self.on_error(str(e)))

    def on_success(self, composite_pdf_path, channels_pdf_path):
        self.progress.stop()
        self.progress.set(1)
        self.btn_run.configure(state="normal", text="GENERATE")

        import platform
        import subprocess

        opened_files = []

        for pdf_path in [composite_pdf_path, channels_pdf_path]:
            if pdf_path and os.path.exists(pdf_path):
                opened_files.append(os.path.basename(pdf_path))
                try:
                    if platform.system() == 'Darwin':
                        subprocess.call(('open', pdf_path))
                    elif platform.system() == 'Windows':
                        os.startfile(pdf_path)
                    else:
                        subprocess.call(('xdg-open', pdf_path))
                except Exception as e:
                    messagebox.showerror("Error", f"Could not open PDF: {e}")

        if not opened_files:
            messagebox.showinfo(
                "Complete", "Process completed, but no PDFs were generated.")
        else:
            messagebox.showinfo(
                "Complete", f"Generated:\n{chr(10).join(opened_files)}")

    def on_error(self, msg):
        self.progress.stop()
        self.btn_run.configure(state="normal", text="GENERATE")
        messagebox.showerror("Error", msg)
