import json
from ultralytics import YOLO

class VehicleDetector:
    def __init__(self, model_path: str, config_path: str):
        self.model = YOLO(model_path)
        self.classes_to_detect = []
        self.class_name_to_id = {}
        self.load_config(config_path)
        
    def load_config(self, config_path: str):
        with open(config_path, 'r') as f:
            config = json.load(f)
            self.classes_to_detect = config.get("classes_to_detect", [])
            
        # Ultralytics model.names is a dict {id: 'class_name'}
        # Reverse it to filter
        for class_id, class_name in self.model.names.items():
            if class_name in self.classes_to_detect:
                self.class_name_to_id[class_name] = class_id

    def detect(self, frame):
        """
        Runs YOLO inference on a single frame.
        Returns a list of detections:
        [
            {"class": "car", "confidence": 0.85, "bbox": [x1, y1, x2, y2], "center": (cx, cy)}
        ]
        """
        # Run inference, only filtering by our specific classes if needed
        # We can pass classes=[0, 2, 3, 5, 7] to YOLO, but we'll do it dynamically
        class_ids = list(self.class_name_to_id.values())
        
        # verbose=False to keep terminal clean
        results = self.model.predict(frame, classes=class_ids, verbose=False)
        
        detections = []
        if len(results) > 0:
            result = results[0]
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                
                # Bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # Bottom-center coordinate for ROI assignment
                cx = (x1 + x2) / 2.0
                cy = y2  # Use the bottom of the bounding box
                
                class_name = self.model.names[cls_id]
                
                detections.append({
                    "class": class_name,
                    "confidence": conf,
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "center": (int(cx), int(cy))
                })
                
        return detections
