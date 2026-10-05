import cv2
import json
import time
from vision.detector import VehicleDetector

img_path = r'C:\project\tools\camera_diagnostics\phone_runtime_raw.jpg'
config_path = r'C:\project\vision\config.json'

with open(config_path, 'r') as f:
    config = json.load(f)
prod_conf = config.get('detector', {}).get('confidence_threshold', 0.25)
prod_imgsz = config.get('detector', {}).get('inference_size', 640)

print("Loading model...")
detector = VehicleDetector(r'C:\project\yolov8n.pt', config_path)
frame = cv2.imread(img_path)
if frame is None:
    print('Error: Could not load image.')
    exit(1)

def run_pass(conf, imgsz, pass_name):
    print(f'\n--- {pass_name} ---')
    detector.conf_threshold = conf
    detector.imgsz = imgsz
    
    # Warmup
    detector.detect(frame, use_tracking=False)
    
    t0 = time.time()
    dets = detector.detect(frame, use_tracking=False)
    t1 = time.time()
    
    print(f'Config: Conf={conf}, Imgsz={imgsz}')
    print(f'Latency: {(t1 - t0) * 1000:.1f} ms')
    print(f'Detections: {len(dets)}')
    for i, d in enumerate(dets):
        print(f'  {i}: Class={d["class"]}, Conf={d["confidence"]}, BBox={d["bbox"]}')

run_pass(prod_conf, prod_imgsz, 'DIAGNOSTIC PASS 1: PRODUCTION SETTINGS')
run_pass(0.05, prod_imgsz, 'DIAGNOSTIC PASS 2: LOW CONFIDENCE (0.05)')
run_pass(prod_conf, 960, 'DIAGNOSTIC PASS 3: IMGSZ = 960')
run_pass(prod_conf, 1280, 'DIAGNOSTIC PASS 4: IMGSZ = 1280')
