import os
import shutil
import glob
import tkinter as tk
from tkinter import messagebox
from PIL import Image, ImageTk

# Configuration
RAW_DATA_DIR = r"data\custom_vehicle_dataset\raw"
ANNOTATED_DIR = r"data\custom_vehicle_dataset\annotated"
ANNOTATED_IMAGES_DIR = os.path.join(ANNOTATED_DIR, "images")
ANNOTATED_LABELS_DIR = os.path.join(ANNOTATED_DIR, "labels")

CLASSES = {
    0: "car",
    1: "motorcycle",
    2: "bus",
    3: "ambulance"
}

class YoloAnnotator:
    def __init__(self, root):
        self.root = root
        self.root.title("AegisFlow - YOLO Annotator")
        self.root.geometry("1400x900")
        
        # Ensure directories exist
        os.makedirs(ANNOTATED_IMAGES_DIR, exist_ok=True)
        os.makedirs(ANNOTATED_LABELS_DIR, exist_ok=True)
        
        # Load image paths
        self.image_paths = []
        for ext in ('*.jpeg', '*.jpg', '*.png'):
            self.image_paths.extend(glob.glob(os.path.join(RAW_DATA_DIR, '**', ext), recursive=True))
        
        self.current_idx = 0
        self.current_image = None
        self.tk_image = None
        self.scale_factor = 1.0
        
        # Annotation state
        self.boxes = [] # list of (cls_id, x_min, y_min, x_max, y_max) in original image coords
        self.current_box = None # (x_min, y_min, x_max, y_max)
        self.start_x = None
        self.start_y = None
        self.active_class = tk.IntVar(value=0)
        
        self.setup_ui()
        
        if not self.image_paths:
            messagebox.showinfo("Info", "No images found in raw dataset.")
        else:
            self.load_image()

    def setup_ui(self):
        # Top Frame for controls
        top_frame = tk.Frame(self.root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=5)
        
        # Class Selection
        class_frame = tk.LabelFrame(top_frame, text="Select Class")
        class_frame.pack(side=tk.LEFT, padx=10)
        
        for cls_id, cls_name in CLASSES.items():
            tk.Radiobutton(class_frame, text=cls_name.upper(), variable=self.active_class, value=cls_id).pack(side=tk.LEFT, padx=5)
            
        # Action Buttons
        btn_frame = tk.Frame(top_frame)
        btn_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Button(btn_frame, text="SAVE", command=self.save_annotation, bg="green", fg="white", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="PREVIOUS", command=self.prev_image, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="NEXT", command=self.next_image, width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="DELETE BOX", command=self.delete_last_box, bg="orange", width=10).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="SKIP", command=self.skip_image, bg="red", fg="white", width=10).pack(side=tk.LEFT, padx=5)
        
        # Progress Label
        self.progress_var = tk.StringVar()
        tk.Label(top_frame, textvariable=self.progress_var, font=("Helvetica", 12, "bold")).pack(side=tk.RIGHT, padx=10)
        
        # Canvas
        self.canvas = tk.Canvas(self.root, bg="gray", cursor="cross")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move_press)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)
        
        # Mouse movement tracking for cursor lines
        self.canvas.bind("<Motion>", self.on_mouse_move)
        
        # Status bar
        self.status_var = tk.StringVar()
        tk.Label(self.root, textvariable=self.status_var, bd=1, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.BOTTOM, fill=tk.X)

    def load_image(self):
        if not self.image_paths: return
        self.current_idx = max(0, min(self.current_idx, len(self.image_paths)-1))
        img_path = self.image_paths[self.current_idx]
        
        # Check if already annotated
        filename = os.path.basename(img_path)
        base_name = os.path.splitext(filename)[0]
        label_path = os.path.join(ANNOTATED_LABELS_DIR, base_name + ".txt")
        
        self.boxes = []
        if os.path.exists(label_path):
            self.load_existing_labels(label_path)
            
        try:
            self.current_image = Image.open(img_path)
            self.orig_w, self.orig_h = self.current_image.size
            
            # Scale to fit canvas nicely, say max 1200x800
            max_w, max_h = 1200, 750
            scale_w = max_w / self.orig_w
            scale_h = max_h / self.orig_h
            self.scale_factor = min(1.0, scale_w, scale_h)
            
            new_w = int(self.orig_w * self.scale_factor)
            new_h = int(self.orig_h * self.scale_factor)
            
            resized_img = self.current_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.tk_image = ImageTk.PhotoImage(resized_img)
            
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
            self.draw_boxes()
            self.update_progress()
            self.status_var.set(f"Loaded: {img_path}")
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image {img_path}\n{e}")

    def load_existing_labels(self, label_path):
        try:
            with open(label_path, 'r') as f:
                lines = f.readlines()
            for line in lines:
                parts = line.strip().split()
                if len(parts) == 5:
                    cls_id = int(parts[0])
                    x_center, y_center, w, h = map(float, parts[1:])
                    # Convert YOLO norm back to original pixels
                    x_min = (x_center - w/2) * self.orig_w
                    y_min = (y_center - h/2) * self.orig_h
                    x_max = (x_center + w/2) * self.orig_w
                    y_max = (y_center + h/2) * self.orig_h
                    self.boxes.append((cls_id, x_min, y_min, x_max, y_max))
        except Exception:
            pass

    def update_progress(self):
        total = len(self.image_paths)
        annotated = len(glob.glob(os.path.join(ANNOTATED_LABELS_DIR, "*.txt")))
        skipped = 0 # Difficult to track strictly unless we make a skipped.txt, but we can approximate or ignore
        self.progress_var.set(f"Image {self.current_idx + 1} / {total} | Annotated: {annotated} | Remaining: {total - annotated}")

    def draw_boxes(self):
        self.canvas.delete("bbox")
        self.canvas.delete("bbox_label")
        for cls_id, x1, y1, x2, y2 in self.boxes:
            cx1 = x1 * self.scale_factor
            cy1 = y1 * self.scale_factor
            cx2 = x2 * self.scale_factor
            cy2 = y2 * self.scale_factor
            self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline="red", width=2, tags="bbox")
            
            cls_name = CLASSES.get(cls_id, "unknown")
            self.canvas.create_text(cx1, cy1-10, text=cls_name.upper(), fill="red", anchor=tk.SW, tags="bbox_label")

    def on_button_press(self, event):
        self.start_x = event.x
        self.start_y = event.y
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline="green", width=2, tags="current_rect")

    def on_move_press(self, event):
        cur_x, cur_y = (event.x, event.y)
        # Constrain to image bounds
        img_w = self.orig_w * self.scale_factor
        img_h = self.orig_h * self.scale_factor
        cur_x = max(0, min(cur_x, img_w))
        cur_y = max(0, min(cur_y, img_h))
        
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        cur_x, cur_y = (event.x, event.y)
        img_w = self.orig_w * self.scale_factor
        img_h = self.orig_h * self.scale_factor
        cur_x = max(0, min(cur_x, img_w))
        cur_y = max(0, min(cur_y, img_h))
        
        if abs(cur_x - self.start_x) > 5 and abs(cur_y - self.start_y) > 5:
            # Convert to original coordinates
            x1 = min(self.start_x, cur_x) / self.scale_factor
            y1 = min(self.start_y, cur_y) / self.scale_factor
            x2 = max(self.start_x, cur_x) / self.scale_factor
            y2 = max(self.start_y, cur_y) / self.scale_factor
            
            self.boxes.append((self.active_class.get(), x1, y1, x2, y2))
            
        self.canvas.delete(self.rect)
        self.draw_boxes()

    def on_mouse_move(self, event):
        # Draw crosshair
        self.canvas.delete("crosshair")
        img_w = self.orig_w * self.scale_factor
        img_h = self.orig_h * self.scale_factor
        
        if 0 <= event.x <= img_w and 0 <= event.y <= img_h:
            self.canvas.create_line(event.x, 0, event.x, img_h, fill="yellow", dash=(4, 4), tags="crosshair")
            self.canvas.create_line(0, event.y, img_w, event.y, fill="yellow", dash=(4, 4), tags="crosshair")

    def delete_last_box(self):
        if self.boxes:
            self.boxes.pop()
            self.draw_boxes()

    def save_annotation(self):
        if not self.image_paths: return
        
        if not self.boxes:
            messagebox.showwarning("Warning", "No bounding boxes to save!")
            return
            
        img_path = self.image_paths[self.current_idx]
        filename = os.path.basename(img_path)
        base_name = os.path.splitext(filename)[0]
        
        dest_img_path = os.path.join(ANNOTATED_IMAGES_DIR, filename)
        label_path = os.path.join(ANNOTATED_LABELS_DIR, base_name + ".txt")
        
        try:
            # Save labels
            with open(label_path, 'w') as f:
                for cls_id, x1, y1, x2, y2 in self.boxes:
                    # Validate
                    w = x2 - x1
                    h = y2 - y1
                    if w <= 0 or h <= 0: continue
                    if cls_id not in CLASSES: continue
                    
                    # Convert to YOLO (norm cx, cy, norm w, norm h)
                    norm_x = (x1 + w/2) / self.orig_w
                    norm_y = (y1 + h/2) / self.orig_h
                    norm_w = w / self.orig_w
                    norm_h = h / self.orig_h
                    
                    # Ensure bounds 0-1
                    norm_x = max(0.0, min(1.0, norm_x))
                    norm_y = max(0.0, min(1.0, norm_y))
                    norm_w = max(0.0, min(1.0, norm_w))
                    norm_h = max(0.0, min(1.0, norm_h))
                    
                    f.write(f"{cls_id} {norm_x:.6f} {norm_y:.6f} {norm_w:.6f} {norm_h:.6f}\n")
            
            # Copy image to annotated dir if not there
            if not os.path.exists(dest_img_path):
                shutil.copy2(img_path, dest_img_path)
                
            self.status_var.set(f"Saved annotation for {filename}")
            self.next_image()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save:\n{e}")

    def skip_image(self):
        # Skip image simply advances without saving.
        # We can also clean up existing files if user wants to explicitly remove it
        img_path = self.image_paths[self.current_idx]
        filename = os.path.basename(img_path)
        base_name = os.path.splitext(filename)[0]
        
        dest_img_path = os.path.join(ANNOTATED_IMAGES_DIR, filename)
        label_path = os.path.join(ANNOTATED_LABELS_DIR, base_name + ".txt")
        
        if os.path.exists(label_path):
            os.remove(label_path)
        if os.path.exists(dest_img_path):
            os.remove(dest_img_path)
            
        self.status_var.set(f"Skipped {filename}")
        self.next_image()

    def prev_image(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.load_image()

    def next_image(self):
        if self.current_idx < len(self.image_paths) - 1:
            self.current_idx += 1
            self.load_image()
        else:
            messagebox.showinfo("Done", "Reached the last image.")
            self.update_progress()

if __name__ == "__main__":
    root = tk.Tk()
    app = YoloAnnotator(root)
    root.mainloop()
