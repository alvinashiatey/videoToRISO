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

# Import reconstruction module
try:
    from reconstruct import ScanProcessor, GridDetector, FrameExtractor, VideoAssembler
    from reconstruct.metadata import MetadataEncoder, SheetMetadata
    from reconstruct.grid_editor import GridEditorWindow
    from reconstruct.grid_detect import DetectedGrid, GridCell
    RECONSTRUCT_AVAILABLE = True
except ImportError:
    RECONSTRUCT_AVAILABLE = False


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

        self.title("VIDEO ⟷ RISO")
        self.geometry("520x820")
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

        # --- Variables for Generate tab ---
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

        # --- Variables for Reconstruct tab ---
        self.scan_paths = []
        self.scan_display = ctk.StringVar(value="No scans selected")
        self.recon_output_path = ctk.StringVar(value=default_out)
        self.recon_output_display = ctk.StringVar(
            value=os.path.basename(default_out) or default_out)
        self.recon_rows = ctk.StringVar(value="6")
        self.recon_cols = ctk.StringVar(value="4")
        self.recon_fps = ctk.StringVar(value="12")
        self.recon_format = ctk.StringVar(value="MP4")
        self.recon_upscale = ctk.StringVar(value="1x (Original)")
        self.grid_mode = ctk.StringVar(value="Auto")

        # Cached QR metadata from background scan (avoids re-scanning)
        self.cached_scan_processors = []  # List of ScanProcessor objects with metadata
        self.cached_qr_settings = None  # Combined settings from QR detection

        # Manual grid data from GridEditorWindow
        # Format: list of dicts with {page_index, cells: [(x, y, w, h), ...]}
        self.manual_grid_cells = None
        self.grid_editor_window = None

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
        # TAB VIEW - Generate / Reconstruct
        # ═══════════════════════════════════════════════════════════
        self.tabview = ctk.CTkTabview(
            self.main,
            fg_color=DesignToken.BG,
            segmented_button_fg_color=DesignToken.CARD,
            segmented_button_selected_color=DesignToken.BTN_PRIMARY,
            segmented_button_selected_hover_color=DesignToken.BTN_PRIMARY_HOVER,
            segmented_button_unselected_color=DesignToken.CARD,
            segmented_button_unselected_hover_color=DesignToken.CARD_HOVER,
            text_color=DesignToken.WHITE
        )
        self.tabview.pack(fill="both", expand=True)

        # Add tabs
        self.tab_generate = self.tabview.add("VIDEO → RISO")
        self.tab_reconstruct = self.tabview.add("RISO → VIDEO")

        # Build each tab
        self.create_generate_tab()
        self.create_reconstruct_tab()

    def create_generate_tab(self):
        """Create the Video to RISO generation tab."""
        tab = self.tab_generate

        # ═══════════════════════════════════════════════════════════
        # SECTION: INPUT (Single row layout)
        # ═══════════════════════════════════════════════════════════
        self.create_section_label(tab, "Input")

        input_section = ctk.CTkFrame(
            tab, fg_color=DesignToken.CARD, corner_radius=DesignToken.RADIUS_MD)
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
        self.create_section_label(tab, "Settings")

        settings_section = ctk.CTkFrame(
            tab, fg_color=DesignToken.CARD, corner_radius=DesignToken.RADIUS_MD)
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
        self.create_section_label(tab, "Channels")

        channels_section = ctk.CTkFrame(
            tab, fg_color=DesignToken.CARD, corner_radius=DesignToken.RADIUS_MD)
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
            tab,
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
            tab,
            height=4,
            corner_radius=2,
            fg_color=DesignToken.BORDER,
            progress_color=DesignToken.GRAY_500
        )
        self.progress.pack(fill="x")
        self.progress.set(0)

    def create_reconstruct_tab(self):
        """Create the RISO to Video reconstruction tab."""
        tab = self.tab_reconstruct

        # ═══════════════════════════════════════════════════════════
        # SECTION: SCAN INPUT
        # ═══════════════════════════════════════════════════════════
        self.create_section_label(tab, "Scanned Sheets")

        scan_section = ctk.CTkFrame(
            tab, fg_color=DesignToken.CARD, corner_radius=DesignToken.RADIUS_MD)
        scan_section.pack(fill="x", pady=(0, DesignToken.SPACE_LG))

        scan_inner = ctk.CTkFrame(scan_section, fg_color="transparent")
        scan_inner.pack(fill="x", padx=DesignToken.SPACE_MD,
                        pady=DesignToken.SPACE_MD)

        # Row with scan input controls
        scan_row = ctk.CTkFrame(scan_inner, fg_color="transparent")
        scan_row.pack(fill="x")
        scan_row.columnconfigure(1, weight=1)
        scan_row.columnconfigure(3, weight=1)

        # Scans button
        ctk.CTkButton(
            scan_row,
            text="Scans",
            width=70,
            height=32,
            command=self.browse_scans,
            fg_color=DesignToken.BTN,
            hover_color=DesignToken.BTN_HOVER,
            text_color=DesignToken.WHITE,
            corner_radius=DesignToken.RADIUS_SM,
            font=DesignToken.get_font(12)
        ).grid(row=0, column=0, sticky="w")

        # Scan display
        ctk.CTkLabel(
            scan_row,
            textvariable=self.scan_display,
            font=DesignToken.get_font(11),
            text_color=DesignToken.GRAY_400,
            anchor="w"
        ).grid(row=0, column=1, sticky="ew", padx=(DesignToken.SPACE_SM, DesignToken.SPACE_MD))

        # Output button
        ctk.CTkButton(
            scan_row,
            text="Output",
            width=70,
            height=32,
            command=self.browse_recon_output,
            fg_color=DesignToken.BTN,
            hover_color=DesignToken.BTN_HOVER,
            text_color=DesignToken.WHITE,
            corner_radius=DesignToken.RADIUS_SM,
            font=DesignToken.get_font(12)
        ).grid(row=0, column=2, sticky="w")

        # Output folder name
        ctk.CTkLabel(
            scan_row,
            textvariable=self.recon_output_display,
            font=DesignToken.get_font(11),
            text_color=DesignToken.GRAY_400,
            anchor="w"
        ).grid(row=0, column=3, sticky="ew", padx=(DesignToken.SPACE_SM, 0))

        # ═══════════════════════════════════════════════════════════
        # SECTION: GRID SETTINGS
        # ═══════════════════════════════════════════════════════════
        self.create_section_label(tab, "Grid Selection")

        grid_section = ctk.CTkFrame(
            tab, fg_color=DesignToken.CARD, corner_radius=DesignToken.RADIUS_MD)
        grid_section.pack(fill="x", pady=(0, DesignToken.SPACE_LG))

        grid_inner = ctk.CTkFrame(grid_section, fg_color="transparent")
        grid_inner.pack(fill="x", padx=DesignToken.SPACE_MD,
                        pady=DesignToken.SPACE_MD)

        # Grid status indicator
        self.grid_status_frame = ctk.CTkFrame(
            grid_inner, fg_color="transparent")
        self.grid_status_frame.pack(fill="x", pady=(0, DesignToken.SPACE_SM))

        self.grid_status_label = ctk.CTkLabel(
            self.grid_status_frame,
            text="⚠ No grid defined",
            font=DesignToken.get_font(11),
            text_color=DesignToken.GRAY_400
        )
        self.grid_status_label.pack(anchor="w")

        # Edit Grid button - opens interactive grid editor (PRIMARY ACTION)
        self.btn_edit_grid = ctk.CTkButton(
            grid_inner,
            text="✎ DEFINE GRID",
            command=self.open_grid_editor,
            height=40,
            corner_radius=DesignToken.RADIUS_SM,
            fg_color=DesignToken.BTN_PRIMARY,
            hover_color="#2563EB",
            text_color=DesignToken.WHITE,
            font=DesignToken.get_font(12, "bold")
        )
        self.btn_edit_grid.pack(fill="x", pady=(0, DesignToken.SPACE_MD))

        # Quick settings row (rows/cols) - collapsed by default
        self.manual_grid_frame = ctk.CTkFrame(
            grid_inner, fg_color="transparent")
        self.manual_grid_frame.pack(fill="x")
        self.manual_grid_frame.columnconfigure(0, weight=1)
        self.manual_grid_frame.columnconfigure(1, weight=1)

        # Rows
        rows_frame = ctk.CTkFrame(
            self.manual_grid_frame, fg_color="transparent")
        rows_frame.grid(row=0, column=0, sticky="ew",
                        padx=(0, DesignToken.SPACE_SM))

        ctk.CTkLabel(
            rows_frame,
            text="ROWS",
            font=DesignToken.get_font(10, "bold"),
            text_color=DesignToken.GRAY_500
        ).pack(anchor="w")

        ctk.CTkEntry(
            rows_frame,
            textvariable=self.recon_rows,
            height=28,
            corner_radius=DesignToken.RADIUS_SM,
            border_width=1,
            border_color=DesignToken.BORDER,
            fg_color=DesignToken.BTN,
            text_color=DesignToken.WHITE,
            font=DesignToken.get_font(12)
        ).pack(fill="x", pady=(DesignToken.SPACE_XS, 0))

        # Columns
        cols_frame = ctk.CTkFrame(
            self.manual_grid_frame, fg_color="transparent")
        cols_frame.grid(row=0, column=1, sticky="ew",
                        padx=(DesignToken.SPACE_SM, 0))

        ctk.CTkLabel(
            cols_frame,
            text="COLUMNS",
            font=DesignToken.get_font(10, "bold"),
            text_color=DesignToken.GRAY_500
        ).pack(anchor="w")

        ctk.CTkEntry(
            cols_frame,
            textvariable=self.recon_cols,
            height=28,
            corner_radius=DesignToken.RADIUS_SM,
            border_width=1,
            border_color=DesignToken.BORDER,
            fg_color=DesignToken.BTN,
            text_color=DesignToken.WHITE,
            font=DesignToken.get_font(12)
        ).pack(fill="x", pady=(DesignToken.SPACE_XS, 0))

        # ═══════════════════════════════════════════════════════════
        # SECTION: OUTPUT SETTINGS
        # ═══════════════════════════════════════════════════════════
        self.create_section_label(tab, "Video Output")

        output_section = ctk.CTkFrame(
            tab, fg_color=DesignToken.CARD, corner_radius=DesignToken.RADIUS_MD)
        output_section.pack(fill="x", pady=(0, DesignToken.SPACE_LG))

        output_inner = ctk.CTkFrame(output_section, fg_color="transparent")
        output_inner.pack(fill="x", padx=DesignToken.SPACE_MD,
                          pady=DesignToken.SPACE_MD)

        output_row = ctk.CTkFrame(output_inner, fg_color="transparent")
        output_row.pack(fill="x")
        output_row.columnconfigure(0, weight=1)
        output_row.columnconfigure(1, weight=1)

        # FPS
        fps_frame = ctk.CTkFrame(output_row, fg_color="transparent")
        fps_frame.grid(row=0, column=0, sticky="ew",
                       padx=(0, DesignToken.SPACE_SM))

        ctk.CTkLabel(
            fps_frame,
            text="FPS",
            font=DesignToken.get_font(10, "bold"),
            text_color=DesignToken.GRAY_500
        ).pack(anchor="w")

        ctk.CTkEntry(
            fps_frame,
            textvariable=self.recon_fps,
            height=28,
            corner_radius=DesignToken.RADIUS_SM,
            border_width=1,
            border_color=DesignToken.BORDER,
            fg_color=DesignToken.BTN,
            text_color=DesignToken.WHITE,
            font=DesignToken.get_font(12)
        ).pack(fill="x", pady=(DesignToken.SPACE_XS, 0))

        # Format dropdown
        format_frame = ctk.CTkFrame(output_row, fg_color="transparent")
        format_frame.grid(row=0, column=1, sticky="ew",
                          padx=(DesignToken.SPACE_SM, 0))

        ctk.CTkLabel(
            format_frame,
            text="FORMAT",
            font=DesignToken.get_font(10, "bold"),
            text_color=DesignToken.GRAY_500
        ).pack(anchor="w")

        ctk.CTkOptionMenu(
            format_frame,
            variable=self.recon_format,
            values=["MP4", "MOV", "GIF", "Image Sequence"],
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

        # Upscale row
        upscale_row = ctk.CTkFrame(output_inner, fg_color="transparent")
        upscale_row.pack(fill="x", pady=(DesignToken.SPACE_SM, 0))

        ctk.CTkLabel(
            upscale_row,
            text="UPSCALE",
            font=DesignToken.get_font(10, "bold"),
            text_color=DesignToken.GRAY_500
        ).pack(anchor="w")

        ctk.CTkOptionMenu(
            upscale_row,
            variable=self.recon_upscale,
            values=["1x (Original)", "2x", "3x", "4x"],
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
        # RECONSTRUCT BUTTON
        # ═══════════════════════════════════════════════════════════
        self.btn_reconstruct = ctk.CTkButton(
            tab,
            text="RECONSTRUCT VIDEO",
            command=self.start_reconstruction,
            height=56,
            corner_radius=DesignToken.RADIUS_SM,
            fg_color=DesignToken.BTN_PRIMARY,
            hover_color=DesignToken.BTN_PRIMARY_HOVER,
            text_color=DesignToken.WHITE,
            font=DesignToken.get_font(16, "bold")
        )
        self.btn_reconstruct.pack(fill="x", pady=(
            DesignToken.SPACE_SM, DesignToken.SPACE_MD))

        # Progress bar - minimal
        self.recon_progress = ctk.CTkProgressBar(
            tab,
            height=4,
            corner_radius=2,
            fg_color=DesignToken.BORDER,
            progress_color=DesignToken.GRAY_500
        )
        self.recon_progress.pack(fill="x")
        self.recon_progress.set(0)

        # Update initial grid status
        self._update_grid_status()

    def _update_grid_status(self):
        """Update the grid status label based on current state."""
        if self.manual_grid_cells:
            # Count total frames across all pages
            total_frames = sum(len(page.get('cells', []))
                               for page in self.manual_grid_cells)
            rows = self.recon_rows.get()
            cols = self.recon_cols.get()
            self.grid_status_label.configure(
                text=f"✓ Grid defined: {rows}×{cols} ({total_frames} frames)",
                text_color="#22C55E"  # Green
            )
            self.btn_edit_grid.configure(text="✎ EDIT GRID")
        else:
            self.grid_status_label.configure(
                text="⚠ No grid defined - click below to define",
                text_color=DesignToken.GRAY_400
            )
            self.btn_edit_grid.configure(text="✎ DEFINE GRID")

    def _on_grid_mode_change(self, mode):
        """Legacy method - kept for compatibility."""
        self._update_grid_status()

    def open_grid_editor(self):
        """Open the interactive grid editor window."""
        if not self.scan_paths:
            messagebox.showwarning(
                "No Scans Selected",
                "Please select scanned sheet images first."
            )
            return

        if not RECONSTRUCT_AVAILABLE:
            messagebox.showerror(
                "Error",
                "Reconstruction module not available."
            )
            return

        # Load images for the grid editor
        try:
            from PIL import Image
            images = []

            # Use cached processors if available
            if self.cached_scan_processors:
                for processor in self.cached_scan_processors:
                    preprocessed = processor.get_preprocessed_images()
                    for img in preprocessed:
                        # Convert numpy array to PIL Image if needed
                        if hasattr(img, 'shape'):
                            import numpy as np
                            if img.dtype != np.uint8:
                                img = (img * 255).astype(np.uint8)
                            pil_img = Image.fromarray(img)
                        else:
                            pil_img = img
                        images.append(pil_img)
            else:
                # Load directly from files
                for path in self.scan_paths:
                    if path.lower().endswith('.pdf'):
                        # Use ScanProcessor for PDF handling
                        processor = ScanProcessor(path)
                        preprocessed = processor.get_preprocessed_images()
                        for img in preprocessed:
                            if hasattr(img, 'shape'):
                                import numpy as np
                                if img.dtype != np.uint8:
                                    img = (img * 255).astype(np.uint8)
                                pil_img = Image.fromarray(img)
                            else:
                                pil_img = img
                            images.append(pil_img)
                    else:
                        img = Image.open(path)
                        if img.mode != 'RGB':
                            img = img.convert('RGB')
                        images.append(img)

            if not images:
                messagebox.showerror("Error", "No images could be loaded.")
                return

            # Get initial grid size from current settings or QR metadata
            try:
                initial_rows = int(self.recon_rows.get())
            except (ValueError, TypeError):
                initial_rows = 5

            try:
                initial_cols = int(self.recon_cols.get())
            except (ValueError, TypeError):
                initial_cols = 6

            # Get spacing from QR metadata if available
            initial_spacing = 10  # default
            if self.cached_qr_settings and self.cached_qr_settings.get('spacing'):
                initial_spacing = self.cached_qr_settings['spacing']

            # Debug: Check if we have existing grid data
            print(
                f"[GUI] Opening grid editor with existing_grid_data: {self.manual_grid_cells is not None}")
            if self.manual_grid_cells:
                print(
                    f"[GUI] Existing grid has {len(self.manual_grid_cells)} page(s)")

            # Create and show the grid editor, passing existing grid if available
            self.grid_editor_window = GridEditorWindow(
                self,  # parent
                images,
                initial_grid=(initial_rows, initial_cols),
                initial_spacing=initial_spacing,
                existing_grid_data=self.manual_grid_cells,  # Restore previous grid
                callback=self._on_grid_editor_apply
            )

        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Failed to open grid editor:\n{str(e)}"
            )
            import traceback
            traceback.print_exc()

    def _on_grid_editor_apply(self, grid_data):
        """Callback when user applies the grid in the editor.

        Args:
            grid_data: List of dicts with:
                - 'page_index': int
                - 'cells': list of (x, y, w, h) tuples
                - 'rows': int
                - 'cols': int
        """
        self.manual_grid_cells = grid_data
        self.grid_editor_window = None

        # Update UI to show grid has been set
        if grid_data:
            rows = grid_data[0].get('rows', '?')
            cols = grid_data[0].get('cols', '?')

            # Update rows/cols entries
            self.recon_rows.set(str(rows))
            self.recon_cols.set(str(cols))

            total_cells = sum(len(page['cells']) for page in grid_data)
            print(
                f"[Grid Editor] Applied grid: {len(grid_data)} page(s), {total_cells} total cells")

        # Update the grid status display
        self._update_grid_status()

    def browse_scans(self):
        """Browse for scanned contact sheet images."""
        files = filedialog.askopenfilenames(
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.tiff *.tif *.bmp"),
                ("PDF Files", "*.pdf"),
                ("All Files", "*.*")
            ]
        )
        if files:
            self.scan_paths = list(files)

            # Clear cached data from previous selection
            self.cached_scan_processors = []
            self.cached_qr_settings = None
            self.manual_grid_cells = None

            # Update grid status
            self._update_grid_status()

            if len(files) == 1:
                self.scan_display.set(os.path.basename(files[0]))
            else:
                self.scan_display.set(f"{len(files)} files selected")

            # Start background thread to detect QR metadata
            if RECONSTRUCT_AVAILABLE:
                threading.Thread(
                    target=self._detect_qr_metadata_async,
                    args=(list(files),),
                    daemon=True
                ).start()

    def _detect_qr_metadata_async(self, file_paths):
        """Background thread to detect QR metadata from scanned files."""
        print(
            f"[QR DEBUG] Starting async QR detection for {len(file_paths)} file(s)")
        try:
            detected_settings = None
            processors = []

            for scan_path in file_paths:
                print(f"[QR DEBUG] Processing: {scan_path}")
                try:
                    processor = ScanProcessor(scan_path)
                    processors.append(processor)
                    print(
                        f"[QR DEBUG] Loaded {len(processor.images)} image(s)")
                    print(f"[QR DEBUG] Metadata list: {processor.metadata}")
                    print(
                        f"[QR DEBUG] Has metadata: {processor.has_metadata()}")

                    if not detected_settings and processor.has_metadata():
                        settings = processor.get_combined_settings()
                        print(f"[QR DEBUG] Combined settings: {settings}")
                        if settings:
                            detected_settings = settings
                except Exception as e:
                    import traceback
                    print(f"[QR DEBUG] Error scanning {scan_path} for QR: {e}")
                    traceback.print_exc()
                    continue

            # Cache the processors and settings for later use (avoids re-scanning)
            self.cached_scan_processors = processors
            self.cached_qr_settings = detected_settings
            print(
                f"[QR DEBUG] Cached {len(processors)} processor(s), settings: {detected_settings}")

            if detected_settings:
                print(
                    f"[QR DEBUG] Applying settings to UI: {detected_settings}")
                # Update UI on main thread
                self.after(
                    0, lambda s=detected_settings: self._apply_detected_settings(s))
            else:
                print("[QR DEBUG] No settings detected from any file")

        except Exception as e:
            import traceback
            print(f"[QR DEBUG] Error in QR detection thread: {e}")
            traceback.print_exc()

    def _apply_detected_settings(self, settings):
        """Apply detected QR settings to the UI fields."""
        updates_made = []

        # Update rows
        if settings.get('rows'):
            self.recon_rows.set(str(settings['rows']))
            updates_made.append(f"Rows: {settings['rows']}")

        # Update columns
        if settings.get('cols'):
            self.recon_cols.set(str(settings['cols']))
            updates_made.append(f"Columns: {settings['cols']}")

        # Update FPS
        if settings.get('fps'):
            self.recon_fps.set(str(settings['fps']))
            updates_made.append(f"FPS: {settings['fps']}")

        # Switch to Manual mode since we have specific grid settings
        if settings.get('rows') and settings.get('cols'):
            self.grid_mode.set("Manual")
            self._on_grid_mode_change("Manual")

        # Update the scan display to show QR was detected
        if updates_made:
            current_display = self.scan_display.get()
            self.scan_display.set(f"{current_display} ✓ QR")

            # Show brief notification
            print(f"QR Metadata detected: {', '.join(updates_made)}")

    def browse_recon_output(self):
        """Browse for reconstruction output directory."""
        d = filedialog.askdirectory()
        if d:
            self.recon_output_path.set(d)
            self.recon_output_display.set(
                os.path.basename(d) if os.path.basename(d) else d)

    def start_reconstruction(self):
        """Start the RISO-to-Video reconstruction process."""
        if not self.scan_paths:
            messagebox.showerror(
                "Error", "Please select scanned sheet images.")
            return

        if not RECONSTRUCT_AVAILABLE:
            messagebox.showerror(
                "Error",
                "Reconstruction module not available.\n"
                "Please ensure all dependencies are installed."
            )
            return

        self.btn_reconstruct.configure(state="disabled", text="PROCESSING...")
        self.recon_progress.set(0)
        self.recon_progress.start()

        threading.Thread(target=self.run_reconstruction, daemon=True).start()

    def run_reconstruction(self):
        """Run the reconstruction process in a background thread."""
        try:
            output_dir = self.recon_output_path.get()

            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            # Parse settings (may be overridden by QR metadata)
            try:
                fps = float(self.recon_fps.get())
            except ValueError:
                raise ValueError("Invalid FPS. Please enter a number.")

            rows = None
            cols = None
            if self.grid_mode.get() == "Manual":
                try:
                    rows = int(self.recon_rows.get())
                    cols = int(self.recon_cols.get())
                except ValueError:
                    raise ValueError(
                        "Invalid rows/columns. Please enter numbers.")

            all_frames = []
            qr_settings_applied = False

            # Use cached processors if available (from background QR scan)
            # This avoids re-scanning files for QR metadata
            if self.cached_scan_processors and len(self.cached_scan_processors) == len(self.scan_paths):
                print(
                    "[Reconstruct] Using cached ScanProcessor objects (no re-scan needed)")
                processors = self.cached_scan_processors
            else:
                # Fall back to creating new processors if cache is empty/stale
                print("[Reconstruct] Creating new ScanProcessor objects")
                processors = [ScanProcessor(scan_path)
                              for scan_path in self.scan_paths]

            # Check for QR metadata from cached settings or first processor
            if self.cached_qr_settings:
                qr_settings = self.cached_qr_settings
                if qr_settings.get('rows') and qr_settings.get('cols'):
                    rows = qr_settings['rows']
                    cols = qr_settings['cols']
                    qr_settings_applied = True
                    print(
                        f"Using cached QR metadata: {rows} rows × {cols} cols")
                if qr_settings.get('fps'):
                    fps = qr_settings['fps']
                    print(f"Using cached QR metadata FPS: {fps}")

            # Process each scan using (cached) processors
            page_counter = 0  # Track global page index for manual grid lookup

            for processor in processors:
                scans = processor.get_preprocessed_images()

                for idx, scan_image in enumerate(scans):
                    # Check if we have manually selected grid cells for this page
                    manual_cells = None
                    manual_grid_info = None
                    if self.manual_grid_cells:
                        for page_data in self.manual_grid_cells:
                            if page_data.get('page_index') == page_counter:
                                manual_cells = page_data.get('cells', [])
                                manual_grid_info = page_data
                                print(
                                    f"[Reconstruct] Using {len(manual_cells)} manually selected cells for page {page_counter + 1}")
                                break

                    if manual_cells and manual_grid_info:
                        # Create DetectedGrid from manually selected cells
                        # Each cell is (x, y, w, h)
                        grid_cells = []
                        num_rows = manual_grid_info.get('rows', 1)
                        num_cols = manual_grid_info.get('cols', 1)

                        for i, (x, y, w, h) in enumerate(manual_cells):
                            row_idx = i // num_cols
                            col_idx = i % num_cols
                            grid_cells.append(GridCell(
                                x=int(x), y=int(y),
                                width=int(w), height=int(h),
                                row=row_idx, col=col_idx
                            ))

                        # Calculate average cell size and origin
                        if grid_cells:
                            avg_width = sum(
                                c.width for c in grid_cells) // len(grid_cells)
                            avg_height = sum(
                                c.height for c in grid_cells) // len(grid_cells)
                            origin_x = min(c.x for c in grid_cells)
                            origin_y = min(c.y for c in grid_cells)
                        else:
                            avg_width = avg_height = 100
                            origin_x = origin_y = 0

                        grid = DetectedGrid(
                            cells=grid_cells,
                            rows=num_rows,
                            cols=num_cols,
                            cell_width=avg_width,
                            cell_height=avg_height,
                            origin=(origin_x, origin_y),
                            spacing_x=0,
                            spacing_y=0,
                            frame_count=len(grid_cells)
                        )
                    else:
                        # Fall back to automatic/metadata-based detection
                        # Check individual page metadata
                        page_metadata = processor.metadata[idx] if idx < len(
                            processor.metadata) else None

                        # Use page-specific metadata if available
                        page_rows = rows
                        page_cols = cols
                        page_frame_count = None
                        page_cell_width = None
                        page_cell_height = None
                        page_margin = None
                        page_spacing = None

                        if page_metadata:
                            page_rows = page_metadata.rows or rows
                            page_cols = page_metadata.cols or cols
                            page_frame_count = page_metadata.frame_count
                            # Get exact cell dimensions if available
                            page_cell_width = page_metadata.cell_width
                            page_cell_height = page_metadata.cell_height
                            page_margin = page_metadata.margin
                            page_spacing = page_metadata.spacing

                            if page_cell_width and page_cell_height:
                                print(f"[Reconstruct] Page {idx+1}: {page_rows}x{page_cols}, "
                                      f"{page_frame_count} frames, cell={page_cell_width}x{page_cell_height}, "
                                      f"margin={page_margin}, spacing={page_spacing}")
                            else:
                                print(
                                    f"[Reconstruct] Page {idx+1}: {page_rows}x{page_cols}, {page_frame_count} frames")

                        # Detect grid - pass all available metadata for precise detection
                        if page_rows and page_cols:
                            grid = GridDetector.detect(
                                scan_image,
                                method="manual",
                                rows=page_rows,
                                cols=page_cols,
                                frame_count=page_frame_count,
                                cell_width=page_cell_width,
                                cell_height=page_cell_height,
                                margin=page_margin,
                                spacing=page_spacing
                            )
                        elif self.grid_mode.get() == "Manual" and rows and cols:
                            grid = GridDetector.detect(
                                scan_image,
                                method="manual",
                                rows=rows,
                                cols=cols
                            )
                        else:
                            grid = GridDetector.detect(
                                scan_image, method="auto")

                    # Extract frames
                    extractor = FrameExtractor(
                        border_crop=5,
                        sharpen=False,
                        preserve_riso_colors=True
                    )
                    frames = extractor.extract_frames(scan_image, grid)
                    print(
                        f"[Reconstruct] Extracted {len(frames)} frames from page {page_counter + 1}")
                    all_frames.extend(frames)

                    # Increment page counter
                    page_counter += 1

            if not all_frames:
                raise ValueError("No frames extracted from scans.")

            # Show notification if QR settings were used
            if qr_settings_applied:
                self.after(
                    0, lambda: self._show_qr_notification(rows, cols, fps))

            # Assemble video
            assembler = VideoAssembler(all_frames)
            assembler.set_fps(fps)

            # Apply upscale factor
            upscale_str = self.recon_upscale.get()
            upscale_factor = 1
            if upscale_str.startswith("2x"):
                upscale_factor = 2
            elif upscale_str.startswith("3x"):
                upscale_factor = 3
            elif upscale_str.startswith("4x"):
                upscale_factor = 4

            if upscale_factor > 1:
                assembler.set_upscale(upscale_factor)

            # Determine output format
            output_format = self.recon_format.get()

            if output_format == "GIF":
                output_path = os.path.join(output_dir, "reconstructed.gif")
                assembler.export_gif(output_path, fps=fps)
            elif output_format == "Image Sequence":
                seq_dir = os.path.join(output_dir, "frames")
                assembler.export_image_sequence(seq_dir)
                output_path = seq_dir
            else:
                ext = "mp4" if output_format == "MP4" else "mov"
                output_path = os.path.join(output_dir, f"reconstructed.{ext}")
                assembler.export(output_path, fps=fps)

            self.after(0, lambda p=output_path: self.on_recon_success(p))

        except Exception as e:
            error_msg = str(e)
            self.after(0, lambda msg=error_msg: self.on_recon_error(msg))

    def _show_qr_notification(self, rows, cols, fps):
        """Show a notification that QR settings were detected and applied."""
        messagebox.showinfo(
            "QR Metadata Detected",
            f"Settings from embedded QR code applied:\n\n"
            f"Grid: {rows} rows × {cols} columns\n"
            f"FPS: {fps}"
        )

    def on_recon_success(self, output_path):
        """Handle successful reconstruction."""
        self.recon_progress.stop()
        self.recon_progress.set(1)
        self.btn_reconstruct.configure(
            state="normal", text="RECONSTRUCT VIDEO")

        import platform
        import subprocess

        try:
            if platform.system() == 'Darwin':
                if os.path.isdir(output_path):
                    subprocess.call(('open', output_path))
                else:
                    subprocess.call(('open', output_path))
            elif platform.system() == 'Windows':
                os.startfile(output_path)
            else:
                subprocess.call(('xdg-open', output_path))
        except Exception as e:
            print(f"Could not open output: {e}")

        messagebox.showinfo(
            "Complete",
            f"Video reconstructed successfully!\n\n{os.path.basename(output_path)}"
        )

    def on_recon_error(self, msg):
        """Handle reconstruction error."""
        self.recon_progress.stop()
        self.recon_progress.set(0)
        self.btn_reconstruct.configure(
            state="normal", text="RECONSTRUCT VIDEO")
        messagebox.showerror("Error", msg)

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
            fps = processor.fps if hasattr(processor, 'fps') else None
            processor.close()

            if not frames:
                raise ValueError(
                    "No frames extracted. Check interval or video.")

            # 2. Layout
            dpi = 300
            layout = LayoutEngine(paper_size="LETTER", dpi=dpi)
            sheets = layout.create_sheets(frames, columns=cols)
            thumb_size = layout.get_thumbnail_size()

            # Calculate actual rows per sheet based on printable area and thumb size
            if thumb_size:
                printable_height = layout.page_height - (2 * layout.margin)
                # This is the max rows that can fit on a page
                max_rows_per_page = int((printable_height + layout.spacing) /
                                        (thumb_size[1] + layout.spacing))
            else:
                max_rows_per_page = 6  # fallback

            # Calculate frames per full sheet
            frames_per_full_sheet = max_rows_per_page * cols

            # Initialize metadata encoder for QR codes
            try:
                metadata_encoder = MetadataEncoder(
                    # Larger QR for reliable scanning (150px at 300dpi = 0.5 inch)
                    qr_size=150,
                    position="bottom-right",
                    margin=30
                )
                qr_available = True
            except:
                qr_available = False

            self.generated_sheets = []

            # 3. Save & Separate
            composite_pages = []
            channel_pages = []
            effect_name = self.selected_effect.get()

            # Track frame positions across sheets
            frame_start = 0
            total_frames = len(frames)

            for i, sheet in enumerate(sheets):
                # Calculate how many frames remain for this sheet
                remaining_frames = total_frames - frame_start

                # Calculate frames on this sheet (can't exceed what fits on a full sheet)
                frames_on_sheet = min(frames_per_full_sheet, remaining_frames)

                # Calculate actual rows used on this sheet
                actual_rows = (frames_on_sheet + cols -
                               1) // cols  # Ceiling division

                # Create metadata for this sheet
                sheet_metadata = None
                if qr_available:
                    sheet_metadata = SheetMetadata(
                        page_number=i + 1,
                        total_pages=len(sheets),
                        rows=actual_rows,
                        cols=cols,
                        frame_start=frame_start,
                        frame_count=frames_on_sheet,
                        fps=fps,
                        # Include exact cell dimensions for precise reconstruction
                        cell_width=thumb_size[0] if thumb_size else None,
                        cell_height=thumb_size[1] if thumb_size else None,
                        margin=layout.margin,
                        spacing=layout.spacing
                    )
                    # Add QR code to composite sheet
                    sheet = metadata_encoder.add_qr_code(
                        sheet, sheet_metadata, use_compact=True)

                frame_start += frames_on_sheet

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

                    # Add QR code to Black channel (will be visible on final print)
                    if qr_available and sheet_metadata:
                        # Convert to RGB to add QR, then back to grayscale
                        img_black_rgb = img_black.convert('RGB')
                        img_black_rgb = metadata_encoder.add_qr_code(
                            img_black_rgb, sheet_metadata, use_compact=True)
                        img_black = img_black_rgb.convert('L')

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
