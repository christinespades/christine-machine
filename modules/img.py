import threading, torch, cv2, os, io, time
from datetime import datetime
import numpy as np
from PIL import Image, ImageTk
import tkinter as tk
from tkinter import filedialog

THEME_COLORS = {
    "tl": (18, 18, 24),     # top-left
    "tr": (60, 30, 90),     # top-right
    "bl": (12, 12, 16),     # bottom-left
    "br": (120, 40, 70)    # bottom-right
}

def smoothstep(t):
    return t * t * (3.0 - 2.0 * t)

def extract_palette(image, k=5):
    """
    Fast palette extraction without sklearn.
    Returns k averaged colors.
    """
    img = image.reshape(-1, 3).astype(np.float32)

    # random but deterministic sampling
    idx = np.linspace(0, len(img) - 1, k, dtype=int)
    return img[idx]

def lerp(a, b, t):
    return a * (1.0 - t) + b * t

def generate_2d_gradient(
    w,
    h,
    palette_image=None,     # np.ndarray (H,W,3) or None
    palette_blend=0.0,      # 0 = theme, 1 = image
    time=0.0,               # animation time
    chroma_drift=0.015      # subtle RGB separation
):
    # ----------------------------
    # Base theme colors
    # ----------------------------
    tl = np.array(THEME_COLORS["tl"], dtype=np.float32)
    tr = np.array(THEME_COLORS["tr"], dtype=np.float32)
    bl = np.array(THEME_COLORS["bl"], dtype=np.float32)
    br = np.array(THEME_COLORS["br"], dtype=np.float32)

    # ----------------------------
    # Optional image palette blend
    # ----------------------------
    if palette_image is not None and palette_blend > 0.0:
        pal = extract_palette(palette_image, k=4)
        tl = lerp(tl, pal[0], palette_blend)
        tr = lerp(tr, pal[1], palette_blend)
        bl = lerp(bl, pal[2], palette_blend)
        br = lerp(br, pal[3], palette_blend)

    # ----------------------------
    # Violet / blue bias (artistic)
    # ----------------------------
    bias = np.array([20, -10, 35], dtype=np.float32)
    tl += bias
    tr += bias
    bl += bias
    br += bias

    # ----------------------------
    # Build 3x3 control grid
    # ----------------------------
    top = (tl + tr) * 0.5
    bottom = (bl + br) * 0.5
    left = (tl + bl) * 0.5
    right = (tr + br) * 0.5
    center = (tl + tr + bl + br) * 0.25 + np.array([10, -6, 22])

    grid = np.array([
        [tl,    top,    tr],
        [left,  center, right],
        [bl,    bottom, br]
    ])

    # ----------------------------
    # Vectorized coordinate space
    # ----------------------------
    y = np.linspace(0, 1, h, dtype=np.float32)
    x = np.linspace(0, 1, w, dtype=np.float32)
    fy, fx = np.meshgrid(y, x, indexing="ij")

    # Time-based flow
    fx = (fx + time * 0.05) % 1.0
    fy = (fy + np.sin(time * 0.3) * 0.02) % 1.0

    fx = smoothstep(fx)
    fy = smoothstep(fy)

    gx = fx * 2
    gy = fy * 2

    ix = np.clip(gx.astype(int), 0, 1)
    iy = np.clip(gy.astype(int), 0, 1)

    tx = gx - ix
    ty = gy - iy

    # ----------------------------
    # Fetch grid corners (vectorized)
    # ----------------------------
    c00 = grid[iy,     ix    ]
    c10 = grid[iy,     ix + 1]
    c01 = grid[iy + 1, ix    ]
    c11 = grid[iy + 1, ix + 1]

    grad = (
        c00 * (1 - tx)[..., None] * (1 - ty)[..., None] +
        c10 * tx[..., None]       * (1 - ty)[..., None] +
        c01 * (1 - tx)[..., None] * ty[..., None] +
        c11 * tx[..., None]       * ty[..., None]
    )

    # ----------------------------
    # Subtle chroma drift (film-like)
    # ----------------------------
    drift_x = int(w * chroma_drift)
    drift_y = int(h * chroma_drift)

    r = np.roll(grad[..., 0], shift= drift_x, axis=1)
    g = grad[..., 1]
    b = np.roll(grad[..., 2], shift=-drift_y, axis=0)

    grad = np.stack([r, g, b], axis=-1)

    return np.clip(grad, 0, 255).astype(np.uint8)

def start_gradient_animation(canvas):
    def animate():
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w < 2 or h < 2:
            # Wait a bit and try again
            canvas.after(50, animate)
            return
        grad = generate_2d_gradient(
            w, h, palette_image=None, palette_blend=0.25, time=time.time()
        )
        img = ImageTk.PhotoImage(Image.fromarray(grad))
        canvas._bg_img = img  # prevent GC
        canvas.delete("all")
        canvas.create_image(0, 0, image=img, anchor="nw")
        canvas.after(33, animate)
    animate()

_remove_fn = None

def get_rembg():
    global _remove_fn
    if _remove_fn is None:
        console.log("Loading background removal model (first use)...")
        from rembg import remove as _r
        _remove_fn = _r

        # Log if GPU is available via PyTorch
        if torch.cuda.is_available():
            console.log(f"GPU detected: {torch.cuda.get_device_name(0)} – rembg should use CUDA")
        else:
            console.log("No GPU detected – rembg will run on CPU")

        console.log("Background removal model loaded.")
    return _remove_fn

def to_tk(img, size=(512, 512)):
    img = Image.fromarray(img)
    img.thumbnail(size, Image.LANCZOS)
    return ImageTk.PhotoImage(img)

def checkerboard_bg(h, w, size=32):  # bigger squares = crisper preview
    y, x = np.indices((h, w))
    board = ((x // size + y // size) % 2).astype(np.float32)
    light = np.array([200, 200, 200], dtype=np.float32)
    dark  = np.array([120, 120, 120], dtype=np.float32)
    return np.where(board[..., None] == 0, light, dark)

class ChristineConsole:
    def __init__(self, root):
        self.zoom = 1.0  # 100%
        self.win = tk.Toplevel(root)
        self.win.title(".ℭ𝔥𝔯𝔦𝔰𝔱𝔦𝔫𝔢♠ 𝔠𝔬𝔫𝔰𝔬𝔩𝔢")
        self.win.configure(bg="#111")
        self.win.geometry("600x300")
        self.text = tk.Text(self.win, bg="#000", fg="white", state="disabled", font=("Consolas", 12))
        self.text.pack(fill="both", expand=True)
        self.text_font_base = ("Consolas", 12)  # base font size
        self.text.configure(font=self.text_font_base)
        self.is_hovered = False
        self.win.bind("<Enter>", lambda e: setattr(self, "is_hovered", True))
        self.win.bind("<Leave>", lambda e: setattr(self, "is_hovered", False))
        self.win.bind("<MouseWheel>", self.on_scroll)

        # Inside ChristineConsole.__init__
        self.win.overrideredirect(True)

        border_thickness = 4
        self.border_frame = tk.Frame(self.win, bg="#222")
        self.border_frame.pack(fill="both", expand=True)

        # Inner content
        self.container = tk.Frame(self.border_frame, bg="#000")
        self.container.pack(fill="both", expand=True, padx=border_thickness, pady=border_thickness)

        # Gradient background canvas
        self.bg_canvas = tk.Canvas(self.container, highlightthickness=0, bg="#000")
        self.bg_canvas.pack(fill="both", expand=True)

        def redraw_gradient(event=None):
            w = self.win.winfo_width()
            h = self.win.winfo_height()
            if w < 2 or h < 2:
                return
            grad = generate_2d_gradient(w, h, palette_image=None, palette_blend=0.25, time=time.time()%10)
            img = ImageTk.PhotoImage(Image.fromarray(grad))
            self._bg_img = img  # keep reference
            self.bg_canvas.delete("all")
            self.bg_canvas.create_image(0,0,image=img,anchor="nw")

        self.win.bind("<Configure>", redraw_gradient)

    def on_scroll(self, event):
        if event.state & 0x4:  # Ctrl key pressed
            # Only zoom if hovered
            if self.is_hovered:
                if event.delta > 0:
                    self.zoom *= 1.1
                else:
                    self.zoom /= 1.1
                self.zoom = max(0.2, min(5.0, self.zoom))
                new_size = int(self.text_font_base[1] * self.zoom)
                self.text.configure(font=(self.text_font_base[0], new_size))
            return "break"  # stop default scrolling
        # Else: allow normal scrolling

    def log(self, message):
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.text.config(state="normal")
        self.text.insert("end", f"{self.gothic(timestamp)} {self.gothic(message)}\n")
        self.text.see("end")
        self.text.config(state="disabled")

    def gothic(self, text):
        gothic_map = str.maketrans(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
            "𝒜𝐵𝒞𝒟𝐸𝐹𝒢𝐻𝐼𝒥𝒦𝐿𝑀𝒩𝒪𝒫𝒬𝑅𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵𝒶𝒷𝒸𝒹𝑒𝒻𝑔𝒽𝒾𝒿𝓀𝓁𝓂𝓃𝑜𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏"
        )
        return text.translate(gothic_map)
# ---------------------------
# Utility: NumPy <-> Torch GPU
# ---------------------------
def to_tensor_gpu(img: np.ndarray):
    return torch.from_numpy(img.astype(np.float32) / 255.0).permute(2,0,1).unsqueeze(0).cuda()

def to_numpy_cpu(tensor):
    return (tensor.squeeze(0).permute(1,2,0).clamp(0,1).cpu().numpy() * 255).astype(np.uint8)

def animate_titlebar_gradient(self):
    w = self.title_grad_canvas.winfo_width()
    h = self.title_grad_canvas.winfo_height()
    if w > 1 and h > 1:
        grad = generate_2d_gradient(w, h, palette_blend=0.35, time=time.time())
        img = ImageTk.PhotoImage(Image.fromarray(grad))
        self._title_grad_img = img
        self.title_grad_canvas.delete("all")
        self.title_grad_canvas.create_image(0, 0, image=img, anchor="nw")
    self.title_grad_canvas.after(66, self.animate_titlebar_gradient)

# ---------------------------
# Fast threaded background removal
# ---------------------------
def remove_background_async(path, callback):
    def worker():
        with open(path, "rb") as f:
            input_bytes = f.read()
        output_bytes = get_rembg()(input_bytes)
        img = Image.open(io.BytesIO(output_bytes)).convert("RGBA")
        arr = np.array(img)
        console.log(f"Background removal done for {os.path.basename(path)}")
        callback(arr)
    threading.Thread(target=worker).start()
    console.log(f"Background removal finished: {os.path.basename(path)}")

class MachineGUI:
    PARAMS = [
        ("Outline Halo Power", "HALO_STRENGTH", 0.0, 1.0, 0.01),
        ("Outline Halo Blur", "SOFTEN", 0, 50, 1),
        ("Outline Halo R", "HALO_COLOR_R", 0, 255, 1),
        ("Outline Halo G", "HALO_COLOR_G", 0, 255, 1),
        ("Outline Halo B", "HALO_COLOR_B", 0, 255, 1),
        ("Bloom Power", "BLOOM_STRENGTH", 0.0, 1.0, 0.01),
        ("Saturation Boost", "SATURATION_BOOST", 0.0, 2.0, 0.01),
        ("Contrast Boost", "CONTRAST_BOOST", 0.0, 2.0, 0.01),
        ("Brightness Shift", "BRIGHTNESS_SHIFT", -50, 50, 1),
        ("Pixelation", "PIXELATION", 0, 20, 1),
        ("Ripple Power", "RIPPLE_STRENGTH", 0.0, 5.0, 0.01),
        ("Ripple Frequency", "RIPPLE_FREQUENCY", 0.1, 10.0, 0.1),
        ("Edge Noise Power", "EDGE_NOISE_STRENGTH", 0.0, 1.0, 0.01)
    ]

    def __init__(self, root):
        # ---- Root container (grid-safe) ----
        self.container = tk.Frame(root)
        self.container.pack(fill="both", expand=True)

        self.container.columnconfigure(0, weight=1)
        self.container.columnconfigure(1, weight=1)
        self.container.rowconfigure(1, weight=1)

        self.root = root

        # ---- Gradient background canvas ----
        self.bg_canvas = tk.Canvas(
            self.container,
            highlightthickness=0,
            bd=0
        )
        self.bg_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        def redraw_gradient(event=None):
            w = root.winfo_width()
            h = root.winfo_height()
            if w < 2 or h < 2:
                return

            grad = generate_2d_gradient(
                w, h,
                palette_image=None,   # or your np.ndarray image
                palette_blend=0.35,  # float
                time=0.0
            )

            img = ImageTk.PhotoImage(Image.fromarray(grad))
            self._bg_img = img  # prevent GC
            self.bg_canvas.delete("all")
            self.bg_canvas.create_image(0, 0, image=img, anchor="nw")

        self.container.bind("<Configure>", redraw_gradient)

        self.update_lock = threading.Lock()
        self.update_scheduled = False
        self.preview_scale = 1.0  # scale down for live preview performance
        self.bg_removed = None  # <-- initialize here
        self.zoom = 1.0
        self.base_font_size = 10  # base font size for sliders/buttons
        self.is_hovered = False

        # ---- Custom Title Bar ----
        titlebar_height = 32
        titlebar = tk.Frame(self.root, height=32, bg="#444", highlightthickness=0)
        titlebar.place(x=0, y=0, relwidth=1)
        titlebar.lift()
        titlebar.place(x=0, y=0, relwidth=1)
        titlebar.lift()  # ensure it draws above main_frame

        title_label = tk.Label(
            titlebar,
            text=self.gothic(".ℭ𝔥𝔯𝔦𝔰𝔱𝔦𝔫𝔢♠ 𝔪𝔞𝔠𝔥𝔦𝔫𝔢"),
            fg="white",
            bg="#444",
            font=("Consolas", 12, "bold")
        )
        title_label.pack(side="left", padx=10)

        top_row_grad = generate_2d_gradient(1200, 32)
        img = ImageTk.PhotoImage(Image.fromarray(top_row_grad))
        title_bg_label = tk.Label(titlebar, image=img)
        title_bg_label.image = img
        title_bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        title_bg_label.lower()  # put behind text

        # ---- Dragging ----
        def start_move(e):
            root._drag_start_x = e.x
            root._drag_start_y = e.y

        def on_move(e):
            x = e.x_root - root._drag_start_x
            y = e.y_root - root._drag_start_y
            root.geometry(f"+{x}+{y}")

        titlebar.bind("<Button-1>", start_move)
        titlebar.bind("<B1-Motion>", on_move)
        title_label.bind("<Button-1>", start_move)
        title_label.bind("<B1-Motion>", on_move)

        self.title_grad_canvas = tk.Canvas(titlebar, highlightthickness=0, bd=0)
        self.title_grad_canvas.place(x=0, y=0, relwidth=1, relheight=1)

        self.main_frame = tk.Frame(self.container, bg="")
        self.main_frame.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.main_frame.lift()
        self.main_frame.bind("<Enter>", lambda e: setattr(self, "is_hovered", True))
        self.main_frame.bind("<Leave>", lambda e: setattr(self, "is_hovered", False))
        self.main_frame.bind("<MouseWheel>", self.on_scroll)
        root.title(".ℭ𝔥𝔯𝔦𝔰𝔱𝔦𝔫𝔢♠ 𝔪𝔞𝔠𝔥𝔦𝔫𝔢")
        root.configure(bg="#000")
        root.geometry("1200x700")
        root.minsize(1000, 600)

        # Icon
        icon_path = r"C:\Users\Public\Downloads\edge\avatar.gif"
        if not os.path.exists(icon_path):
            icon_path = r"C:\Users\Public\Downloads\edge\avatar.jpg"
        try:
            root.iconphoto(True, tk.PhotoImage(file=icon_path))
        except:
            pass

        # Grid resizing
        root.columnconfigure(0, weight=1)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        root.rowconfigure(1, weight=0)
        root.rowconfigure(2, weight=0)

        self.original = None
        self.processed = None
        self.scales = {}

        # Previews
        self.left = tk.Label(self.container, bg="#000")
        self.left.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.right = tk.Label(self.container, bg="#000")
        self.right.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        # -----------------------------
        # Sliders + separators
        # -----------------------------
        slider_area = tk.Frame(self.container, bg="")
        slider_area.grid(row=1, column=0, columnspan=2, sticky="ew")
        self.container.rowconfigure(1, weight=0)
        self.container.rowconfigure(2, weight=0)
        slider_area.columnconfigure(0, weight=1)

        # Top separator
        tk.Frame(slider_area, bg="white", height=2).grid(row=0, column=0, sticky="ew")

        # Canvas for horizontal scrolling
        canvas = tk.Canvas(slider_area, bg="#000", height=180, highlightthickness=0)
        canvas.grid(row=1, column=0, sticky="ew")

        # Scrollable frame inside canvas
        scroll_frame = tk.Frame(canvas, bg="#000")
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        # Bottom separator
        tk.Frame(slider_area, bg="white", height=2).grid(row=2, column=0, sticky="ew", pady=0)

        # Update scroll region
        def update_scroll(event):
            canvas.config(scrollregion=canvas.bbox("all"))
        scroll_frame.bind("<Configure>", update_scroll)

        # Vertical sliders inside scroll_frame
        self.scales = {}
        for i, (label, var_name, minv, maxv, step) in enumerate(self.PARAMS):
            # Label above the scale
            tk.Label(
                scroll_frame,
                text=self.gothic(label),
                bg="#000",
                fg="white",
                font=("Consolas", 12, "italic")
            ).grid(row=0, column=i, padx=3, pady=(0,1), sticky="s")

            # Slider itself (no label)
            def scale_callback(v, name=var_name, label=label, s=None):
                # Update the slider value text to gothic
                s.configure(label=gui.gothic(str(round(float(v), 2))))
                # Update the image
                gui.update_image(name, label, v)

            scale = tk.Scale(
                scroll_frame,
                from_=minv,
                to=maxv,
                resolution=step,
                orient="horizontal",
                bg="#000",
                fg="white",
                highlightthickness=0,
                troughcolor="#222",
                sliderrelief="flat",
                font=("Consolas", 12, "italic"),
                length=150,
                command=lambda v, s=None: scale_callback(v, s=scale)
            )
            scale.set(globals()[var_name])
            scale.grid(row=1, column=i, padx=3, pady=4, sticky="n")  # smaller pady to reduce space
            self.scales[var_name] = scale

        scroll_frame.update_idletasks()
        canvas.config(scrollregion=canvas.bbox("all"), height=scroll_frame.winfo_height())

        # Horizontal scrolling only when hovering over slider area
        def slider_scroll(event):
            delta = -1 if event.delta < 0 else 1
            canvas.xview_scroll(delta, "units")
            return "break"

        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", slider_scroll))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        # Folder entry + buttons
        btn_frame = tk.Frame(self.container, bg="")
        btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        btn_frame = tk.Frame(self.container, bg="")
        btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)

        # Folder path entry
        self.folder_var = tk.StringVar(value=INPUT_FOLDER)
        tk.Entry(btn_frame, textvariable=self.folder_var, font=("Segoe UI", 10), width=50).grid(row=0, column=0, sticky="ew", padx=5)

        # Load image button
        tk.Button(btn_frame, text=self.gothic("Load Image"), command=self.load, bg="#111", fg="white", font=("Consolas", 11, "italic")).grid(row=0, column=1, sticky="ew", padx=5)

        # Process default folder button
        tk.Button(btn_frame, text=self.gothic("Process Default Folder"), command=self.process_default_folder, bg="#111", fg="white", font=("Consolas", 11, "italic")).grid(row=0, column=2, sticky="ew", padx=5)

        # Load first image from default folder if exists
        self.load_first_from_default()

    def on_scroll(self, event):
        if event.state & 0x4:  # Ctrl pressed
            if self.is_hovered:
                if event.delta > 0:
                    self.zoom *= 1.1
                else:
                    self.zoom /= 1.1
                self.zoom = max(0.2, min(5.0, self.zoom))

                # Scale fonts
                for scale in self.scales.values():
                    f = scale.cget("font").split()
                    font_name = f[0]
                    new_size = max(1, int(self.base_font_size * self.zoom))
                    scale.configure(font=(font_name, new_size, "bold"))

                for child in self.root.winfo_children():
                    self.scale_widget_fonts(child)

            return "break"  # prevent scrolling while zooming
        # else: allow normal scroll

    def scale_widget_fonts(self, widget):
        try:
            f = widget.cget("font").split()
            font_name = f[0]
            new_size = max(1, int(self.base_font_size * self.zoom))
            widget.configure(font=(font_name, new_size))
        except:
            pass
        for child in widget.winfo_children():
            self.scale_widget_fonts(child)

    def gothic(self, text):
        gothic_map = str.maketrans(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
            "𝒜𝐵𝒞𝒟𝐸𝐹𝒢𝐻𝐼𝒥𝒦𝐿𝑀𝒩𝒪𝒫𝒬𝑅𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵𝒶𝒷𝒸𝒹𝑒𝒻𝑔𝒽𝒾𝒿𝓀𝓁𝓂𝓃𝑜𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏"
        )
        return text.translate(gothic_map)

    def load_first_from_default(self):
        folder = self.folder_var.get()
        if not os.path.exists(folder):
            return
        files = [f for f in os.listdir(folder) if f.lower().endswith((".png",".jpg",".jpeg",".webp",".bmp",".tiff",".avif",".gif"))]
        if files:
            path = os.path.join(folder, files[0])
            console.log(f"Auto-loaded preview image: {os.path.basename(path)}")
            self.original = load_image_as_rgba(path)
            remove_background_async(path, self.set_bg_removed)

    def load(self):
        path = filedialog.askopenfilename()
        if not path:
            return
        self.original = load_image_as_rgba(path)  # load immediately for quick preview
        console.log(f"Loaded image {os.path.basename(path)}")
        console.log("Starting background removal (async)...")

        # Start threaded background removal
        remove_background_async(path, self.set_bg_removed)

    def set_bg_removed(self, arr):
        self.bg_removed = arr
        self.update_image()

    def update_image(self, var_name=None, label=None, value=None):
        if self.original is None:
            return
        if var_name is not None and label is not None and value is not None:
            console.log(f"{label} set to {float(value):.2f}")

        # Update globals from sliders
        for var_name, scale in self.scales.items():
            globals()[var_name] = scale.get()

        # Schedule threaded update (debounced)
        if not self.update_scheduled:
            self.update_scheduled = True
            threading.Thread(target=self._threaded_update, daemon=True).start()

    def _threaded_update(self):
        time.sleep(0.1)
        console.log("Updating preview with current slider settings.")
        with self.update_lock:
            if self.bg_removed is None:
                # Background removal not done yet: show checkerboard preview
                source = np.zeros_like(self.original)
                source[:, :, :3] = checkerboard_bg(*self.original.shape[:2])
                source[:, :, 3] = 0  # fully transparent
            else:
                source = self.bg_removed

            # Resize for preview
            preview_rgba = np.array(
                Image.fromarray(source, 'RGBA').resize(
                    (int(source.shape[1] * self.preview_scale),
                     int(source.shape[0] * self.preview_scale)),
                    Image.LANCZOS
                )
            )

            processed_preview = apply_effects(
                preview_rgba
            )

            self.root.after(0, lambda: self._update_preview(processed_preview))
        self.update_scheduled = False

    def _update_preview(self, processed_preview):
        # base preview size
        preview_size = (512, 512)
        # scale by zoom
        zoomed_size = (int(preview_size[0] * self.zoom), int(preview_size[1] * self.zoom))

        self.left.img = to_tk(self.original[:, :, :3], size=zoomed_size)
        self.left.config(image=self.left.img)

        right_rgb = rgba_to_preview(processed_preview)
        self.right.img = to_tk(right_rgb, size=zoomed_size)
        self.right.config(image=self.right.img)

    def process_default_folder(self):
        global INPUT_FOLDER
        INPUT_FOLDER = self.folder_var.get()
        main()

def remove_background_to_rgba(path):
    """
    Loads an image, removes background, returns RGBA numpy array.
    """
    with open(path, "rb") as f:
        input_bytes = f.read()

    output_bytes = get_rembg()(input_bytes)
    img = Image.open(io.BytesIO(output_bytes)).convert("RGBA")
    return np.array(img)

def load_image_as_rgba(path):
    """
    Loads any image format and returns RGBA numpy array.
    """
    img = Image.open(path)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return np.array(img, dtype=np.uint8)

def rgba_to_preview(img_rgba):
    rgb = img_rgba[:, :, :3].astype(np.float32)
    alpha = img_rgba[:, :, 3:4].astype(np.float32) / 255.0

    # Checkerboard background
    h, w = alpha.shape[:2]
    bg = checkerboard_bg(h, w)

    out = rgb * alpha + bg * (1 - alpha)  # alpha masks the subject
    return out.astype(np.uint8)

INPUT_FOLDER = r"C:\Users\Public\Downloads\edge\in"
OUTPUT_FOLDER = r"C:\Users\Public\Downloads\edge\out"
# Edge noise / grunge
EDGE_NOISE_STRENGTH = 0.15   # 0 = off, 0.2–0.5 subtle, >0.7 messy
EDGE_NOISE_SCALE = 1         # bigger = chunkier texture
RIPPLE_STRENGTH = 0.4   # 0 = off, 1–4 subtle, 8+ wild
RIPPLE_FREQUENCY = 3.5
# Max halo width in pixels (feather size)
HALO_WIDTH = 40
HALO_COLOR_R = 88
HALO_COLOR_G = 25
HALO_COLOR_B = 88
# Overall halo strength (0–1)
HALO_STRENGTH = 0.9
# Extra softness (Gaussian blur)
SOFTEN = 12
BLOOM_STRENGTH = 0.1   # 0 = off, 0.3–0.7 subtle
# Optional subtle glow multiplier (1 = off, 2–4 = stronger)
GLOW = 9.0
# Save compression
PNG_COMPRESSION = 6
# Image adjustments
SATURATION_BOOST = 1.08     # 1.0 = no change, 1.2–1.6 works well
CONTRAST_BOOST   = 0.92     # 1.0 = no change
BRIGHTNESS_SHIFT = 0       # small values like 5–15
# Pixelation amount (0 = off, higher = chunkier)
PIXELATION = 3             # try 6–20

# -------------------------------------------------
def add_bloom(rgb, strength):
    if strength <= 0:
        return rgb

    blur = cv2.GaussianBlur(rgb, (0, 0), 18)
    return np.clip(rgb + blur * strength, 0, 255)


def ripple_distortion(rgb, strength, freq):
    if strength <= 0:
        return rgb

    h, w = rgb.shape[:2]

    y, x = np.indices((h, w)).astype(np.float32)

    ripple = np.sin(x / freq) + np.cos(y / freq)

    x_new = x + ripple * strength
    y_new = y + ripple * strength

    return cv2.remap(
        rgb,
        x_new,
        y_new,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT
    )

def boost_saturation(rgb, factor):
    hsv = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] *= factor
    hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)

def adjust_contrast(rgb, contrast, brightness):
    # result = rgb * contrast + brightness
    out = rgb * contrast + brightness
    return np.clip(out, 0, 255)

def apply_pixelation(rgb, amount):
    if amount <= 0:
        return rgb

    h, w = rgb.shape[:2]

    small = cv2.resize(
        rgb,
        (max(1, w // amount), max(1, h // amount)),
        interpolation=cv2.INTER_NEAREST
    )

    pixelated = cv2.resize(
        small,
        (w, h),
        interpolation=cv2.INTER_NEAREST
    )

    return pixelated

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def build_edge_gradient(alpha):
    """
    Strong at the edge, fading outward into transparency.
    """

    # Solid subject mask
    a = (alpha > 0).astype(np.uint8)

    # Background = 1, subject = 0
    inv = 1 - a

    # Distance OUT from edge
    dist = cv2.distanceTransform(inv, cv2.DIST_L2, 3)

    # Limit to halo width
    dist = np.clip(dist, 0, HALO_WIDTH).astype(np.float32)

    # Convert to 0–1 where:
    # 1 = at the edge, 0 = far background
    gradient = 1.0 - (dist / HALO_WIDTH)

    # Slight curve for nicer rolloff
    gradient = gradient**1.4

    return gradient

def apply_effects(rgba):
    rgb = rgba[:, :, :3].astype(np.float32)
    alpha = rgba[:, :, 3].astype(np.uint8)

    halo_gradient = build_edge_gradient(alpha)

    # Create colored halo
    color = np.zeros_like(rgb)
    HALO_COLOR = (
        globals()["HALO_COLOR_R"],
        globals()["HALO_COLOR_G"],
        globals()["HALO_COLOR_B"]
    )
    color[:] = HALO_COLOR

    # mask so halo appears ONLY outside the subject
    a = (alpha > 0).astype(np.float32)
    inv = 1.0 - (alpha > 0).astype(np.float32)  # background only
    halo = color * halo_gradient[..., None] * inv[..., None] * HALO_STRENGTH

    # Optional glow softening
    if SOFTEN > 0:
        halo = cv2.GaussianBlur(halo, (0, 0), SOFTEN)

    if GLOW > 1.0:
        halo = np.clip(halo * GLOW, 0, 255)

    # Composite under subject using existing alpha
    a = alpha.astype(np.float32) / 255.0
    a3 = a[..., None]          # make it (h, w, 1)

    # Composite
    result_rgb = halo + rgb
    result_rgb = np.clip(result_rgb, 0, 255)

    # Edge grunge
    result_rgb = add_edge_noise(result_rgb, halo_gradient)

    # --- POST EFFECTS (subject + halo together) ---

    # Saturation
    if SATURATION_BOOST != 1.0:
        result_rgb = boost_saturation(result_rgb, SATURATION_BOOST)

    # Contrast + brightness
    result_rgb = adjust_contrast(result_rgb, CONTRAST_BOOST, BRIGHTNESS_SHIFT)

    # Pixelation
    result_rgb = apply_pixelation(result_rgb, PIXELATION)

    result_rgb = ripple_distortion(result_rgb, RIPPLE_STRENGTH, RIPPLE_FREQUENCY)

    # Bloom glow
    result_rgb = add_bloom(result_rgb, BLOOM_STRENGTH)

    # Re-attach alpha
    out = np.dstack([result_rgb.clip(0, 255).astype(np.uint8), alpha])
    return out

def add_edge_noise(rgb, gradient):
    if EDGE_NOISE_STRENGTH <= 0:
        return rgb
    h, w = gradient.shape
    noise = np.random.randn(h // EDGE_NOISE_SCALE + 1,
                            w // EDGE_NOISE_SCALE + 1).astype(np.float32)
    noise = cv2.resize(noise, (w, h), interpolation=cv2.INTER_LINEAR)
    noise = (noise - noise.min()) / (noise.max() - noise.min())
    noise = (noise[..., None] * 255)
    mask = gradient[..., None]
    return np.clip(rgb + noise * mask * EDGE_NOISE_STRENGTH, 0, 255)

def process_image(path):
    rgba = load_image_as_rgba(path)
    rgba = remove_background_to_rgba(path)
    result = apply_effects(rgba)
    base = os.path.splitext(os.path.basename(path))[0]
    out_path = os.path.join(OUTPUT_FOLDER, base + ".png")
    out = Image.fromarray(result, "RGBA")
    out.save(out_path, compress_level=PNG_COMPRESSION)

def main():
    ensure_dir(OUTPUT_FOLDER)
    files = [
        f for f in os.listdir(INPUT_FOLDER)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".avif", ".gif"))
    ]

    if not files:
        print(f"No PNGs found in {INPUT_FOLDER}.")
        return

    for f in files:
        print("Processing:", f)
        process_image(os.path.join(INPUT_FOLDER, f))

    print("Done.")

def center_windows(main_win, console_win, main_w=1200, main_h=700, console_w=600, console_h=300, gap=10):
    screen_w = main_win.winfo_screenwidth()
    screen_h = main_win.winfo_screenheight()

    # Center main window
    main_x = (screen_w - main_w - console_w - gap) // 2
    main_y = (screen_h - main_h) // 2
    main_win.geometry(f"{main_w}x{main_h}+{main_x}+{main_y}")

    # Place console to the right
    console_x = main_x + main_w + gap
    console_y = main_y
    console_win.geometry(f"{console_w}x{console_h}+{console_x}+{console_y}")

if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # hide main window until GUI is fully ready
    root.overrideredirect(True)

    # Create console first
    console = ChristineConsole(root)

    # Then create main GUI
    gui = MachineGUI(root)

    root.update_idletasks()  # make sure winfo_screenwidth() is accurate
    center_windows(root, console.win)
    console.log(".ℭ𝔥𝔯𝔦𝔰𝔱𝔦𝔫𝔢♠ 𝔪𝔞𝔠𝔥𝔦𝔫𝔢 initialized.")

    root.deiconify()  # show main window
    root.mainloop()
