import cv2
import json
import os
from ultralytics import YOLO

video_path = r'C:\project\data\custom_vehicle_dataset\video_source\Seedance 2_0 - Use the supplied reference image as the exact visual reference for the intersection.mp4'
debug_dir = r'C:\project\tools\camera_diagnostics\video_detection_debug'
config_path = r'C:\project\vision\config.json'
model_path = r'C:\project\yolov8n.pt'

os.makedirs(debug_dir, exist_ok=True)

with open(config_path, 'r') as f:
    config = json.load(f)
prod_conf = config.get('detector', {}).get('confidence_threshold', 0.25)
prod_imgsz = config.get('detector', {}).get('inference_size', 640)

# We want classes 0(person), 1(bicycle), 2(car), 3(motorcycle), 5(bus), 7(truck)
classes_to_keep = [0, 1, 2, 3, 5, 7]

print(f"Loading video: {video_path}")
cap = cv2.VideoCapture(video_path)
total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

frame_indices = [
    int(total_frames * 0.1),
    int(total_frames * 0.3),
    int(total_frames * 0.5),
    int(total_frames * 0.7),
    int(total_frames * 0.9)
]

frames = []
for idx in frame_indices:
    cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
    ret, frame = cap.read()
    if ret:
        frames.append((idx, frame))

cap.release()

print("Loading model...")
model = YOLO(model_path)

confs_to_test = [0.25, 0.20, 0.15, 0.10, 0.05]
imgsz_to_test = [640, 960, 1280]

results = {}

for idx, frame in frames:
    print(f"\n================ FRAME {idx} ================")
    
    for size in imgsz_to_test:
        for conf in confs_to_test:
            
            res = model(frame, conf=conf, imgsz=size, classes=classes_to_keep, verbose=False)
            boxes = res[0].boxes
            
            setting_key = f"size={size}, conf={conf}"
            print(f"--- {setting_key} ---")
            print(f"Detections: {len(boxes)}")
            for box in boxes:
                cls_id = int(box.cls[0].item())
                c = float(box.conf[0].item())
                name = model.names[cls_id]
                print(f"  {name} {c:.2f}")
