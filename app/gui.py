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


class IconGenerator:
    @staticmethod
    def create_video_icon(size=(20, 20), color="white"):
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Film strip style
        draw.rectangle([2, 4, 18, 16], outline=color, width=2)
        draw.polygon([8, 6, 8, 14, 14, 10], fill=color)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)

    @staticmethod
    def create_folder_icon(size=(20, 20), color="white"):
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Folder shape
        draw.polygon([2, 4, 8, 4, 10, 6, 18, 6, 18, 16, 2, 16],
                     outline=color, width=2)
        draw.line([2, 8, 18, 8], fill=color, width=1)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)

    @staticmethod
    def create_play_icon(size=(20, 20), color="white"):
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Play triangle
        draw.polygon([6, 4, 6, 16, 16, 10], fill=color)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)


class RisoApp(ctk.CTk):
    COLOR_BG = "#181818"
    COLOR_PRIMARY = "#8FA31E"
    COLOR_HOVER = "#556B2F"

    def __init__(self):
        super().__init__()

        self.title("Video to RISO")
        self.geometry("500x700")
        self.resizable(False, False)
        self.configure(fg_color=self.COLOR_BG)

        # Set App Icon
        try:
            icon_path = self.resource_path("icons/appstore.png")
            if os.path.exists(icon_path):
                # Set window icon
                icon_img = Image.open(icon_path)
                self.iconphoto(True, ImageTk.PhotoImage(icon_img))
        except Exception as e:
            print(f"Failed to load icon: {e}")

        self.grid_columnconfigure(0, weight=1)

        # --- Variables ---
        self.video_path = ctk.StringVar()
        self.video_name_display = ctk.StringVar(value="No file selected")

        default_out = os.path.join(tempfile.gettempdir(), "videoToRISO_output")
        self.output_path = ctk.StringVar(value=default_out)
        self.output_name_display = ctk.StringVar(
            value=os.path.basename(default_out) or default_out)

        self.columns = ctk.IntVar(value=5)
        self.interval = ctk.StringVar(value="0.5")
        self.selected_effect = ctk.StringVar(value="None")

        self.use_red = ctk.BooleanVar(value=True)
        self.use_green = ctk.BooleanVar(value=True)
        self.use_blue = ctk.BooleanVar(value=True)

        # Icons
        self.icon_video = IconGenerator.create_video_icon()
        self.icon_folder = IconGenerator.create_folder_icon()
        self.icon_play = IconGenerator.create_play_icon()

        # --- UI ---
        self.create_ui()

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def create_ui(self):
        # Main Container with padding
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # File Selection Card
        card_file = ctk.CTkFrame(main_container)
        card_file.pack(pady=(0, 15), fill="x")

        ctk.CTkLabel(card_file, text="Video Source", font=(
            "Arial", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 5))

        file_row = ctk.CTkFrame(card_file, fg_color="transparent")
        file_row.pack(fill="x", padx=10, pady=(0, 15))

        ctk.CTkButton(file_row, text="Select Video", image=self.icon_video, compound="left", width=140,
                      command=self.browse_file, fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER).pack(side="left", padx=5)

        ctk.CTkLabel(file_row, textvariable=self.video_name_display,
                     text_color="gray").pack(side="left", padx=10)

        # Output Selection Card
        card_out = ctk.CTkFrame(main_container)
        card_out.pack(pady=(0, 15), fill="x")

        ctk.CTkLabel(card_out, text="Output Location", font=(
            "Arial", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 5))

        out_row = ctk.CTkFrame(card_out, fg_color="transparent")
        out_row.pack(fill="x", padx=10, pady=(0, 15))

        ctk.CTkButton(out_row, text="Select Folder", image=self.icon_folder, compound="left", width=140,
                      command=self.browse_output, fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER).pack(side="left", padx=5)

        ctk.CTkLabel(out_row, textvariable=self.output_name_display,
                     text_color="gray").pack(side="left", padx=10)

        # Settings Card
        card_settings = ctk.CTkFrame(main_container)
        card_settings.pack(pady=(0, 15), fill="x")
        ctk.CTkLabel(card_settings, text="Configuration", font=(
            "Arial", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))

        # Grid layout for settings
        settings_grid = ctk.CTkFrame(card_settings, fg_color="transparent")
        settings_grid.pack(fill="x", padx=10, pady=(0, 15))

        # Columns
        ctk.CTkLabel(settings_grid, text="Columns:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5)
        ctk.CTkSlider(settings_grid, from_=1, to=10, number_of_steps=9, variable=self.columns,
                      button_color=self.COLOR_PRIMARY, progress_color=self.COLOR_PRIMARY).grid(row=0, column=1, sticky="ew", padx=5)
        ctk.CTkLabel(settings_grid, textvariable=self.columns,
                     width=20).grid(row=0, column=2, padx=5)

        # Interval
        ctk.CTkLabel(settings_grid, text="Interval (s):").grid(
            row=1, column=0, sticky="w", padx=5, pady=5)
        ctk.CTkEntry(settings_grid, textvariable=self.interval,
                     width=60).grid(row=1, column=1, sticky="w", padx=5)

        # Effects
        ctk.CTkLabel(settings_grid, text="Effect:").grid(
            row=2, column=0, sticky="w", padx=5, pady=5)
        ctk.CTkOptionMenu(settings_grid, variable=self.selected_effect, values=ImageEffects.OPTIONS,
                          fg_color=self.COLOR_PRIMARY, button_color=self.COLOR_HOVER).grid(row=2, column=1, sticky="w", padx=5)

        settings_grid.columnconfigure(1, weight=1)

        # Channels Card
        card_channels = ctk.CTkFrame(main_container)
        card_channels.pack(pady=(0, 15), fill="x")
        ctk.CTkLabel(card_channels, text="RISO Channels", font=(
            "Arial", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))

        grid_ch = ctk.CTkFrame(card_channels, fg_color="transparent")
        grid_ch.pack(padx=10, pady=(0, 15), fill="x")

        # Use grid for even spacing
        grid_ch.columnconfigure((0, 1, 2), weight=1)
        ctk.CTkCheckBox(grid_ch, text="Red", variable=self.use_red,
                        fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER).grid(row=0, column=0)
        ctk.CTkCheckBox(grid_ch, text="Green", variable=self.use_green,
                        fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER).grid(row=0, column=1)
        ctk.CTkCheckBox(grid_ch, text="Blue", variable=self.use_blue,
                        fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER).grid(row=0, column=2)

        # Actions
        self.btn_run = ctk.CTkButton(
            main_container, text="Generate Sheets", image=self.icon_play, compound="left",
            command=self.start_generation, height=50, font=("Arial", 16, "bold"),
            fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER)
        self.btn_run.pack(pady=10, fill="x")

        self.progress = ctk.CTkProgressBar(
            main_container, progress_color=self.COLOR_PRIMARY)
        self.progress.pack(pady=(0, 10), fill="x")
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

        self.btn_run.configure(state="disabled")
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
            layout = LayoutEngine(paper_size="LETTER", dpi=300)
            sheets = layout.create_sheets(frames, columns=cols)

            self.generated_sheets = []

            # 3. Save & Separate
            all_pdf_pages = []
            effect_name = self.selected_effect.get()

            for i, sheet in enumerate(sheets):
                # Add Composite to PDF list
                labeled_sheet = layout.add_label(
                    sheet, f"Sheet {i+1} - Composite")
                all_pdf_pages.append(labeled_sheet)

                # Separate channels
                channels = layout.separate_channels(sheet, mode="RGB")

                if self.use_red.get():
                    img_red = ImageEffects.apply_effect(
                        channels['Red'], effect_name)
                    lbl_red = layout.add_label(
                        img_red, f"Sheet {i+1} - Red Channel")
                    all_pdf_pages.append(lbl_red)

                if self.use_green.get():
                    img_green = ImageEffects.apply_effect(
                        channels['Green'], effect_name)
                    lbl_green = layout.add_label(
                        img_green, f"Sheet {i+1} - Green Channel")
                    all_pdf_pages.append(lbl_green)

                if self.use_blue.get():
                    img_blue = ImageEffects.apply_effect(
                        channels['Blue'], effect_name)
                    lbl_blue = layout.add_label(
                        img_blue, f"Sheet {i+1} - Blue Channel")
                    all_pdf_pages.append(lbl_blue)

            # Save single PDF
            pdf_path = None
            if all_pdf_pages:
                pdf_path = os.path.join(output_dir, "output_sheets.pdf")
                all_pdf_pages[0].save(
                    pdf_path, save_all=True, append_images=all_pdf_pages[1:])

            self.after(0, lambda: self.on_success(pdf_path))

        except Exception as e:
            self.after(0, lambda: self.on_error(str(e)))

    def on_success(self, pdf_path):
        self.progress.stop()
        self.progress.set(1)
        self.btn_run.configure(state="normal")

        if pdf_path and os.path.exists(pdf_path):
            # Open the PDF
            import platform
            import subprocess

            try:
                if platform.system() == 'Darwin':       # macOS
                    subprocess.call(('open', pdf_path))
                elif platform.system() == 'Windows':    # Windows
                    os.startfile(pdf_path)
                else:                                   # linux variants
                    subprocess.call(('xdg-open', pdf_path))
            except Exception as e:
                messagebox.showerror("Error", f"Could not open PDF: {e}")
        else:
            messagebox.showinfo(
                "Success", "Process completed, but no PDF was generated.")

    def on_error(self, msg):
        self.progress.stop()
        self.btn_run.configure(state="normal")
        messagebox.showerror("Error", msg)
