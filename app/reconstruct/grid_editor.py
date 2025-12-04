"""
Interactive Grid Selection Editor

A dedicated window for manually selecting and adjusting the grid
on scanned contact sheets for video reconstruction.
"""

import customtkinter as ctk
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import messagebox
from typing import Optional, List, Dict, Tuple, Set
from dataclasses import dataclass


@dataclass
class CellBounds:
    """Represents the bounds of a single grid cell."""
    row: int
    col: int
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1


class GridEditorWindow(ctk.CTkToplevel):
    """
    Interactive window for manual grid selection on scanned images.

    Features:
    - Pan and zoom the scanned image
    - Draw a grid rectangle over the thumbnails
    - Adjust rows and columns
    - Preview extracted frames
    - Fine-tune individual cell boundaries
    - Navigate between multiple scanned pages
    """

    def __init__(self, parent, scan_images: List[Image.Image],
                 initial_grid: Tuple[int, int] = (6, 4),
                 initial_spacing: int = 10,
                 existing_grid_data: Optional[List[Dict]] = None,
                 callback: Optional[callable] = None):
        """
        Initialize the grid editor.

        Args:
            parent: Parent window
            scan_images: List of PIL Images of scanned contact sheets
            initial_grid: Tuple of (rows, cols) for initial grid
            initial_spacing: Initial gap between cells in pixels
            existing_grid_data: Previously saved grid data to restore
            callback: Callback function when grid is confirmed
        """
        super().__init__(parent)

        self.title("Grid Selection Editor")
        self.geometry("1400x900")
        self.minsize(1000, 700)

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Store references - handle both single image and list
        if isinstance(scan_images, list):
            self.scan_images = [img.convert("RGB") for img in scan_images]
        else:
            self.scan_images = [scan_images.convert("RGB")]

        self.current_page = 0
        self.scan_image = self.scan_images[0]  # Current active image
        self.original_size = self.scan_image.size

        self.rows = initial_grid[0]
        self.cols = initial_grid[1]
        self.spacing = initial_spacing  # Gap between cells in pixels
        self.callback = callback

        # Per-page grid state
        self.page_grids: Dict[int, Tuple[float, float, float, float]] = {}
        self.page_cells: Dict[int, List[CellBounds]] = {}

        # Current page grid state
        self.grid_rect: Optional[Tuple[float, float, float, float]] = None
        self.result_cells: Optional[List[CellBounds]] = None
        self.confirmed = False

        # Restore existing grid data if provided (after initializing grid state)
        if existing_grid_data:
            self._restore_grid_data(existing_grid_data)

        # Drawing state
        self.draw_start: Optional[Tuple[float, float]] = None
        self.is_drawing = False

        # View state
        self.zoom_level = 1.0
        self.pan_offset = [0, 0]
        self.current_tool = "draw"  # draw, pan, adjust
        self.pan_start: Optional[Tuple[int, int]] = None
        self.space_pan_active = False
        self.previous_tool: Optional[str] = None

        # Handle selection for adjustment
        self.selected_handle: Optional[str] = None
        self.handle_size = 8

        # Image cache
        self.photo_image: Optional[ImageTk.PhotoImage] = None
        self.preview_photos: List[ImageTk.PhotoImage] = []

        # Frame preview pagination and exclusion
        self.preview_page = 0  # Will be set in _build_bottom_panel too
        self.previews_per_page = 12  # Will be set in _build_bottom_panel too
        # Selected frames for multi-selection (shift-click)
        self.selected_frames: Set[int] = set()
        # For shift-click range selection
        self.last_selected_frame: Optional[int] = None
        # Global frame indices to exclude
        self.excluded_frames: Set[int] = set()

        # Undo state
        self.undo_stack = []
        self.is_undoing = False
        self.temp_state = None

        # Build UI
        self._build_ui()
        self._bind_events()

        # Update UI fields if we restored grid data
        if existing_grid_data:
            self.rows_var.set(str(self.rows))
            self.cols_var.set(str(self.cols))
            self.spacing_var.set(str(self.spacing))

        # Initial fit to view and redraw after window is shown
        self.after(100, self._initial_display)

    def _build_ui(self):
        """Construct the editor UI."""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Top toolbar
        self._build_toolbar()

        # Main canvas area
        self._build_canvas()

        # Bottom panel with preview and actions
        self._build_bottom_panel()

    def _initial_display(self):
        """Initial display setup after window is shown."""
        self.fit_to_view()
        # Update preview and info if we have existing grid
        if self.result_cells:
            self._update_preview()
            self._update_info()

    def _build_toolbar(self):
        """Build the top toolbar (Swiss Grid Style)."""
        toolbar = ctk.CTkFrame(
            self, height=50, fg_color="#1E1E1E", corner_radius=0)
        toolbar.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        toolbar.grid_columnconfigure(10, weight=1)  # Spacer

        # --- Tools Section ---
        tool_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        tool_frame.pack(side="left", padx=15, pady=10)

        ctk.CTkLabel(
            tool_frame, text="TOOLS", font=("Helvetica", 10, "bold"),
            text_color="#666666"
        ).pack(side="left", padx=(0, 10))

        self.draw_btn = ctk.CTkButton(
            tool_frame, text="DRAW", width=80, height=28,
            command=lambda: self._set_tool("draw"),
            fg_color="#333333", hover_color="#444444",
            font=("Helvetica", 11, "bold"), corner_radius=0
        )
        self.draw_btn.pack(side="left", padx=2)

        self.pan_btn = ctk.CTkButton(
            tool_frame, text="PAN", width=60, height=28,
            command=lambda: self._set_tool("pan"),
            fg_color="transparent", hover_color="#333333",
            border_width=1, border_color="#333333",
            font=("Helvetica", 11, "bold"), corner_radius=0
        )
        self.pan_btn.pack(side="left", padx=2)

        self.adjust_btn = ctk.CTkButton(
            tool_frame, text="ADJUST", width=70, height=28,
            command=lambda: self._set_tool("adjust"),
            fg_color="transparent", hover_color="#333333",
            border_width=1, border_color="#333333",
            font=("Helvetica", 11, "bold"), corner_radius=0
        )
        self.adjust_btn.pack(side="left", padx=2)

        # Separator
        sep1 = ctk.CTkFrame(toolbar, width=1, height=24, fg_color="#333333")
        sep1.pack(side="left", padx=15)

        # --- Grid Settings Section ---
        settings_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        settings_frame.pack(side="left", padx=0)

        ctk.CTkLabel(
            settings_frame, text="GRID", font=("Helvetica", 10, "bold"),
            text_color="#666666"
        ).pack(side="left", padx=(0, 10))

        # Rows
        ctk.CTkLabel(settings_frame, text="R:", font=(
            "Helvetica", 11, "bold"), text_color="#888888").pack(side="left", padx=(0, 2))
        self.rows_var = ctk.StringVar(value=str(self.rows))
        self.rows_entry = ctk.CTkEntry(
            settings_frame, width=36, height=28, textvariable=self.rows_var,
            font=("Helvetica", 12), corner_radius=0, border_width=1, border_color="#333333", fg_color="#252525"
        )
        self.rows_entry.pack(side="left", padx=(0, 8))

        # Cols
        ctk.CTkLabel(settings_frame, text="C:", font=(
            "Helvetica", 11, "bold"), text_color="#888888").pack(side="left", padx=(0, 2))
        self.cols_var = ctk.StringVar(value=str(self.cols))
        self.cols_entry = ctk.CTkEntry(
            settings_frame, width=36, height=28, textvariable=self.cols_var,
            font=("Helvetica", 12), corner_radius=0, border_width=1, border_color="#333333", fg_color="#252525"
        )
        self.cols_entry.pack(side="left", padx=(0, 8))

        # Gap
        ctk.CTkLabel(settings_frame, text="GAP:", font=(
            "Helvetica", 11, "bold"), text_color="#888888").pack(side="left", padx=(0, 2))
        self.spacing_var = ctk.StringVar(value=str(self.spacing))
        self.spacing_entry = ctk.CTkEntry(
            settings_frame, width=36, height=28, textvariable=self.spacing_var,
            font=("Helvetica", 12), corner_radius=0, border_width=1, border_color="#333333", fg_color="#252525"
        )
        self.spacing_entry.pack(side="left", padx=(0, 5))

        update_btn = ctk.CTkButton(
            settings_frame, text="UPDATE", width=60, height=28,
            command=self._update_grid_from_entries,
            fg_color="#333333", hover_color="#444444",
            font=("Helvetica", 11, "bold"), corner_radius=0
        )
        update_btn.pack(side="left", padx=5)

        # Separator
        sep2 = ctk.CTkFrame(toolbar, width=1, height=24, fg_color="#333333")
        sep2.pack(side="left", padx=15)

        # --- Zoom Section ---
        zoom_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        zoom_frame.pack(side="left", padx=0)

        ctk.CTkButton(
            zoom_frame, text="-", width=28, height=28,
            command=self.zoom_out,
            fg_color="transparent", hover_color="#333333",
            border_width=1, border_color="#333333",
            font=("Helvetica", 14), corner_radius=0
        ).pack(side="left", padx=2)

        self.zoom_label = ctk.CTkLabel(
            zoom_frame, text="100%", width=45,
            font=("Helvetica", 11, "bold"), text_color="#888888"
        )
        self.zoom_label.pack(side="left", padx=2)

        ctk.CTkButton(
            zoom_frame, text="+", width=28, height=28,
            command=self.zoom_in,
            fg_color="transparent", hover_color="#333333",
            border_width=1, border_color="#333333",
            font=("Helvetica", 14), corner_radius=0
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            zoom_frame, text="FIT", width=40, height=28,
            command=self.fit_to_view,
            fg_color="transparent", hover_color="#333333",
            text_color="#888888",
            font=("Helvetica", 10, "bold"), corner_radius=0
        ).pack(side="left", padx=5)

        # --- Page Navigation (if needed) ---
        if len(self.scan_images) > 1:
            sep3 = ctk.CTkFrame(
                toolbar, width=1, height=24, fg_color="#333333")
            sep3.pack(side="left", padx=15)

            page_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
            page_frame.pack(side="left", padx=0)

            self.prev_page_btn = ctk.CTkButton(
                page_frame, text="←", width=28, height=28,
                command=self._prev_page,
                fg_color="transparent", hover_color="#333333",
                font=("Helvetica", 12, "bold"), corner_radius=0
            )
            self.prev_page_btn.pack(side="left", padx=2)

            self.page_label = ctk.CTkLabel(
                page_frame,
                text=f"PAGE 1 / {len(self.scan_images)}",
                width=90,
                font=("Helvetica", 10, "bold"), text_color="#888888"
            )
            self.page_label.pack(side="left", padx=5)

            self.next_page_btn = ctk.CTkButton(
                page_frame, text="→", width=28, height=28,
                command=self._next_page,
                fg_color="transparent", hover_color="#333333",
                font=("Helvetica", 12, "bold"), corner_radius=0
            )
            self.next_page_btn.pack(side="left", padx=2)

        # --- Action Buttons (Right) ---
        action_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        action_frame.pack(side="right", padx=15, pady=10)

        ctk.CTkButton(
            action_frame, text="CANCEL", width=80, height=28,
            command=self._cancel,
            fg_color="transparent", hover_color="#333333",
            text_color="#FF5555",
            font=("Helvetica", 11, "bold"), corner_radius=0
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            action_frame, text="APPLY & PROCESS", width=140, height=28,
            command=self._confirm,
            fg_color="#336633", hover_color="#447744",
            font=("Helvetica", 11, "bold"), corner_radius=0
        ).pack(side="left", padx=5)

    def _build_canvas(self):
        """Build the main canvas area."""
        canvas_container = ctk.CTkFrame(self, fg_color="#1A1A1A")
        canvas_container.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        canvas_container.grid_columnconfigure(0, weight=1)
        canvas_container.grid_rowconfigure(0, weight=1)

        # Canvas with scrollbars (hidden but functional for large images)
        self.canvas = tk.Canvas(
            canvas_container,
            bg="#1A1A1A",
            highlightthickness=0,
            cursor="crosshair"
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # Make canvas focusable for scroll events
        self.canvas.configure(takefocus=True)
        # Click to focus
        self.canvas.bind(
            "<Button-1>", lambda e: self.canvas.focus_set(), add="+")
        # Auto-focus on mouse enter
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())

        # Instructions overlay
        self.instructions = ctk.CTkLabel(
            canvas_container,
            text="Drag to draw the grid | Scroll to zoom | Hold space and drag to pan",
            font=("Arial", 14),
            fg_color="#333333",
            corner_radius=5,
            padx=15, pady=8
        )
        self.instructions.place(relx=0.5, y=20, anchor="n")

    def _build_bottom_panel(self):
        """Build the bottom panel with preview and frame controls (Swiss Grid Style)."""
        bottom_panel = ctk.CTkFrame(
            self, height=90, fg_color="#1E1E1E", corner_radius=0)
        bottom_panel.grid(row=2, column=0, sticky="ew", padx=0, pady=0)

        # Use a 3-column grid with specific weights
        bottom_panel.grid_columnconfigure(0, weight=1, minsize=250)  # Info
        bottom_panel.grid_columnconfigure(
            1, weight=3)              # Preview (expands)
        bottom_panel.grid_columnconfigure(2, weight=1, minsize=200)  # Controls
        bottom_panel.grid_rowconfigure(0, weight=1)

        # --- Section 1: Grid Info (Left) ---
        info_frame = ctk.CTkFrame(bottom_panel, fg_color="transparent")
        info_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # Label: GRID STATUS
        ctk.CTkLabel(
            info_frame,
            text="GRID STATUS",
            font=("Helvetica", 10, "bold"),
            text_color="#666666"
        ).pack(anchor="w")

        # Main Info
        self.info_label = ctk.CTkLabel(
            info_frame,
            text="NO GRID DEFINED",
            font=("Helvetica", 14, "bold"),
            text_color="#FFFFFF",
            justify="left"
        )
        self.info_label.pack(anchor="w", pady=(2, 0))

        # Sub Info
        self.grid_info_label = ctk.CTkLabel(
            info_frame,
            text="Draw a grid to begin",
            font=("Helvetica", 12),
            text_color="#888888",
            justify="left"
        )
        self.grid_info_label.pack(anchor="w", pady=(0, 0))

        # Separator line
        sep1 = ctk.CTkFrame(bottom_panel, width=1, fg_color="#333333")
        sep1.grid(row=0, column=0, sticky="ne", pady=10)

        # --- Section 2: Preview (Center) ---
        preview_container = ctk.CTkFrame(bottom_panel, fg_color="transparent")
        preview_container.grid(
            row=0, column=1, sticky="nsew", padx=10, pady=10)

        # Header row
        preview_header = ctk.CTkFrame(
            preview_container, fg_color="transparent", height=20)
        preview_header.pack(fill="x", pady=(0, 2))

        ctk.CTkLabel(
            preview_header,
            text="FRAME PREVIEW",
            font=("Helvetica", 10, "bold"),
            text_color="#666666"
        ).pack(side="left")

        # Navigation (Right aligned in header)
        nav_frame = ctk.CTkFrame(preview_header, fg_color="transparent")
        nav_frame.pack(side="right")

        self.btn_prev_frames = ctk.CTkButton(
            nav_frame, text="←", width=30, height=20,
            command=self._prev_preview_page,
            fg_color="transparent", hover_color="#333333",
            text_color="#FFFFFF", font=("Helvetica", 12, "bold")
        )
        self.btn_prev_frames.pack(side="left")

        self.preview_page_label = ctk.CTkLabel(
            nav_frame, text="01 / 01", width=60,
            font=("Helvetica", 11, "bold"), text_color="#888888"
        )
        self.preview_page_label.pack(side="left", padx=5)

        self.btn_next_frames = ctk.CTkButton(
            nav_frame, text="→", width=30, height=20,
            command=self._next_preview_page,
            fg_color="transparent", hover_color="#333333",
            text_color="#FFFFFF", font=("Helvetica", 12, "bold")
        )
        self.btn_next_frames.pack(side="left")

        # Canvas
        self.preview_canvas = tk.Canvas(
            preview_container,
            height=90,
            bg="#1E1E1E",  # Match background
            highlightthickness=0
        )
        self.preview_canvas.pack(fill="x", expand=True)
        self.preview_canvas.bind("<Button-1>", self._on_preview_click)

        # Separator line
        sep2 = ctk.CTkFrame(bottom_panel, width=1, fg_color="#333333")
        sep2.grid(row=0, column=1, sticky="ne", pady=10)

        # --- Section 3: Controls (Right) ---
        controls_frame = ctk.CTkFrame(bottom_panel, fg_color="transparent")
        controls_frame.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)

        ctk.CTkLabel(
            controls_frame,
            text="SELECTION",
            font=("Helvetica", 10, "bold"),
            text_color="#666666"
        ).pack(anchor="w")

        self.selected_frame_label = ctk.CTkLabel(
            controls_frame,
            text="NONE",
            font=("Helvetica", 14, "bold"),
            text_color="#FFFFFF"
        )
        self.selected_frame_label.pack(anchor="w", pady=(2, 5))

        # Action buttons - Minimalist
        self.btn_exclude_frame = ctk.CTkButton(
            controls_frame,
            text="EXCLUDE FRAME",
            width=140, height=24,
            command=self._toggle_exclude_frame,
            fg_color="#333333", hover_color="#444444",
            font=("Helvetica", 11, "bold"),
            corner_radius=0
        )
        self.btn_exclude_frame.pack(anchor="w", pady=(0, 5))

        self.btn_restore_all = ctk.CTkButton(
            controls_frame,
            text="RESTORE ALL",
            width=140, height=24,
            command=self._restore_all_frames,
            fg_color="transparent", hover_color="#333333",
            border_width=1, border_color="#444444",
            font=("Helvetica", 11, "bold"),
            corner_radius=0
        )
        self.btn_restore_all.pack(anchor="w")

    def _bind_events(self):
        """Bind mouse and keyboard events."""
        # Mouse events
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Motion>", self._on_mouse_move)

        # Scroll for zoom - comprehensive bindings for macOS trackpad support
        # We use bind_all to catch events even if the canvas doesn't have strict focus

        # Standard MouseWheel (macOS/Windows)
        self.canvas.bind_all('<MouseWheel>', self._on_mousewheel)
        self.canvas.bind_all('<Shift-MouseWheel>', self._on_mousewheel)
        self.canvas.bind_all('<Control-MouseWheel>', self._on_mousewheel)

        # Linux buttons (and some macOS setups)
        self.canvas.bind_all('<Button-4>', self._on_mousewheel)
        self.canvas.bind_all('<Button-5>', self._on_mousewheel)

        # Local bindings as backup
        self.canvas.bind('<MouseWheel>', self._on_scroll)
        self.canvas.bind('<Button-4>', self._on_scroll)
        self.canvas.bind('<Button-5>', self._on_scroll)

        # Canvas resize
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        # Keyboard shortcuts
        self.bind("<Escape>", lambda e: self._cancel())
        self.bind("<Return>", lambda e: self._confirm())
        self.bind("<KeyPress-space>", self._on_space_press)
        self.bind("<KeyRelease-space>", self._on_space_release)
        self.bind("<d>", lambda e: self._set_tool("draw"))
        self.bind("<a>", lambda e: self._set_tool("adjust"))
        self.bind("<plus>", lambda e: self.zoom_in())
        self.bind("<minus>", lambda e: self.zoom_out())
        self.bind("<equal>", lambda e: self.zoom_in())  # + without shift
        self.bind("<Command-z>", self.undo)
        self.bind("<Control-z>", self.undo)

        # Entry validation
        self.rows_var.trace_add(
            "write", lambda *args: self._on_grid_setting_change())
        self.cols_var.trace_add(
            "write", lambda *args: self._on_grid_setting_change())

    def _set_tool(self, tool: str):
        """Switch the active tool."""
        self.current_tool = tool

        # Update button appearances
        active_color = "#505050"
        inactive_color = "#333333"

        self.draw_btn.configure(
            fg_color=active_color if tool == "draw" else inactive_color)
        self.pan_btn.configure(
            fg_color=active_color if tool == "pan" else inactive_color)
        self.adjust_btn.configure(
            fg_color=active_color if tool == "adjust" else inactive_color)

        # Update cursor
        if tool == "draw":
            self.canvas.configure(cursor="crosshair")
            self.instructions.configure(
                text="Draw mode - Drag to place grid | Scroll to zoom | Hold space to pan")
        elif tool == "pan":
            self.canvas.configure(cursor="fleur")
            self.instructions.configure(
                text="Pan mode - Drag to move | Scroll to zoom")
        elif tool == "adjust":
            self.canvas.configure(cursor="hand2")
            self.instructions.configure(
                text="Adjust mode - Drag grid corners or edges to refine")

    def _on_space_press(self, event):
        """Temporarily switch to pan tool while space is held."""
        if self.space_pan_active:
            return

        self.space_pan_active = True
        if self.current_tool != "pan":
            self.previous_tool = self.current_tool
            self._set_tool("pan")

    def _on_space_release(self, event):
        """Restore the previous tool after space is released."""
        if not self.space_pan_active:
            return

        self.space_pan_active = False
        if self.previous_tool and self.current_tool == "pan":
            self._set_tool(self.previous_tool)
        self.previous_tool = None

    def _canvas_to_image(self, cx: float, cy: float) -> Tuple[float, float]:
        """Convert canvas coordinates to image coordinates."""
        ix = (cx - self.pan_offset[0]) / self.zoom_level
        iy = (cy - self.pan_offset[1]) / self.zoom_level
        return (ix, iy)

    def _image_to_canvas(self, ix: float, iy: float) -> Tuple[float, float]:
        """Convert image coordinates to canvas coordinates."""
        cx = ix * self.zoom_level + self.pan_offset[0]
        cy = iy * self.zoom_level + self.pan_offset[1]
        return (cx, cy)

    def _on_mouse_down(self, event):
        """Handle mouse press."""
        # Capture state before potential modification
        if self.current_tool in ["draw", "adjust"]:
            self.temp_state = self._create_state_snapshot()

        if self.current_tool == "draw":
            self.draw_start = self._canvas_to_image(event.x, event.y)
            self.is_drawing = True
        elif self.current_tool == "pan":
            self.pan_start = (event.x, event.y)
            self.canvas.configure(cursor="fleur")
        elif self.current_tool == "adjust":
            self._start_handle_drag(event)

    def _on_mouse_drag(self, event):
        """Handle mouse drag."""
        if self.current_tool == "draw" and self.is_drawing and self.draw_start:
            current = self._canvas_to_image(event.x, event.y)
            self._update_draw_preview(self.draw_start, current)
        elif self.current_tool == "pan" and self.pan_start:
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]
            self.pan_offset[0] += dx
            self.pan_offset[1] += dy
            self.pan_start = (event.x, event.y)
            self._redraw()
        elif self.current_tool == "adjust" and self.selected_handle:
            self._drag_handle(event)

    def _on_mouse_up(self, event):
        """Handle mouse release."""
        if self.current_tool == "draw" and self.is_drawing and self.draw_start:
            end = self._canvas_to_image(event.x, event.y)

            # Check if valid grid (must match _finalize_grid check)
            x1, y1 = self.draw_start
            x2, y2 = end
            if abs(x2 - x1) >= 50 and abs(y2 - y1) >= 50:
                if self.temp_state:
                    self.undo_stack.append(self.temp_state)
                    if len(self.undo_stack) > 30:
                        self.undo_stack.pop(0)

            self._finalize_grid(self.draw_start, end)
            self.is_drawing = False
            self.draw_start = None
        elif self.current_tool == "pan":
            self.pan_start = None
        elif self.current_tool == "adjust":
            if self.selected_handle and self.temp_state:
                # We finished adjusting
                self.undo_stack.append(self.temp_state)
                if len(self.undo_stack) > 30:
                    self.undo_stack.pop(0)
            self.selected_handle = None

        self.temp_state = None

    def _on_mouse_move(self, event):
        """Handle mouse movement for cursor updates."""
        if self.current_tool == "adjust" and self.grid_rect:
            handle = self._get_handle_at(event.x, event.y)
            if handle:
                if handle in ["nw", "se"]:
                    self.canvas.configure(cursor="sizing")
                elif handle in ["ne", "sw"]:
                    self.canvas.configure(cursor="sizing")
                elif handle in ["n", "s"]:
                    self.canvas.configure(cursor="sb_v_double_arrow")
                elif handle in ["e", "w"]:
                    self.canvas.configure(cursor="sb_h_double_arrow")
            else:
                self.canvas.configure(cursor="hand2")

    def _on_scroll(self, event):
        """Handle scroll wheel for zoom (Linux Button-4/5)."""
        self._do_zoom(event, event.x, event.y)
        return "break"

    def _on_mousewheel(self, event):
        """Handle MouseWheel events (works with macOS trackpad and Magic Mouse)."""
        try:
            # Always zoom if the event is received, assuming bind_all works correctly
            # But we should check if we are over the canvas to avoid zooming when over other widgets

            # Get absolute mouse position
            x_root = getattr(event, 'x_root', None)
            y_root = getattr(event, 'y_root', None)

            if x_root is None:
                x_root, y_root = self.winfo_pointerxy()

            # Check what widget is under the mouse
            widget = self.winfo_containing(x_root, y_root)

            # Allow zoom if:
            # 1. Mouse is over the canvas
            # 2. Mouse is over the instructions label (which is on top of canvas)
            # 3. Mouse is over the window but not over a specific button/entry (fallback)

            should_zoom = False
            if widget == self.canvas:
                should_zoom = True
            elif widget == self.instructions:
                should_zoom = True
            elif str(widget).startswith(str(self.canvas)):  # Child of canvas
                should_zoom = True

            if should_zoom:
                cx = x_root - self.canvas.winfo_rootx()
                cy = y_root - self.canvas.winfo_rooty()
                self._do_zoom(event, cx, cy)
        except Exception as e:
            print(f"Zoom error: {e}")
            pass

    def _do_zoom(self, event, mx, my):
        """Perform zoom centered at mouse position."""
        # Determine scroll direction
        delta = 0

        # Handle delta (macOS/Windows)
        if hasattr(event, 'delta'):
            delta = event.delta
            # macOS trackpad often sends small deltas or 0
            # If 0, we can't do anything
            if delta == 0:
                return

            # Normalize delta
            # Trackpads can send continuous stream of small values
            # We want to be sensitive but not too fast
            if abs(delta) < 1:
                # Very small delta (high precision trackpad)
                # Accumulate or just use direction
                if delta > 0:
                    delta = 1
                else:
                    delta = -1
            elif abs(delta) > 100:
                # Windows mouse wheel usually 120
                delta = delta / 120

        # Handle buttons (Linux/some macOS)
        elif hasattr(event, 'num'):
            if event.num == 4:
                delta = 1
            elif event.num == 5:
                delta = -1

        if delta == 0:
            return

        # Calculate new zoom
        old_zoom = self.zoom_level

        # Use a smaller zoom factor for smoother trackpad zooming
        # If delta is small (trackpad), use smaller factor
        if abs(delta) <= 1:
            zoom_factor = 1.05  # 5% for trackpad/smooth scroll
        else:
            zoom_factor = 1.15  # 15% for mouse wheel

        if delta > 0:
            self.zoom_level *= zoom_factor
        else:
            self.zoom_level /= zoom_factor

        # Clamp zoom
        self.zoom_level = max(0.1, min(10.0, self.zoom_level))

        # Adjust pan to keep mouse position stable
        scale_change = self.zoom_level / old_zoom
        self.pan_offset[0] = mx - (mx - self.pan_offset[0]) * scale_change
        self.pan_offset[1] = my - (my - self.pan_offset[1]) * scale_change

        self._update_zoom_label()
        self._redraw()

    def _on_canvas_resize(self, event):
        """Handle canvas resize."""
        self._redraw()

    def _create_state_snapshot(self):
        """Create a snapshot of the current state."""
        return {
            'rows': self.rows,
            'cols': self.cols,
            'spacing': self.spacing,
            'grid_rect': self.grid_rect,
            'page_grids': self.page_grids.copy(),
            'page_cells': {k: v[:] for k, v in self.page_cells.items()},
            'excluded_frames': self.excluded_frames.copy(),
            'current_page': self.current_page,
            'result_cells': self.result_cells[:] if self.result_cells else None
        }

    def _save_state(self):
        """Save current state to undo stack."""
        if self.is_undoing:
            return

        state = self._create_state_snapshot()
        self.undo_stack.append(state)

        # Limit stack size
        if len(self.undo_stack) > 30:
            self.undo_stack.pop(0)

    def undo(self, event=None):
        """Undo the last action."""
        if not self.undo_stack:
            return

        state = self.undo_stack.pop()
        self.is_undoing = True

        try:
            # Restore state
            self.rows = state['rows']
            self.cols = state['cols']
            self.spacing = state['spacing']
            self.grid_rect = state['grid_rect']
            self.page_grids = state['page_grids']
            self.page_cells = state['page_cells']
            self.excluded_frames = state['excluded_frames']
            self.result_cells = state['result_cells']

            # Restore UI vars
            self.rows_var.set(str(self.rows))
            self.cols_var.set(str(self.cols))
            self.spacing_var.set(str(self.spacing))

            # Restore page if changed
            if self.current_page != state['current_page']:
                self.current_page = state['current_page']
                self.scan_image = self.scan_images[self.current_page]
                self.original_size = self.scan_image.size
                self.photo_image = None  # Force reload
                if hasattr(self, 'page_label'):
                    self.page_label.configure(
                        text=f"Page {self.current_page + 1} / {len(self.scan_images)}")

                # Update button states
                if hasattr(self, 'prev_page_btn'):
                    self.prev_page_btn.configure(
                        state="normal" if self.current_page > 0 else "disabled")
                if hasattr(self, 'next_page_btn'):
                    self.next_page_btn.configure(state="normal" if self.current_page < len(
                        self.scan_images) - 1 else "disabled")

            # Redraw
            self._redraw()
            self._update_preview()
            self._update_info()

        finally:
            self.is_undoing = False

    def _on_grid_setting_change(self):
        """Handle changes to rows/cols entries."""
        self._save_state()

        # Just update the grid if we have one
        if self.grid_rect:
            self._calculate_cells()
            self._redraw()
            self._update_preview()

    def _update_grid_from_entries(self):
        """Update grid from entry values."""
        try:
            self.rows = int(self.rows_var.get())
            self.cols = int(self.cols_var.get())
            if self.grid_rect:
                self._calculate_cells()
                self._redraw()
                self._update_preview()
        except ValueError:
            pass

    def _update_draw_preview(self, start: Tuple[float, float], end: Tuple[float, float]):
        """Update the grid preview while drawing."""
        # Temporarily set grid_rect for preview
        x1, y1 = start
        x2, y2 = end
        self.grid_rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        self._calculate_cells()
        self._redraw()

    def _finalize_grid(self, start: Tuple[float, float], end: Tuple[float, float]):
        """Finalize the drawn grid."""
        try:
            self.rows = int(self.rows_var.get())
            self.cols = int(self.cols_var.get())
        except ValueError:
            self.rows = 6
            self.cols = 4

        x1, y1 = start
        x2, y2 = end

        # Ensure minimum size
        if abs(x2 - x1) < 50 or abs(y2 - y1) < 50:
            return

        self.grid_rect = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
        self._calculate_cells()
        self._redraw()
        self._update_preview()
        self._update_info()

    def _calculate_cells(self):
        """Calculate individual cell bounds from grid rectangle with spacing."""
        if not self.grid_rect:
            self.result_cells = None
            return

        try:
            self.rows = int(self.rows_var.get())
            self.cols = int(self.cols_var.get())
            self.spacing = int(self.spacing_var.get()) if hasattr(
                self, 'spacing_var') else 10
        except ValueError:
            return

        x1, y1, x2, y2 = self.grid_rect
        grid_w = x2 - x1
        grid_h = y2 - y1

        # Calculate cell size accounting for spacing between cells
        # Total spacing = (cols - 1) * spacing horizontally, (rows - 1) * spacing vertically
        total_spacing_x = (self.cols - 1) * self.spacing
        total_spacing_y = (self.rows - 1) * self.spacing

        cell_w = (grid_w - total_spacing_x) / self.cols
        cell_h = (grid_h - total_spacing_y) / self.rows

        self.result_cells = []
        for row in range(self.rows):
            for col in range(self.cols):
                # Position includes spacing between previous cells
                cx1 = x1 + col * (cell_w + self.spacing)
                cy1 = y1 + row * (cell_h + self.spacing)
                cx2 = cx1 + cell_w
                cy2 = cy1 + cell_h

                self.result_cells.append(CellBounds(
                    row=row, col=col,
                    x1=int(cx1), y1=int(cy1),
                    x2=int(cx2), y2=int(cy2)
                ))

    def _get_handle_at(self, cx: int, cy: int) -> Optional[str]:
        """Check if canvas position is over a resize handle."""
        if not self.grid_rect:
            return None

        x1, y1, x2, y2 = self.grid_rect

        # Convert to canvas coords
        cx1, cy1 = self._image_to_canvas(x1, y1)
        cx2, cy2 = self._image_to_canvas(x2, y2)

        hs = self.handle_size

        # Check corners
        if abs(cx - cx1) < hs and abs(cy - cy1) < hs:
            return "nw"
        if abs(cx - cx2) < hs and abs(cy - cy1) < hs:
            return "ne"
        if abs(cx - cx1) < hs and abs(cy - cy2) < hs:
            return "sw"
        if abs(cx - cx2) < hs and abs(cy - cy2) < hs:
            return "se"

        # Check edges
        if abs(cy - cy1) < hs and cx1 < cx < cx2:
            return "n"
        if abs(cy - cy2) < hs and cx1 < cx < cx2:
            return "s"
        if abs(cx - cx1) < hs and cy1 < cy < cy2:
            return "w"
        if abs(cx - cx2) < hs and cy1 < cy < cy2:
            return "e"

        return None

    def _start_handle_drag(self, event):
        """Start dragging a handle."""
        self.selected_handle = self._get_handle_at(event.x, event.y)
        self.drag_start_pos = self._canvas_to_image(event.x, event.y)
        self.drag_start_rect = self.grid_rect

    def _drag_handle(self, event):
        """Update grid rect while dragging a handle."""
        if not self.selected_handle or not self.drag_start_rect:
            return

        current = self._canvas_to_image(event.x, event.y)
        dx = current[0] - self.drag_start_pos[0]
        dy = current[1] - self.drag_start_pos[1]

        x1, y1, x2, y2 = self.drag_start_rect

        # Apply changes based on handle
        if "n" in self.selected_handle:
            y1 += dy
        if "s" in self.selected_handle:
            y2 += dy
        if "w" in self.selected_handle:
            x1 += dx
        if "e" in self.selected_handle:
            x2 += dx

        # Ensure valid rectangle
        if x2 > x1 + 50 and y2 > y1 + 50:
            self.grid_rect = (x1, y1, x2, y2)
            self._calculate_cells()
            self._redraw()

    def _redraw(self):
        """Redraw the canvas."""
        self.canvas.delete("all")

        # Calculate display size
        display_w = int(self.original_size[0] * self.zoom_level)
        display_h = int(self.original_size[1] * self.zoom_level)

        # Resize image for display
        if display_w > 0 and display_h > 0:
            resized = self.scan_image.resize(
                (display_w, display_h),
                Image.Resampling.LANCZOS
            )
            self.photo_image = ImageTk.PhotoImage(resized)

            self.canvas.create_image(
                self.pan_offset[0],
                self.pan_offset[1],
                anchor="nw",
                image=self.photo_image
            )

        # Draw grid overlay
        if self.result_cells:
            self._draw_grid_overlay()

    def _draw_grid_overlay(self):
        """Draw the grid lines and cell numbers."""
        if not self.result_cells:
            return

        for cell in self.result_cells:
            # Convert to canvas coords
            cx1, cy1 = self._image_to_canvas(cell.x1, cell.y1)
            cx2, cy2 = self._image_to_canvas(cell.x2, cell.y2)

            # Draw cell rectangle
            self.canvas.create_rectangle(
                cx1, cy1, cx2, cy2,
                outline="#00FF00",
                width=2
            )

            # Draw cell number
            idx = cell.row * self.cols + cell.col + 1
            font_size = max(8, int(12 * self.zoom_level))
            self.canvas.create_text(
                (cx1 + cx2) / 2,
                (cy1 + cy2) / 2,
                text=str(idx),
                fill="#00FF00",
                font=("Arial", font_size, "bold")
            )

        # Draw resize handles if in adjust mode
        if self.current_tool == "adjust" and self.grid_rect:
            self._draw_handles()

    def _draw_handles(self):
        """Draw resize handles on the grid corners and edges."""
        if not self.grid_rect:
            return

        x1, y1, x2, y2 = self.grid_rect
        cx1, cy1 = self._image_to_canvas(x1, y1)
        cx2, cy2 = self._image_to_canvas(x2, y2)

        hs = self.handle_size

        # Corner handles
        corners = [
            (cx1, cy1), (cx2, cy1),
            (cx1, cy2), (cx2, cy2)
        ]

        for x, y in corners:
            self.canvas.create_rectangle(
                x - hs, y - hs, x + hs, y + hs,
                fill="#00FF00", outline="#FFFFFF"
            )

        # Edge handles
        mx = (cx1 + cx2) / 2
        my = (cy1 + cy2) / 2
        edges = [
            (mx, cy1), (mx, cy2),
            (cx1, my), (cx2, my)
        ]

        for x, y in edges:
            self.canvas.create_rectangle(
                x - hs/2, y - hs/2, x + hs/2, y + hs/2,
                fill="#00FF00", outline="#FFFFFF"
            )

    def _update_preview(self):
        """Update the frame preview strip with pagination."""
        self.preview_canvas.delete("all")
        self.preview_photos.clear()
        # Store (x, width, frame_index) for click detection
        self.preview_frame_positions = []

        if not self.result_cells:
            self._update_preview_nav()
            return

        thumb_size = 55
        x_offset = 5

        # Calculate pagination
        total_frames = len(self.result_cells)
        start_idx = self.preview_page * self.previews_per_page
        end_idx = min(start_idx + self.previews_per_page, total_frames)

        for i in range(start_idx, end_idx):
            cell = self.result_cells[i]
            try:
                # Clamp bounds to image size
                x1 = max(0, min(cell.x1, self.original_size[0]))
                y1 = max(0, min(cell.y1, self.original_size[1]))
                x2 = max(0, min(cell.x2, self.original_size[0]))
                y2 = max(0, min(cell.y2, self.original_size[1]))

                if x2 <= x1 or y2 <= y1:
                    continue

                # Crop frame from original image
                frame = self.scan_image.crop((x1, y1, x2, y2))

                # Calculate thumbnail size preserving aspect ratio
                aspect = frame.width / frame.height
                if aspect > 1:
                    tw = thumb_size
                    th = int(thumb_size / aspect)
                else:
                    th = thumb_size
                    tw = int(thumb_size * aspect)

                frame = frame.resize((tw, th), Image.Resampling.LANCZOS)

                # Dim excluded frames
                is_excluded = i in self.excluded_frames
                if is_excluded:
                    # Convert to grayscale and dim
                    frame = frame.convert('L').convert('RGB')
                    from PIL import ImageEnhance
                    enhancer = ImageEnhance.Brightness(frame)
                    frame = enhancer.enhance(0.4)

                photo = ImageTk.PhotoImage(frame)
                self.preview_photos.append(photo)

                # Center vertically
                y_pos = (70 - th) // 2

                self.preview_canvas.create_image(
                    x_offset, y_pos,
                    anchor="nw",
                    image=photo,
                    tags=f"frame_{i}"
                )

                # Store position for click detection
                self.preview_frame_positions.append((x_offset, tw, i))

                # Draw selection highlight (green for selected, blue for multi-selected)
                is_selected = i in self.selected_frames
                if is_selected:
                    outline_color = "#00FF00" if len(
                        self.selected_frames) == 1 else "#00AAFF"
                    self.preview_canvas.create_rectangle(
                        x_offset - 2, y_pos - 2,
                        x_offset + tw + 2, y_pos + th + 2,
                        outline=outline_color, width=2
                    )

                # Draw frame number (with X if excluded)
                label = f"X{i + 1}" if is_excluded else str(i + 1)
                if is_excluded:
                    color = "#FF4444"
                elif is_selected:
                    color = "#00FF00" if len(
                        self.selected_frames) == 1 else "#00AAFF"
                else:
                    color = "#888888"
                self.preview_canvas.create_text(
                    x_offset + tw // 2, y_pos + th + 8,
                    text=label,
                    fill=color,
                    font=("Arial", 9)
                )

                x_offset += tw + 8

            except Exception as e:
                print(f"Preview error for cell {i}: {e}")

        self._update_preview_nav()

    def _update_preview_nav(self):
        """Update preview navigation label."""
        if not self.result_cells:
            self.preview_page_label.configure(text="-- / --")
            return

        total = len(self.result_cells)
        start = self.preview_page * self.previews_per_page + 1
        end = min(start + self.previews_per_page - 1, total)

        self.preview_page_label.configure(
            text=f"{start:02d}-{end:02d} / {total:02d}")

    def _prev_preview_page(self):
        """Go to previous preview page."""
        if self.preview_page > 0:
            self.preview_page -= 1
            self._update_preview()

    def _next_preview_page(self):
        """Go to next preview page."""
        if self.result_cells:
            max_page = (len(self.result_cells) - 1) // self.previews_per_page
            if self.preview_page < max_page:
                self.preview_page += 1
                self._update_preview()

    def _on_preview_click(self, event):
        """Handle click on preview to select frame(s). Shift+click for multi-select."""
        if not hasattr(self, 'preview_frame_positions'):
            return

        shift_held = event.state & 0x1  # Check if Shift key is held

        # Find which frame was clicked
        for x_start, width, frame_idx in self.preview_frame_positions:
            if x_start <= event.x <= x_start + width:
                if shift_held:
                    # Shift+click: add/remove from selection or select range
                    if self.last_selected_frame is not None:
                        # Select range from last selected to current
                        start = min(self.last_selected_frame, frame_idx)
                        end = max(self.last_selected_frame, frame_idx)
                        for i in range(start, end + 1):
                            self.selected_frames.add(i)
                    else:
                        # Toggle frame in selection
                        if frame_idx in self.selected_frames:
                            self.selected_frames.discard(frame_idx)
                        else:
                            self.selected_frames.add(frame_idx)
                else:
                    # Regular click: single selection
                    self.selected_frames.clear()
                    self.selected_frames.add(frame_idx)

                self.last_selected_frame = frame_idx
                self._update_selected_frame_ui()
                self._update_preview()
                return

        # Clicked outside any frame - deselect all
        self.selected_frames.clear()
        self.last_selected_frame = None
        self._update_selected_frame_ui()
        self._update_preview()

    def _update_selected_frame_ui(self):
        """Update the selected frame label and button."""
        count = len(self.selected_frames)
        if count > 0:
            if count == 1:
                frame_idx = next(iter(self.selected_frames))
                is_excluded = frame_idx in self.excluded_frames
                self.selected_frame_label.configure(
                    text=f"FRAME {frame_idx + 1}")
            else:
                # Multiple frames selected
                all_excluded = all(
                    f in self.excluded_frames for f in self.selected_frames)
                is_excluded = all_excluded
                self.selected_frame_label.configure(
                    text=f"{count} FRAMES")

            if is_excluded:
                self.btn_exclude_frame.configure(
                    text="INCLUDE FRAME", fg_color="#336633", hover_color="#447744")
            else:
                self.btn_exclude_frame.configure(
                    text="EXCLUDE FRAME", fg_color="#333333", hover_color="#444444")
        else:
            self.selected_frame_label.configure(text="NONE")
            self.btn_exclude_frame.configure(
                text="EXCLUDE FRAME", fg_color="#333333", hover_color="#444444")

    def _toggle_exclude_frame(self):
        """Toggle exclusion of selected frame(s)."""
        if not self.selected_frames:
            return

        self._save_state()

        # Check if all selected are excluded
        all_excluded = all(
            f in self.excluded_frames for f in self.selected_frames)

        if all_excluded:
            # Include all selected
            for frame_idx in self.selected_frames:
                self.excluded_frames.discard(frame_idx)
        else:
            # Exclude all selected
            for frame_idx in self.selected_frames:
                self.excluded_frames.add(frame_idx)

        self._update_selected_frame_ui()
        self._update_preview()
        self._update_info()

    def _restore_all_frames(self):
        """Restore all excluded frames."""
        self._save_state()
        self.excluded_frames.clear()
        self._update_selected_frame_ui()
        self._update_preview()
        self._update_info()

    def _update_info(self):
        """Update the info labels."""
        if self.result_cells:
            total = len(self.result_cells)
            excluded = len(self.excluded_frames) if hasattr(
                self, 'excluded_frames') else 0
            included = total - excluded

            if excluded > 0:
                self.info_label.configure(
                    text=f"{self.rows} x {self.cols} GRID • {included} FRAMES"
                )
                self.grid_info_label.configure(
                    text=f"{total} total frames detected • {excluded} excluded"
                )
            else:
                self.info_label.configure(
                    text=f"{self.rows} x {self.cols} GRID • {total} FRAMES"
                )
                if self.grid_rect:
                    x1, y1, x2, y2 = self.grid_rect
                    cell_w = (x2 - x1) / self.cols
                    cell_h = (y2 - y1) / self.rows
                    self.grid_info_label.configure(
                        text=f"Cell size: {int(cell_w)} x {int(cell_h)} px"
                    )
        else:
            self.info_label.configure(text="NO GRID DEFINED")
            self.grid_info_label.configure(text="Draw a grid to begin")

    def _update_zoom_label(self):
        """Update zoom percentage label."""
        self.zoom_label.configure(text=f"{int(self.zoom_level * 100)}%")

    def zoom_in(self):
        """Zoom in."""
        self.zoom_level *= 1.25
        self.zoom_level = min(10.0, self.zoom_level)
        self._update_zoom_label()
        self._redraw()

    def zoom_out(self):
        """Zoom out."""
        self.zoom_level /= 1.25
        self.zoom_level = max(0.1, self.zoom_level)
        self._update_zoom_label()
        self._redraw()

    def fit_to_view(self):
        """Fit image to canvas size."""
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()

        if canvas_w <= 1 or canvas_h <= 1:
            return

        scale_x = (canvas_w - 40) / self.original_size[0]
        scale_y = (canvas_h - 40) / self.original_size[1]

        self.zoom_level = min(scale_x, scale_y)

        # Center image
        display_w = self.original_size[0] * self.zoom_level
        display_h = self.original_size[1] * self.zoom_level
        self.pan_offset[0] = (canvas_w - display_w) / 2
        self.pan_offset[1] = (canvas_h - display_h) / 2

        self._update_zoom_label()
        self._redraw()

    def _prev_page(self):
        """Navigate to previous page."""
        if self.current_page > 0:
            self._save_current_page_grid()
            self.current_page -= 1
            self._load_page(self.current_page)

    def _next_page(self):
        """Navigate to next page."""
        if self.current_page < len(self.scan_images) - 1:
            self._save_current_page_grid()
            self.current_page += 1
            self._load_page(self.current_page)

    def _save_current_page_grid(self):
        """Save the current page's grid before switching."""
        if self.grid_rect:
            self.page_grids[self.current_page] = self.grid_rect
        if self.result_cells:
            self.page_cells[self.current_page] = self.result_cells

    def _restore_grid_data(self, grid_data: List[Dict]):
        """Restore previously saved grid data.

        Args:
            grid_data: List of dicts with page_index, cells, rows, cols, spacing
        """
        print(f"[GridEditor] Restoring grid data: {len(grid_data)} page(s)")

        for page_data in grid_data:
            page_idx = page_data.get('page_index', 0)
            cells = page_data.get('cells', [])
            rows = page_data.get('rows', self.rows)
            cols = page_data.get('cols', self.cols)
            spacing = page_data.get('spacing', self.spacing)

            print(
                f"[GridEditor] Page {page_idx}: {len(cells)} cells, {rows}x{cols}, spacing={spacing}")

            if cells:
                # Convert (x, y, w, h) tuples back to CellBounds
                cell_bounds = []
                for i, (x, y, w, h) in enumerate(cells):
                    row_idx = i // cols
                    col_idx = i % cols
                    cell_bounds.append(CellBounds(
                        row=row_idx, col=col_idx,
                        x1=int(x), y1=int(y),
                        x2=int(x + w), y2=int(y + h)
                    ))

                self.page_cells[page_idx] = cell_bounds

                # Reconstruct grid_rect from cells
                if cell_bounds:
                    min_x = min(c.x1 for c in cell_bounds)
                    min_y = min(c.y1 for c in cell_bounds)
                    max_x = max(c.x2 for c in cell_bounds)
                    max_y = max(c.y2 for c in cell_bounds)
                    self.page_grids[page_idx] = (min_x, min_y, max_x, max_y)
                    print(
                        f"[GridEditor] Grid rect for page {page_idx}: {self.page_grids[page_idx]}")

                # Update rows/cols/spacing from stored data
                self.rows = rows
                self.cols = cols
                self.spacing = spacing

        # Load first page's grid if available
        if 0 in self.page_grids:
            self.grid_rect = self.page_grids[0]
            self.result_cells = self.page_cells.get(0)
            print(
                f"[GridEditor] Restored grid_rect: {self.grid_rect}, cells: {len(self.result_cells) if self.result_cells else 0}")

    def _load_page(self, page_index: int):
        """Load a specific page."""
        self.scan_image = self.scan_images[page_index]
        self.original_size = self.scan_image.size

        # Restore grid for this page if we have one
        self.grid_rect = self.page_grids.get(page_index)
        self.result_cells = self.page_cells.get(page_index)

        # Update page label
        if hasattr(self, 'page_label'):
            self.page_label.configure(
                text=f"Page {page_index + 1} / {len(self.scan_images)}"
            )

        # Update button states
        if hasattr(self, 'prev_page_btn'):
            self.prev_page_btn.configure(
                state="normal" if page_index > 0 else "disabled"
            )
        if hasattr(self, 'next_page_btn'):
            self.next_page_btn.configure(
                state="normal" if page_index < len(
                    self.scan_images) - 1 else "disabled"
            )

        # Fit new page to view
        self.after(50, self.fit_to_view)

    def _confirm(self):
        """Confirm selection and close."""
        # Save current page before confirming
        self._save_current_page_grid()

        # Check if at least one page has a grid defined
        if not self.page_cells and not self.result_cells:
            messagebox.showwarning(
                "No Grid Defined",
                "Please draw a grid over the thumbnails on at least one page."
            )
            return

        self.confirmed = True

        if self.callback:
            self.callback(self.get_result())

        # Unbind global events
        try:
            self.canvas.unbind_all('<MouseWheel>')
            self.canvas.unbind_all('<Shift-MouseWheel>')
            self.canvas.unbind_all('<Control-MouseWheel>')
            self.canvas.unbind_all('<Button-4>')
            self.canvas.unbind_all('<Button-5>')
        except:
            pass
        self.destroy()

    def _cancel(self):
        """Cancel and close."""
        self.page_cells = {}
        self.result_cells = None
        self.confirmed = False
        # Unbind global events
        try:
            self.canvas.unbind_all('<MouseWheel>')
            self.canvas.unbind_all('<Shift-MouseWheel>')
            self.canvas.unbind_all('<Control-MouseWheel>')
            self.canvas.unbind_all('<Button-4>')
            self.canvas.unbind_all('<Button-5>')
        except:
            pass
        self.destroy()

    def get_result(self) -> Optional[List[Dict]]:
        """Return the selected grid cells for all pages as a list of dicts.

        Returns:
            List of page data, each containing:
                - page_index: int
                - cells: list of (x, y, w, h) tuples (excluding removed frames)
                - rows: int
                - cols: int
                - spacing: int
                - excluded_indices: list of original indices that were excluded
        """
        if not self.confirmed:
            return None

        result = []

        for page_idx in range(len(self.scan_images)):
            cells = self.page_cells.get(page_idx, [])
            if cells:
                # Convert CellBounds to (x, y, w, h) tuples, excluding removed frames
                cell_tuples = []
                excluded_indices = []

                for i, cell in enumerate(cells):
                    if hasattr(self, 'excluded_frames') and i in self.excluded_frames:
                        excluded_indices.append(i)
                        continue
                    cell_tuples.append(
                        (cell.x1, cell.y1, cell.x2 - cell.x1, cell.y2 - cell.y1)
                    )

                result.append({
                    'page_index': page_idx,
                    'cells': cell_tuples,
                    'rows': self.rows,
                    'cols': self.cols,
                    'spacing': self.spacing,
                    'excluded_indices': excluded_indices
                })

        return result if result else None
