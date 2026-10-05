import json
import abc
from typing import Optional
from ultralytics import YOLO

class EmergencyDetector(abc.ABC):
    """
    Abstract boundary for a specialized emergency detector.
    A specialized model (e.g., audio siren detector or fine-tuned visual AI)
    can implement this interface to inject emergency bounding boxes/classes
    into the canonical pipeline without modifying the general VehicleDetector.
    """
    @abc.abstractmethod
    def detect_emergency(self, frame) -> list:
        pass

class VehicleDetector:
    """
    General Vehicle Detector wrapping YOLOv8.
    
    IMPORTANT ARCHITECTURE BOUNDARY:
    The current YOLOv8 COCO model DOES NOT contain an 'ambulance' or 'fire-truck' class.
    While this class implements the *interface* for emergency detection (extracting
    pre-configured emergency classes and forwarding them as EmergencyState), it acts
    as a placeholder boundary. It will fail honestly (by never returning those classes)
    until a specialized fine-tuned model is provided.
    
    Future Work: If a dedicated EmergencyDetector model is introduced, it should be
    called alongside this general detector, and their bounding boxes unified here
    before being passed down to the canonical pipeline.
    """
    def __init__(self, model_path: str, config_path: str, emergency_detector: Optional[EmergencyDetector] = None):
        self.emergency_detector = emergency_detector
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
            self.roi_anchor = config.get("roi_anchor", "BOTTOM_CENTER")
            
        # Ultralytics model.names is a dict {id: 'class_name'}
        # Reverse it to filter
        for class_id, class_name in self.model.names.items():
            if class_name in self.classes_to_detect:
                self.class_name_to_id[class_name] = class_id

    def detect(self, frame, use_tracking=False, conf=None, imgsz=None):
        """
        Runs YOLO inference on a single frame.
        If use_tracking is True, uses ByteTrack to persist object IDs.
        """
        # Run inference, only filtering by our specific classes if needed
        class_ids = list(self.class_name_to_id.values())
        
        # Build kwargs
        kwargs = {"classes": class_ids, "verbose": False}
        if conf is not None:
            kwargs["conf"] = conf
        if imgsz is not None:
            kwargs["imgsz"] = imgsz

        if use_tracking:
            results = self.model.track(frame, persist=True, tracker="bytetrack.yaml", **kwargs)
        else:
            results = self.model.predict(frame, **kwargs)
        
        detections = []
        if len(results) > 0:
            result = results[0]
            boxes = result.boxes
            for box in boxes:
                cls_id = int(box.cls[0].item())
                conf = float(box.conf[0].item())
                
                # Bounding box coordinates
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                
                # Coordinate for ROI assignment based on anchor configuration
                cx = (x1 + x2) / 2.0
                if self.roi_anchor == "CENTER":
                    cy = (y1 + y2) / 2.0
                else:
                    cy = y2  # Default to BOTTOM_CENTER
                
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
                
        if self.emergency_detector:
            detections.extend(self.emergency_detector.detect_emergency(frame))
                
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
