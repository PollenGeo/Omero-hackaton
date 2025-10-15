import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import tifffile

# Try to import OpenSlide for whole slide imaging
try:
    import openslide
    OPENSLIDE_AVAILABLE = True
except ImportError:
    OPENSLIDE_AVAILABLE = False
    print("OpenSlide not available. Install with: pip install openslide-python")

class WholeSlideImageViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Whole Slide Image Viewer with Grid")
        
        # Image variables
        self.slide = None  # OpenSlide object
        self.image = None  # PIL Image (for small images)
        self.use_openslide = False
        self.slide_dimensions = (0, 0)
        self.level_count = 0
        self.level_dimensions = []
        self.level_downsamples = []
        
        # View variables
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.photo = None
        self.show_grid = True
        self.grid_size = 5000  # Larger default for WSI
        self.max_cols = 0
        self.max_rows = 0
        
        self.setup_ui()
        
    def setup_ui(self):
        # Top controls
        top = tk.Frame(self.root)
        top.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        tk.Button(top, text="Load Image", command=self.load_image, 
                 width=12, bg='lightblue').pack(side=tk.LEFT, padx=2)
        tk.Button(top, text="Grid ON/OFF", command=self.toggle_grid, width=10).pack(side=tk.LEFT, padx=2)
        
        tk.Label(top, text="Grid Size:").pack(side=tk.LEFT, padx=5)
        for size in [1000, 2000, 5000, 10000]:
            tk.Button(top, text=str(size), command=lambda s=size: self.set_grid_size(s), 
                     width=6).pack(side=tk.LEFT, padx=1)
        
        tk.Label(top, text="Zoom:").pack(side=tk.LEFT, padx=5)
        tk.Button(top, text="-", command=self.zoom_out, width=3).pack(side=tk.LEFT)
        self.lbl_zoom = tk.Label(top, text="100%", width=8, relief=tk.SUNKEN)
        self.lbl_zoom.pack(side=tk.LEFT)
        tk.Button(top, text="+", command=self.zoom_in, width=3).pack(side=tk.LEFT)
        
        tk.Button(top, text="Reset", command=self.reset, width=6).pack(side=tk.LEFT, padx=10)
        
        self.lbl_sector = tk.Label(top, text="Sector: -", fg='blue', font=('Arial', 9, 'bold'))
        self.lbl_sector.pack(side=tk.RIGHT, padx=10)
        
        # Main area
        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas
        self.canvas = tk.Canvas(main, bg='gray')
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Side panel
        side = tk.Frame(main, width=260, relief=tk.RAISED, bd=2)
        side.pack(side=tk.RIGHT, fill=tk.Y, padx=(5,0))
        side.pack_propagate(False)
        
        tk.Label(side, text="Sector Navigator", font=('Arial', 12, 'bold')).pack(pady=15)
        
        # Sector selector
        selector_frame = tk.LabelFrame(side, text="Go to Sector", font=('Arial', 10, 'bold'))
        selector_frame.pack(padx=10, pady=10, fill=tk.X)
        
        col_frame = tk.Frame(selector_frame)
        col_frame.pack(pady=8, padx=10, fill=tk.X)
        tk.Label(col_frame, text="Column:", font=('Arial', 9, 'bold'), width=8, anchor='w').pack(side=tk.LEFT)
        self.spin_col = tk.Spinbox(col_frame, from_=0, to=0, width=8, font=('Arial', 10))
        self.spin_col.pack(side=tk.LEFT, padx=5)
        
        row_frame = tk.Frame(selector_frame)
        row_frame.pack(pady=8, padx=10, fill=tk.X)
        tk.Label(row_frame, text="Row:", font=('Arial', 9, 'bold'), width=8, anchor='w').pack(side=tk.LEFT)
        self.spin_row = tk.Spinbox(row_frame, from_=0, to=0, width=8, font=('Arial', 10))
        self.spin_row.pack(side=tk.LEFT, padx=5)
        
        tk.Button(selector_frame, text="GO TO SECTOR", command=self.goto_sector, 
                 bg='lightgreen', width=18, font=('Arial', 10, 'bold'), height=2).pack(pady=15)
        
        tk.Label(side, text="─" * 38).pack(pady=10)
        
        # Image info
        info_frame = tk.LabelFrame(side, text="Image Information", font=('Arial', 10, 'bold'))
        info_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        self.lbl_info = tk.Label(info_frame, text="No image loaded", fg='gray', 
                                 wraplength=230, justify=tk.LEFT, font=('Arial', 8))
        self.lbl_info.pack(pady=10, padx=10, anchor='w')
        
        # Status
        self.lbl_status = tk.Label(side, text="", fg='green', font=('Arial', 8, 'italic'))
        self.lbl_status.pack(pady=5)
        
        # Navigation help
        tk.Label(side, text="Navigation:", font=('Arial', 9, 'bold')).pack(pady=(10,5))
        tk.Label(side, text="• Drag to pan", font=('Arial', 8)).pack(anchor='w', padx=20)
        tk.Label(side, text="• Mouse wheel to zoom", font=('Arial', 8)).pack(anchor='w', padx=20)
        tk.Label(side, text="• Pyramid levels auto-selected", font=('Arial', 8)).pack(anchor='w', padx=20)
        
        # Bindings
        self.canvas.bind("<ButtonPress-1>", lambda e: setattr(self, 'pan_start', (e.x, e.y)))
        self.canvas.bind("<B1-Motion>", self.pan)
        self.canvas.bind("<MouseWheel>", lambda e: self.zoom_in() if e.delta > 0 else self.zoom_out())
        self.canvas.bind("<Button-4>", lambda e: self.zoom_in())
        self.canvas.bind("<Button-5>", lambda e: self.zoom_out())
        
    def load_image(self):
        path = filedialog.askopenfilename(
            filetypes=[
                ("Whole Slide", "*.ndpi *.svs *.tif *.tiff *.vms *.vmu *.scn *.mrxs *.bif"),
                ("All Images", "*.png *.jpg *.jpeg *.bmp"),
                ("All", "*.*")
            ])
        if not path:
            return
        
        try:
            # Close previous slide/image
            if self.slide:
                self.slide.close()
            self.slide = None
            self.image = None
            self.use_openslide = False
            
            # Try OpenSlide first for WSI formats
            if OPENSLIDE_AVAILABLE and path.lower().endswith(('.ndpi', '.svs', '.vms', '.vmu', '.scn', '.mrxs', '.tif', '.tiff', '.bif')):
                try:
                    self.slide = openslide.OpenSlide(path)
                    self.use_openslide = True
                    self.slide_dimensions = self.slide.dimensions
                    self.level_count = self.slide.level_count
                    self.level_dimensions = self.slide.level_dimensions
                    self.level_downsamples = self.slide.level_downsamples
                    
                    self.lbl_status.config(text=f"✓ Using OpenSlide ({self.level_count} pyramid levels)", fg='green')
                    
                except openslide.OpenSlideError:
                    # If OpenSlide fails, try regular image loading
                    self.use_openslide = False
            
            # Fallback to PIL/tifffile for regular images
            if not self.use_openslide:
                if path.endswith(('.tif', '.tiff')):
                    self.image = Image.fromarray(tifffile.imread(path))
                else:
                    self.image = Image.open(path)
                self.slide_dimensions = (self.image.width, self.image.height)
                self.lbl_status.config(text="✓ Using PIL/tifffile (standard loading)", fg='orange')
            
            self.update_info()
            self.reset()
            messagebox.showinfo("Success", 
                f"Image loaded successfully\n"
                f"Size: {self.slide_dimensions[0]} x {self.slide_dimensions[1]} px\n"
                f"Method: {'OpenSlide' if self.use_openslide else 'Standard'}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load image:\n{str(e)}")
            self.lbl_status.config(text="✗ Error loading image", fg='red')
    
    def update_info(self):
        if not self.slide_dimensions[0]:
            return
        
        w, h = self.slide_dimensions
        self.max_cols = (w + self.grid_size - 1) // self.grid_size
        self.max_rows = (h + self.grid_size - 1) // self.grid_size
        
        self.spin_col.config(from_=0, to=max(0, self.max_cols-1))
        self.spin_row.config(from_=0, to=max(0, self.max_rows-1))
        
        info_text = f"Dimensions:\n  {w:,} x {h:,} px\n\n"
        info_text += f"File size: {w * h / 1e6:.1f} megapixels\n\n"
        info_text += f"Grid Cell: {self.grid_size:,} px\n\n"
        info_text += f"Grid Layout:\n  {self.max_cols} cols x {self.max_rows} rows\n\n"
        info_text += f"Total Sectors: {self.max_cols * self.max_rows}\n\n"
        
        if self.use_openslide:
            info_text += f"Pyramid Levels: {self.level_count}\n"
            info_text += f"Magnification: {self.slide.properties.get(openslide.PROPERTY_NAME_OBJECTIVE_POWER, 'N/A')}\n"
        
        self.lbl_info.config(text=info_text)
    
    def get_best_level(self, zoom):
        """Select best pyramid level based on zoom"""
        if not self.use_openslide:
            return 0
        
        # Find level with downsample closest to 1/zoom
        target_downsample = 1.0 / zoom
        best_level = 0
        min_diff = abs(self.level_downsamples[0] - target_downsample)
        
        for level, downsample in enumerate(self.level_downsamples):
            diff = abs(downsample - target_downsample)
            if diff < min_diff:
                min_diff = diff
                best_level = level
        
        return best_level
    
    def read_region(self, x, y, width, height, zoom):
        """Read a region from the image at given zoom"""
        if self.use_openslide:
            level = self.get_best_level(zoom)
            downsample = self.level_downsamples[level]
            
            # Calculate size at selected level
            level_width = int(width / downsample)
            level_height = int(height / downsample)
            
            # Read region from slide
            region = self.slide.read_region((int(x), int(y)), level, (level_width, level_height))
            region = region.convert('RGB')
            
            # Scale to desired size
            target_width = int(width * zoom)
            target_height = int(height * zoom)
            region = region.resize((target_width, target_height), Image.Resampling.LANCZOS)
            
            return region
        else:
            # Standard PIL crop and resize
            x2 = min(x + width, self.image.width)
            y2 = min(y + height, self.image.height)
            region = self.image.crop((int(x), int(y), int(x2), int(y2)))
            target_w = int((x2 - x) * zoom)
            target_h = int((y2 - y) * zoom)
            return region.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    def draw_grid(self, img):
        if not self.show_grid:
            return img
        
        img = img.convert('RGBA')
        draw = ImageDraw.Draw(img, 'RGBA')
        
        w, h = max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)
        cell = self.grid_size * self.zoom
        ox = (self.offset_x % self.grid_size) * self.zoom
        oy = (self.offset_y % self.grid_size) * self.zoom
        
        first_col = int(self.offset_x // self.grid_size)
        first_row = int(self.offset_y // self.grid_size)
        
        # Vertical lines
        x, col = -ox, first_col
        while x < w:
            if 0 <= x <= img.width:
                draw.line([(x, 0), (x, img.height)], fill=(255,255,0,220), width=3)
                if x > 30:
                    t = f"Col {col}"
                    bbox = draw.textbbox((0,0), t)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    draw.rectangle([x-tw//2-5, 5, x+tw//2+5, 5+th+10], fill=(0,0,0,220))
                    draw.text((x-tw//2, 8), t, fill=(255,255,0,255))
            x += cell
            col += 1
        
        # Horizontal lines
        y, row = -oy, first_row
        while y < h:
            if 0 <= y <= img.height:
                draw.line([(0, y), (img.width, y)], fill=(255,255,0,220), width=3)
                if y > 30:
                    t = f"Row {row}"
                    bbox = draw.textbbox((0,0), t)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    draw.rectangle([5, y-th//2-5, 5+tw+10, y+th//2+5], fill=(0,0,0,220))
                    draw.text((8, y-th//2), t, fill=(255,255,0,255))
            y += cell
            row += 1
        
        # Sector labels (only if zoom is reasonable)
        if self.zoom >= 0.3:
            x_start, col = -ox + cell/2, first_col
            while x_start < w + cell:
                y_start, row = -oy + cell/2, first_row
                while y_start < h + cell:
                    if 0 < x_start < img.width and 0 < y_start < img.height:
                        if col < self.max_cols and row < self.max_rows:
                            sector_text = f"Sector\n({col},{row})"
                            lines = sector_text.split('\n')
                            max_width = 0
                            total_height = 0
                            for line in lines:
                                bbox = draw.textbbox((0,0), line)
                                line_width = bbox[2] - bbox[0]
                                line_height = bbox[3] - bbox[1]
                                max_width = max(max_width, line_width)
                                total_height += line_height + 2
                            
                            padding = 8
                            draw.rectangle([
                                x_start - max_width//2 - padding,
                                y_start - total_height//2 - padding,
                                x_start + max_width//2 + padding,
                                y_start + total_height//2 + padding
                            ], fill=(50, 50, 50, 180))
                            
                            current_y = y_start - total_height//2
                            for line in lines:
                                bbox = draw.textbbox((0,0), line)
                                line_width = bbox[2] - bbox[0]
                                line_height = bbox[3] - bbox[1]
                                draw.text((x_start - line_width//2, current_y), line, 
                                        fill=(255,255,255,255))
                                current_y += line_height + 2
                    
                    y_start += cell
                    row += 1
                x_start += cell
                col += 1
        
        return img
    
    def update_view(self):
        if not self.slide_dimensions[0]:
            return
        
        w, h = max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)
        view_w = int(w / self.zoom)
        view_h = int(h / self.zoom)
        
        max_w, max_h = self.slide_dimensions
        view_w = min(view_w, max_w)
        view_h = min(view_h, max_h)
        
        self.offset_x = max(0, min(self.offset_x, max_w - view_w))
        self.offset_y = max(0, min(self.offset_y, max_h - view_h))
        
        # Read region on demand
        region = self.read_region(self.offset_x, self.offset_y, view_w, view_h, self.zoom)
        region = self.draw_grid(region)
        
        self.photo = ImageTk.PhotoImage(region)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        
        # Update sector
        cx = self.offset_x + (view_w / 2)
        cy = self.offset_y + (view_h / 2)
        col = int(cx // self.grid_size)
        row = int(cy // self.grid_size)
        self.lbl_sector.config(text=f"Sector: (Col {col}, Row {row})")
    
    def toggle_grid(self):
        self.show_grid = not self.show_grid
        self.update_view()
    
    def set_grid_size(self, size):
        self.grid_size = size
        self.update_info()
        self.update_view()
    
    def goto_sector(self):
        if not self.slide_dimensions[0]:
            messagebox.showwarning("Warning", "Load an image first")
            return
        try:
            col = int(self.spin_col.get())
            row = int(self.spin_row.get())
            
            if col < 0 or col >= self.max_cols or row < 0 or row >= self.max_rows:
                messagebox.showerror("Error", 
                    f"Out of bounds! Valid: Col 0-{self.max_cols-1}, Row 0-{self.max_rows-1}")
                return
            
            cx = (col * self.grid_size) + (self.grid_size / 2)
            cy = (row * self.grid_size) + (self.grid_size / 2)
            
            w, h = max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)
            self.offset_x = cx - (w/self.zoom/2)
            self.offset_y = cy - (h/self.zoom/2)
            self.update_view()
        except ValueError:
            messagebox.showerror("Error", "Invalid values")
    
    def zoom_in(self):
        if self.slide_dimensions[0]:
            self.zoom = min(self.zoom * 1.5, 10.0)
            self.lbl_zoom.config(text=f"{int(self.zoom*100)}%")
            if self.use_openslide:
                level = self.get_best_level(self.zoom)
                self.lbl_zoom.config(text=f"{int(self.zoom*100)}% (L{level})")
            self.update_view()
    
    def zoom_out(self):
        if self.slide_dimensions[0]:
            self.zoom = max(self.zoom / 1.5, 0.05)
            self.lbl_zoom.config(text=f"{int(self.zoom*100)}%")
            if self.use_openslide:
                level = self.get_best_level(self.zoom)
                self.lbl_zoom.config(text=f"{int(self.zoom*100)}% (L{level})")
            self.update_view()
    
    def pan(self, e):
        if self.slide_dimensions[0] and hasattr(self, 'pan_start'):
            dx = (self.pan_start[0] - e.x) / self.zoom
            dy = (self.pan_start[1] - e.y) / self.zoom
            self.offset_x += dx
            self.offset_y += dy
            self.pan_start = (e.x, e.y)
            self.update_view()
    
    def reset(self):
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.lbl_zoom.config(text="100%")
        self.update_view()

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1100x750")
    app = WholeSlideImageViewer(root)
    root.mainloop()