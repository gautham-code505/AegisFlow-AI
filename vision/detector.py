import json
from ultralytics import YOLO

class VehicleDetector:
    def __init__(self, model_path: str, config_path: str):
        self.model = YOLO(model_path)
        self.classes_to_detect = []
        self.emergency_classes = []
        self.class_name_to_id = {}
        self.load_config(config_path)
        
    def load_config(self, config_path: str):
        with open(config_path, 'r') as f:
            config = json.load(f)
            self.classes_to_detect = config.get("classes_to_detect", [])
            self.emergency_classes = config.get("emergency_classes", [])
            
        # Ultralytics model.names is a dict {id: 'class_name'}
        # Reverse it to filter
        for class_id, class_name in self.model.names.items():
            if class_name in self.classes_to_detect:
                self.class_name_to_id[class_name] = class_id

    def detect(self, frame, use_tracking=False):
        """
        Runs YOLO inference on a single frame.
        If use_tracking is True, uses ByteTrack to persist object IDs.
        Returns a list of detections:
        [
            {
                "class": "car", 
                "confidence": 0.85, 
                "bbox": [x1, y1, x2, y2], 
                "center": (cx, cy), 
                "is_emergency": False,
                "track_id": 1 or None
            }
        ]
        """
        # Run inference, only filtering by our specific classes if needed
        class_ids = list(self.class_name_to_id.values())
        
        # verbose=False to keep terminal clean
        if use_tracking:
            results = self.model.track(frame, classes=class_ids, verbose=False, persist=True, tracker="bytetrack.yaml")
        else:
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
                
                track_id = int(box.id[0].item()) if box.id is not None else None
                
                detections.append({
                    "class": class_name,
                    "confidence": conf,
                    "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    "center": (int(cx), int(cy)),
                    "is_emergency": class_name in self.emergency_classes,
                    "track_id": track_id
                })
                
        return detections

    def reset_tracking(self):
        """
        Resets the internal YOLO tracker state so that subsequent
        detect() calls on a new video stream do not inherit old tracking IDs.
        """
        if hasattr(self.model, "predictor") and self.model.predictor is not None:
            if hasattr(self.model.predictor, "trackers"):
                for t in self.model.predictor.trackers:
                    if hasattr(t, "reset"):
                        t.reset()
