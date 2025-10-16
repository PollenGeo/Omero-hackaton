import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
import numpy as np
import tifffile

try:
    import openslide
    OPENSLIDE_AVAILABLE = True
except ImportError:
    OPENSLIDE_AVAILABLE = False
    print("OpenSlide not available. Install: pip install openslide-python")

class WSITrackingViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("WSI Viewer with Tracking Map")
        
        # Image variables
        self.slide = None
        self.image = None
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
        
        # Tracking variables - by percentage
        self.tracking_levels = [10, 40, 60, 80]
        self.tracking_grids = {10: None, 40: None, 60: None, 80: None}
        self.tracking_colors = {
            10: (0, 200, 0, 100),      # Green - low zoom
            40: (0, 100, 255, 100),    # Blue
            60: (255, 165, 0, 100),    # Orange
            80: (255, 0, 0, 100)       # Red - high zoom
        }
        self.grid_cell_size = 100  # Size of tracking grid cells in pixels
        
        # Map variables
        self.map_thumbnail = None
        self.map_scale_x = 1.0
        self.map_scale_y = 1.0
        self.tracking_overlay = None
        self.viewport_rect = None
        
        self.setup_ui()
        
    def setup_ui(self):
        # Top controls
        top = tk.Frame(self.root)
        top.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        tk.Button(top, text="Load Image", command=self.load_image, 
                 width=12, bg='lightblue').pack(side=tk.LEFT, padx=2)
        
        tk.Label(top, text="Quick Zoom:").pack(side=tk.LEFT, padx=5)
        for percent in [10, 40, 60, 80]:
            color = {10: 'lightgreen', 40: 'lightblue', 60: 'orange', 80: 'salmon'}[percent]
            tk.Button(top, text=f"{percent}%", 
                     command=lambda p=percent: self.set_zoom_percent(p), 
                     width=5, bg=color).pack(side=tk.LEFT, padx=1)
        
        tk.Button(top, text="-", command=self.zoom_out, width=3).pack(side=tk.LEFT, padx=(10,0))
        self.lbl_zoom = tk.Label(top, text="100%", width=8, relief=tk.SUNKEN, 
                                 font=('Arial', 9, 'bold'))
        self.lbl_zoom.pack(side=tk.LEFT)
        tk.Button(top, text="+", command=self.zoom_in, width=3).pack(side=tk.LEFT)
        
        tk.Button(top, text="Reset", command=self.reset, width=6).pack(side=tk.LEFT, padx=10)
        tk.Button(top, text="Clear Tracking", command=self.clear_tracking, 
                 width=12, bg='lightyellow').pack(side=tk.LEFT, padx=2)
        
        self.lbl_info = tk.Label(top, text="", fg='gray')
        self.lbl_info.pack(side=tk.RIGHT, padx=10)
        
        # Main area
        main = tk.Frame(self.root)
        main.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Canvas
        canvas_frame = tk.Frame(main, relief=tk.SUNKEN, bd=2)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg='gray')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Side panel
        side = tk.Frame(main, width=320, relief=tk.RAISED, bd=2)
        side.pack(side=tk.RIGHT, fill=tk.Y, padx=(5,0))
        side.pack_propagate(False)
        
        tk.Label(side, text="Navigation Map", font=('Arial', 11, 'bold')).pack(pady=10)
        
        # Map canvas
        self.canvas_map = tk.Canvas(side, width=300, height=300, bg='lightgray', 
                                    relief=tk.SUNKEN, bd=2)
        self.canvas_map.pack(padx=10, pady=10)
        
        tk.Label(side, text="Click map to navigate", font=('Arial', 8, 'italic'), 
                fg='gray').pack()
        
        # Legend
        legend_frame = tk.LabelFrame(side, text="Tracking Legend", font=('Arial', 10, 'bold'))
        legend_frame.pack(padx=10, pady=15, fill=tk.X)
        
        tk.Label(legend_frame, text="Visited areas by zoom level:", 
                font=('Arial', 8)).pack(pady=(5,8))
        
        for percent in [10, 40, 60, 80]:
            lf = tk.Frame(legend_frame)
            lf.pack(anchor='w', padx=15, pady=3)
            color_rgb = self.tracking_colors[percent][:3]
            color_hex = '#%02x%02x%02x' % color_rgb
            canvas_color = tk.Canvas(lf, width=25, height=18, bg=color_hex, 
                                    relief=tk.SOLID, borderwidth=1)
            canvas_color.pack(side=tk.LEFT)
            tk.Label(lf, text=f" {percent}% zoom", font=('Arial', 9)).pack(side=tk.LEFT)
        
        # Info
        info_frame = tk.LabelFrame(side, text="Image Info")
        info_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        self.lbl_details = tk.Label(info_frame, text="No image loaded", 
                                    fg='gray', wraplength=280, justify=tk.LEFT, 
                                    font=('Arial', 8))
        self.lbl_details.pack(pady=10, padx=10, anchor='w')
        
        # Status
        self.lbl_status = tk.Label(side, text="", fg='green', font=('Arial', 8, 'italic'))
        self.lbl_status.pack(pady=5)
        
        # Bindings
        self.canvas.bind("<ButtonPress-1>", lambda e: setattr(self, 'pan_start', (e.x, e.y)))
        self.canvas.bind("<B1-Motion>", self.pan)
        self.canvas.bind("<MouseWheel>", lambda e: self.zoom_in() if e.delta > 0 else self.zoom_out())
        self.canvas.bind("<Button-4>", lambda e: self.zoom_in())
        self.canvas.bind("<Button-5>", lambda e: self.zoom_out())
        self.canvas_map.bind("<Button-1>", self.click_map)
        
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
            if self.slide:
                self.slide.close()
            self.slide = None
            self.image = None
            self.use_openslide = False
            
            # Try OpenSlide
            if OPENSLIDE_AVAILABLE and path.lower().endswith(('.ndpi', '.svs', '.vms', '.vmu', '.scn', '.mrxs', '.tif', '.tiff', '.bif')):
                try:
                    self.slide = openslide.OpenSlide(path)
                    self.use_openslide = True
                    self.slide_dimensions = self.slide.dimensions
                    self.level_count = self.slide.level_count
                    self.level_dimensions = self.slide.level_dimensions
                    self.level_downsamples = self.slide.level_downsamples
                    self.lbl_status.config(text=f"✓ OpenSlide ({self.level_count} levels)", fg='green')
                except openslide.OpenSlideError:
                    self.use_openslide = False
            
            # Fallback to PIL
            if not self.use_openslide:
                if path.endswith(('.tif', '.tiff')):
                    self.image = Image.fromarray(tifffile.imread(path))
                else:
                    self.image = Image.open(path)
                self.slide_dimensions = (self.image.width, self.image.height)
                self.lbl_status.config(text="✓ PIL/tifffile", fg='orange')
            
            self.initialize_tracking()
            self.update_info()
            self.reset()
            messagebox.showinfo("Success", 
                f"Loaded: {self.slide_dimensions[0]} x {self.slide_dimensions[1]} px\n"
                f"Method: {'OpenSlide' if self.use_openslide else 'Standard'}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Could not load:\n{str(e)}")
            self.lbl_status.config(text="✗ Error", fg='red')
    
    def initialize_tracking(self):
        """Initialize tracking grids"""
        w, h = self.slide_dimensions
        grid_w = (w // self.grid_cell_size) + 1
        grid_h = (h // self.grid_cell_size) + 1
        
        for percent in self.tracking_levels:
            self.tracking_grids[percent] = np.zeros((grid_h, grid_w), dtype=bool)
    
    def update_info(self):
        w, h = self.slide_dimensions
        info = f"Size: {w:,} x {h:,} px\n"
        info += f"Megapixels: {w * h / 1e6:.1f}\n\n"
        if self.use_openslide:
            info += f"Pyramid Levels: {self.level_count}\n"
            mag = self.slide.properties.get(openslide.PROPERTY_NAME_OBJECTIVE_POWER, 'N/A')
            info += f"Magnification: {mag}\n"
        self.lbl_details.config(text=info)
        self.lbl_info.config(text=f"{w} x {h} px")
    
    def get_best_level(self, zoom):
        if not self.use_openslide:
            return 0
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
        if self.use_openslide:
            level = self.get_best_level(zoom)
            downsample = self.level_downsamples[level]
            level_width = int(width / downsample)
            level_height = int(height / downsample)
            region = self.slide.read_region((int(x), int(y)), level, (level_width, level_height))
            region = region.convert('RGB')
            target_width = int(width * zoom)
            target_height = int(height * zoom)
            region = region.resize((target_width, target_height), Image.Resampling.LANCZOS)
            return region
        else:
            x2 = min(x + width, self.image.width)
            y2 = min(y + height, self.image.height)
            region = self.image.crop((int(x), int(y), int(x2), int(y2)))
            target_w = int((x2 - x) * zoom)
            target_h = int((y2 - y) * zoom)
            return region.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    def get_tracking_level(self, zoom_percent):
        """Get closest tracking level for current zoom percentage"""
        return min(self.tracking_levels, key=lambda x: abs(x - zoom_percent))
    
    def mark_visited(self):
        """Mark current viewport as visited"""
        if not self.slide_dimensions[0]:
            return
        
        # Convert zoom to percentage
        zoom_percent = int(self.zoom * 100)
        
        # Find closest tracking level
        tracking_level = self.get_tracking_level(zoom_percent)
        
        if tracking_level not in self.tracking_grids:
            return
        
        w, h = max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)
        view_w = w / self.zoom
        view_h = h / self.zoom
        
        x1 = int(self.offset_x)
        y1 = int(self.offset_y)
        x2 = int(self.offset_x + view_w)
        y2 = int(self.offset_y + view_h)
        
        # Mark grid cells as visited
        grid_x1 = max(0, x1 // self.grid_cell_size)
        grid_y1 = max(0, y1 // self.grid_cell_size)
        grid_x2 = min(self.tracking_grids[tracking_level].shape[1] - 1, x2 // self.grid_cell_size)
        grid_y2 = min(self.tracking_grids[tracking_level].shape[0] - 1, y2 // self.grid_cell_size)
        
        self.tracking_grids[tracking_level][grid_y1:grid_y2+1, grid_x1:grid_x2+1] = True
    
    def update_map(self):
        """Update navigation map with tracking overlay"""
        if not self.slide_dimensions[0]:
            return
        
        # Create thumbnail
        if self.use_openslide:
            # Use lowest resolution level for thumbnail
            thumb_level = self.level_count - 1
            thumb_size = self.level_dimensions[thumb_level]
            thumb = self.slide.read_region((0, 0), thumb_level, thumb_size)
            thumb = thumb.convert('RGB')
            thumb.thumbnail((290, 290), Image.Resampling.LANCZOS)
        else:
            thumb = self.image.copy()
            thumb.thumbnail((290, 290), Image.Resampling.LANCZOS)
        
        self.map_scale_x = thumb.width / self.slide_dimensions[0]
        self.map_scale_y = thumb.height / self.slide_dimensions[1]
        
        # Create tracking overlay
        tracking_overlay = Image.new('RGBA', thumb.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(tracking_overlay, 'RGBA')
        
        # Draw tracking for each percentage level
        for percent in self.tracking_levels:
            if self.tracking_grids[percent] is None:
                continue
            
            grid = self.tracking_grids[percent]
            color = self.tracking_colors[percent]
            
            for i in range(grid.shape[0]):
                for j in range(grid.shape[1]):
                    if grid[i, j]:
                        img_x1 = j * self.grid_cell_size
                        img_y1 = i * self.grid_cell_size
                        img_x2 = (j + 1) * self.grid_cell_size
                        img_y2 = (i + 1) * self.grid_cell_size
                        
                        map_x1 = img_x1 * self.map_scale_x
                        map_y1 = img_y1 * self.map_scale_y
                        map_x2 = img_x2 * self.map_scale_x
                        map_y2 = img_y2 * self.map_scale_y
                        
                        draw.rectangle([map_x1, map_y1, map_x2, map_y2], fill=color)
        
        # Composite thumbnail with tracking
        thumb_rgba = thumb.convert('RGBA')
        thumb_with_tracking = Image.alpha_composite(thumb_rgba, tracking_overlay)
        
        self.map_thumbnail = ImageTk.PhotoImage(thumb_with_tracking)
        self.canvas_map.delete("all")
        self.canvas_map.create_image(150, 150, image=self.map_thumbnail)
        
        self.update_viewport_rect()
    
    def update_viewport_rect(self):
        """Draw viewport rectangle on map"""
        if not self.slide_dimensions[0] or not self.map_thumbnail:
            return
        
        w, h = max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)
        view_w = w / self.zoom
        view_h = h / self.zoom
        
        x1 = (self.offset_x * self.map_scale_x) + (150 - (self.map_thumbnail.width() / 2))
        y1 = (self.offset_y * self.map_scale_y) + (150 - (self.map_thumbnail.height() / 2))
        x2 = x1 + (view_w * self.map_scale_x)
        y2 = y1 + (view_h * self.map_scale_y)
        
        if self.viewport_rect:
            self.canvas_map.delete(self.viewport_rect)
        
        self.viewport_rect = self.canvas_map.create_rectangle(
            x1, y1, x2, y2, outline='white', width=3
        )
    
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
        
        # Mark as visited
        self.mark_visited()
        
        # Read and display region
        region = self.read_region(self.offset_x, self.offset_y, view_w, view_h, self.zoom)
        self.photo = ImageTk.PhotoImage(region)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
        
        # Update map periodically
        self.update_map()
    
    def click_map(self, event):
        """Navigate by clicking on map"""
        if not self.slide_dimensions[0] or not self.map_thumbnail:
            return
        
        map_x = event.x - (150 - (self.map_thumbnail.width() / 2))
        map_y = event.y - (150 - (self.map_thumbnail.height() / 2))
        
        img_x = map_x / self.map_scale_x
        img_y = map_y / self.map_scale_y
        
        w, h = max(self.canvas.winfo_width(), 1), max(self.canvas.winfo_height(), 1)
        self.offset_x = img_x - (w / self.zoom / 2)
        self.offset_y = img_y - (h / self.zoom / 2)
        
        self.update_view()
    
    def set_zoom_percent(self, percent):
        """Set zoom by percentage"""
        if self.slide_dimensions[0]:
            self.zoom = percent / 100.0
            self.lbl_zoom.config(text=f"{percent}%")
            self.update_view()
    
    def zoom_in(self):
        if self.slide_dimensions[0]:
            self.zoom = min(self.zoom * 1.5, 10.0)
            self.lbl_zoom.config(text=f"{int(self.zoom*100)}%")
            self.update_view()
    
    def zoom_out(self):
        if self.slide_dimensions[0]:
            self.zoom = max(self.zoom / 1.5, 0.05)
            self.lbl_zoom.config(text=f"{int(self.zoom*100)}%")
            self.update_view()
    
    def pan(self, e):
        if self.slide_dimensions[0] and hasattr(self, 'pan_start'):
            dx = (self.pan_start[0] - e.x) / self.zoom
            dy = (self.pan_start[1] - e.y) / self.zoom
            self.offset_x += dx
            self.offset_y += dy
            self.pan_start = (e.x, e.y)
            self.update_view()
    
    def clear_tracking(self):
        """Clear all tracking data"""
        for percent in self.tracking_grids:
            if self.tracking_grids[percent] is not None:
                self.tracking_grids[percent].fill(False)
        self.update_map()
        messagebox.showinfo("Info", "Tracking cleared")
    
    def reset(self):
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.lbl_zoom.config(text="100%")
        self.update_view()

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1000x700")
    app = WSITrackingViewer(root)
    root.mainloop()