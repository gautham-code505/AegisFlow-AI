# AEGISFLOW — DIAGNOSTIC REPORT

Based on the diagnostic runs, the failure is occurring **AFTER** YOLO detection, specifically during the **ROI Assignment** phase. YOLO is successfully detecting the vehicles, but they are being dropped before they can be counted in `TrafficState`.

## Root Causes Identified

1. **Top-Down Coordinate Mismatch (`cy = y2`)**
   In `vision/detector.py`, the point used for ROI testing is calculated as `cy = y2` (the bottom edge of the bounding box). While this is standard for angled real-world CCTV cameras (where `y2` represents the tires touching the road), in a top-down view of toy vehicles, the bottom edge is just the rear bumper. This frequently pushes the test coordinate outside the lane polygon, even when the vehicle's center is clearly inside.

2. **Intersection "Dead Zone"**
   The polygons defined in `config.json` cover the incoming lanes but leave a massive gap in the center of the intersection (X: 500-780, Y: 270-450). Any vehicle that enters this center box is marked `UNASSIGNED` and instantly dropped from the lane counts.

3. **Aspect Ratio Rejection (Offline Only)**
   In earlier offline diagnostics, an aspect ratio mismatch between the video dimensions and the calibration config triggered the `ROIManager` to reject the frame entirely, defaulting all assignments to `UNASSIGNED`. (This is isolated to different video sources).

---

## Diagnostic Trace (Representative Frame from Seedance Video)

### 1. RAW YOLO DETECTIONS (No Filtering)
```text
ID:  2 | Class: car        | Conf: 0.596 | BBox: [606.1, 268.0, 649.5, 295.9] | WxH:  43.3x 27.9 | BottomCenter: (627.8, 295.9)
ID:  2 | Class: car        | Conf: 0.567 | BBox: [483.7, 378.7, 527.9, 408.7] | WxH:  44.2x 30.0 | BottomCenter: (505.8, 408.7)
ID:  2 | Class: car        | Conf: 0.500 | BBox: [457.4, 299.0, 505.1, 325.2] | WxH:  47.8x 26.2 | BottomCenter: (481.2, 325.2)
ID:  2 | Class: car        | Conf: 0.441 | BBox: [533.0, 349.1, 575.1, 375.2] | WxH:  42.1x 26.1 | BottomCenter: (554.0, 375.2)
ID:  2 | Class: car        | Conf: 0.437 | BBox: [465.5, 351.4, 511.9, 375.3] | WxH:  46.4x 24.0 | BottomCenter: (488.7, 375.3)
ID:  2 | Class: car        | Conf: 0.427 | BBox: [754.9, 374.3, 799.4, 403.2] | WxH:  44.6x 28.9 | BottomCenter: (777.2, 403.2)
ID:  2 | Class: car        | Conf: 0.309 | BBox: [713.4, 312.7, 734.3, 327.4] | WxH:  20.8x 14.7 | BottomCenter: (723.9, 327.4)
ID:  2 | Class: car        | Conf: 0.279 | BBox: [446.3, 405.0, 492.5, 429.5] | WxH:  46.2x 24.5 | BottomCenter: (469.4, 429.5)
ID:  2 | Class: car        | Conf: 0.278 | BBox: [692.1, 282.9, 734.3, 309.4] | WxH:  42.2x 26.5 | BottomCenter: (713.2, 309.4)
ID:  2 | Class: car        | Conf: 0.256 | BBox: [860.4, 380.0, 903.7, 402.4] | WxH:  43.4x 22.4 | BottomCenter: (882.0, 402.4)
ID:  2 | Class: car        | Conf: 0.253 | BBox: [252.0, 275.6, 300.7, 303.4] | WxH:  48.7x 27.8 | BottomCenter: (276.3, 303.4)
ID:  2 | Class: car        | Conf: 0.252 | BBox: [  4.1, 289.7,  49.5, 317.5] | WxH:  45.4x 27.9 | BottomCenter: ( 26.8, 317.5)
ID:  9 | Class: traffic light | Conf: 0.250 | BBox: [713.9, 554.6, 737.0, 601.2] | WxH:  23.1x 46.6 | BottomCenter: (725.5, 601.2)
```

### 2. AFTER CONFIDENCE THRESHOLD (0.25)
```text
Class: car        | Conf: 0.596
Class: car        | Conf: 0.567
Class: car        | Conf: 0.500
Class: car        | Conf: 0.441
Class: car        | Conf: 0.437
Class: car        | Conf: 0.427
Class: car        | Conf: 0.309
Class: car        | Conf: 0.279
Class: car        | Conf: 0.278
Class: car        | Conf: 0.256
Class: car        | Conf: 0.253
Class: car        | Conf: 0.252
Class: traffic light | Conf: 0.250
```

### 3. AFTER CLASS FILTERING (Configured Classes Only)
```text
Class: car        | Conf: 0.596
Class: car        | Conf: 0.567
Class: car        | Conf: 0.500
Class: car        | Conf: 0.441
Class: car        | Conf: 0.437
Class: car        | Conf: 0.427
Class: car        | Conf: 0.309
Class: car        | Conf: 0.279
Class: car        | Conf: 0.278
Class: car        | Conf: 0.256
Class: car        | Conf: 0.253
Class: car        | Conf: 0.252
```

### 4. AFTER TRACKING (Passed to ByteTrack)
```text
Class: car | Conf: 0.596 | TrackID: 1 | BboxBottomCenter: (627, 295)
Class: car | Conf: 0.567 | TrackID: 2 | BboxBottomCenter: (505, 408)
Class: car | Conf: 0.500 | TrackID: 3 | BboxBottomCenter: (481, 325)
Class: car | Conf: 0.441 | TrackID: 4 | BboxBottomCenter: (554, 375)
Class: car | Conf: 0.437 | TrackID: 5 | BboxBottomCenter: (488, 375)
Class: car | Conf: 0.427 | TrackID: 6 | BboxBottomCenter: (777, 403)
Class: car | Conf: 0.309 | TrackID: 7 | BboxBottomCenter: (723, 327)
Class: car | Conf: 0.279 | TrackID: 8 | BboxBottomCenter: (469, 429)
Class: car | Conf: 0.278 | TrackID: 9 | BboxBottomCenter: (713, 309)
Class: car | Conf: 0.256 | TrackID: 10 | BboxBottomCenter: (882, 402)
Class: car | Conf: 0.253 | TrackID: 11 | BboxBottomCenter: (276, 303)
Class: car | Conf: 0.252 | TrackID: 12 | BboxBottomCenter: (26, 317)
```

### 5. ROI ASSIGNMENT (The Point of Failure)
```text
TrackID 1 : car UNASSIGNED
TrackID 2 : car UNASSIGNED
TrackID 3 : car ASSIGNED TO WEST
TrackID 4 : car UNASSIGNED
TrackID 5 : car ASSIGNED TO WEST
TrackID 6 : car UNASSIGNED
TrackID 7 : car UNASSIGNED
TrackID 8 : car ASSIGNED TO WEST
TrackID 9 : car UNASSIGNED
TrackID 10 : car ASSIGNED TO EAST
TrackID 11 : car ASSIGNED TO WEST
TrackID 12 : car ASSIGNED TO WEST
```

Notice that NO vehicles were assigned to North or South. Vehicles such as TrackID 2 `(505, 408)` are directly in the unassigned center intersection dead-zone.
