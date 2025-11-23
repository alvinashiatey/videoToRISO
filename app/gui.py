import customtkinter as ctk
from tkinter import filedialog, messagebox
import threading
import os
import tempfile
from PIL import Image, ImageTk

from processor import VideoProcessor
from layout import LayoutEngine


class PreviewWindow(ctk.CTkToplevel):
    def __init__(self, image_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Sheet Preview")
        self.geometry("600x800")

        self.image_path = image_path

        # Load and resize image for display
        try:
            pil_img = Image.open(self.image_path)

            # Calculate resize to fit window
            w, h = pil_img.size
            aspect = w / h
            display_h = 750
            display_w = int(display_h * aspect)

            pil_img_small = pil_img.resize(
                (display_w, display_h), Image.Resampling.LANCZOS)
            self.photo_img = ctk.CTkImage(
                light_image=pil_img_small, dark_image=pil_img_small, size=(display_w, display_h))

            self.label = ctk.CTkLabel(self, image=self.photo_img, text="")
            self.label.pack(padx=20, pady=20)
        except Exception as e:
            ctk.CTkLabel(self, text=f"Error loading preview: {e}").pack(
                padx=20, pady=20)


class RisoApp(ctk.CTk):
    COLOR_BG = "#313647"
    COLOR_PRIMARY = "#435663"
    COLOR_HOVER = "#32414b"

    def __init__(self):
        super().__init__()

        self.title("Video to RISO")
        self.geometry("500x700")
        self.configure(fg_color=self.COLOR_BG)

        self.grid_columnconfigure(0, weight=1)

        # --- Variables ---
        self.video_path = ctk.StringVar()
        self.output_path = ctk.StringVar(
            value=os.path.join(tempfile.gettempdir(), "videoToRISO_output"))
        self.columns = ctk.IntVar(value=3)
        self.interval = ctk.StringVar(value="1.0")

        self.use_red = ctk.BooleanVar(value=True)
        self.use_green = ctk.BooleanVar(value=True)
        self.use_blue = ctk.BooleanVar(value=True)

        self.generated_sheets = []  # Store paths of generated sheets

        # --- UI ---
        self.create_ui()

    def create_ui(self):
        # File Selection
        frame_file = ctk.CTkFrame(self)
        frame_file.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(frame_file, text="Video File:").pack(
            anchor="w", padx=10, pady=(10, 0))
        entry_file = ctk.CTkEntry(
            frame_file, textvariable=self.video_path, placeholder_text="Select video file...")
        entry_file.pack(side="left", padx=10, pady=10, fill="x", expand=True)
        ctk.CTkButton(frame_file, text="Browse", width=80, command=self.browse_file, fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER).pack(
            side="right", padx=10, pady=10)

        # Output Selection
        frame_out = ctk.CTkFrame(self)
        frame_out.pack(pady=10, padx=20, fill="x")

        ctk.CTkLabel(frame_out, text="Output Directory:").pack(
            anchor="w", padx=10, pady=(10, 0))
        entry_out = ctk.CTkEntry(frame_out, textvariable=self.output_path)
        entry_out.pack(side="left", padx=10, pady=10, fill="x", expand=True)
        ctk.CTkButton(frame_out, text="Browse", width=80, command=self.browse_output, fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER).pack(
            side="right", padx=10, pady=10)

        # Settings
        frame_settings = ctk.CTkFrame(self)
        frame_settings.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(frame_settings, text="Settings", font=(
            "Arial", 14, "bold")).pack(anchor="w", padx=10, pady=10)

        # Columns
        frame_cols = ctk.CTkFrame(frame_settings, fg_color="transparent")
        frame_cols.pack(fill="x", padx=10)
        ctk.CTkLabel(frame_cols, text="Columns:").pack(side="left")
        ctk.CTkSlider(frame_cols, from_=1, to=10, number_of_steps=9, variable=self.columns, button_color=self.COLOR_PRIMARY, progress_color=self.COLOR_PRIMARY).pack(
            side="left", padx=10, fill="x", expand=True)
        ctk.CTkLabel(frame_cols, textvariable=self.columns,
                     width=20).pack(side="right")

        # Interval
        frame_int = ctk.CTkFrame(frame_settings, fg_color="transparent")
        frame_int.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(frame_int, text="Capture Interval (sec):").pack(
            side="left")
        ctk.CTkEntry(frame_int, textvariable=self.interval,
                     width=60).pack(side="right")

        # Channels
        frame_channels = ctk.CTkFrame(self)
        frame_channels.pack(pady=10, padx=20, fill="x")
        ctk.CTkLabel(frame_channels, text="RISO Channels (RGB)", font=(
            "Arial", 14, "bold")).pack(anchor="w", padx=10, pady=10)

        grid_ch = ctk.CTkFrame(frame_channels, fg_color="transparent")
        grid_ch.pack(padx=10, pady=(0, 10))
        ctk.CTkCheckBox(grid_ch, text="Red", variable=self.use_red, fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER).pack(
            side="left", padx=10)
        ctk.CTkCheckBox(grid_ch, text="Green", variable=self.use_green, fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER).pack(
            side="left", padx=10)
        ctk.CTkCheckBox(grid_ch, text="Blue", variable=self.use_blue, fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER).pack(
            side="left", padx=10)

        # Actions
        self.btn_run = ctk.CTkButton(
            self, text="Generate Sheets", command=self.start_generation, height=40, font=("Arial", 16), fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER)
        self.btn_run.pack(pady=20, padx=20, fill="x")

        self.progress = ctk.CTkProgressBar(
            self, progress_color=self.COLOR_PRIMARY)
        self.progress.pack(pady=(0, 20), padx=20, fill="x")
        self.progress.set(0)

        self.btn_preview = ctk.CTkButton(
            self, text="View Last Generated Sheet", command=self.open_preview, state="disabled", fg_color=self.COLOR_PRIMARY, hover_color=self.COLOR_HOVER)
        self.btn_preview.pack(pady=(0, 20), padx=20)

    def browse_file(self):
        f = filedialog.askopenfilename(
            filetypes=[("Video Files", "*.mp4 *.mov *.avi *.mkv")])
        if f:
            self.video_path.set(f)

    def browse_output(self):
        d = filedialog.askdirectory()
        if d:
            self.output_path.set(d)

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
            for i, sheet in enumerate(sheets):
                base_name = f"sheet_{i}"

                # Save composite (optional, but good for preview)
                comp_path = os.path.join(
                    output_dir, f"{base_name}_composite.png")
                sheet.save(comp_path)
                self.generated_sheets.append(comp_path)

                # Channels
                channels = layout.separate_channels(sheet, mode="RGB")
                if self.use_red.get():
                    channels['Red'].save(os.path.join(
                        output_dir, f"{base_name}_red.png"))
                if self.use_green.get():
                    channels['Green'].save(os.path.join(
                        output_dir, f"{base_name}_green.png"))
                if self.use_blue.get():
                    channels['Blue'].save(os.path.join(
                        output_dir, f"{base_name}_blue.png"))

            self.after(0, self.on_success)

        except Exception as e:
            self.after(0, lambda: self.on_error(str(e)))

    def on_success(self):
        self.progress.stop()
        self.progress.set(1)
        self.btn_run.configure(state="normal")
        self.btn_preview.configure(state="normal")
        messagebox.showinfo(
            "Success", f"Generated {len(self.generated_sheets)} sheets.")

        # Auto open preview of first sheet
        if self.generated_sheets:
            self.open_preview()

    def on_error(self, msg):
        self.progress.stop()
        self.btn_run.configure(state="normal")
        messagebox.showerror("Error", msg)

    def open_preview(self):
        if self.generated_sheets:
            PreviewWindow(self.generated_sheets[0], self)
