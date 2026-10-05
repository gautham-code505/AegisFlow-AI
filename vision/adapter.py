import json
import logging
import time
from typing import Generator, Dict, List, Optional, Tuple
import cv2

from vision.roi import ROIManager
from vision.occupancy import OccupancyCalculator
from vision.detector import VehicleDetector
from vision.video_processor import VideoProcessor
from vision.tracker import TrackManager
from models import TrafficState, LaneState, Lane, EmergencyState

logger = logging.getLogger("aegisflow.vision.adapter")

class VisionAdapter:
    """
    Adapter bridging Harshadha's Vision Perception module to AegisFlow AI.
    Converts raw YOLO/OpenCV detections into canonical TrafficState snapshots.
    """
    
    # Map vision configuration lane strings to enum
    LANE_MAPPING = {
        "north": Lane.NORTH,
        "south": Lane.SOUTH,
        "east": Lane.EAST,
        "west": Lane.WEST
    }

    # The canonical TrafficState and safety phase matrix currently model one
    # four-approach intersection only.  Configuration is intentionally
    # validated at this boundary so a 6/8-way camera is never silently
    # interpreted as a safe four-way topology.
    SUPPORTED_APPROACHES = frozenset(LANE_MAPPING)

    def __init__(self, config_path: str = "vision/config.json", model_path: str = "../yolov8n.pt"):
        self.config_path = config_path
        self.model_path = model_path
        self._validate_topology_config()
        self.roi_mgr = ROIManager(config_path)
        self.occ_calc = OccupancyCalculator(config_path, self.roi_mgr)
        self._emergency_classes: List[str] = []
        self._load_emergency_config()
        
        # Debounce emergency detections to prevent single-frame false positives
        # Defaults to 3 frames, overridden by config if present.
        self._emergency_debounce_frames = 3
        with open(self.config_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            self._emergency_debounce_frames = cfg.get("emergency", {}).get("confirmation_frames", 3)
        
        # Load detector lazily to avoid heavy loading on import/startup if not needed immediately
        self.detector = None

    def _validate_topology_config(self) -> None:
        """Reject configurations that the four-way safety model cannot represent."""
        with open(self.config_path, "r", encoding="utf-8") as config_file:
            config = json.load(config_file)

        topology = config.get("topology", {})
        approach_names = topology.get("approaches", list(config.get("lanes", {}).keys()))
        normalized = {str(name).lower() for name in approach_names}

        if normalized != self.SUPPORTED_APPROACHES:
            raise ValueError(
                "Unsupported intersection topology. AegisFlow's current vision, "
                "TrafficState, and safety matrix support exactly the configured "
                "four approaches: north, south, east, west. A 6/8-way intersection "
                "requires an explicit topology model and validated conflict matrix."
            )

    def _load_emergency_config(self) -> None:
        """Load emergency vehicle class names from config."""
        with open(self.config_path, "r", encoding="utf-8") as config_file:
            config = json.load(config_file)
        self._emergency_classes = config.get("emergency_classes", [])

    def _detect_emergency_in_detections(
        self, detections: List[dict], lane_assignments: List[Optional[str]], emergency_history: Optional[List[bool]] = None
    ) -> EmergencyState:
        """
        Scan detections for emergency vehicles and apply multi-frame debounce.
        Returns EmergencyState populated from actual YOLO detections.
        Only triggers if the model genuinely outputs an emergency class for N consecutive frames.
        """
        emergency_hits: Dict[str, List[float]] = {}  # lane -> [confidences]
        emergency_type: Optional[str] = None

        for det, lane in zip(detections, lane_assignments):
            if det.get("is_emergency", False) and lane:
                if lane not in emergency_hits:
                    emergency_hits[lane] = []
                emergency_hits[lane].append(det["confidence"])
                emergency_type = det["class"].upper()

        if emergency_history is not None:
            if not emergency_hits:
                emergency_history.append(False)
            else:
                emergency_history.append(True)
                
            # Maintain sliding window in-place
            while len(emergency_history) > self._emergency_debounce_frames:
                emergency_history.pop(0)
            
            # Not confirmed yet
            if len(emergency_history) < self._emergency_debounce_frames or not all(emergency_history):
                return EmergencyState(detected=False, lane=None, vehicle_type=None)
        else:
            # For single-image processing (no history), trigger immediately if detected
            if not emergency_hits:
                return EmergencyState(detected=False, lane=None, vehicle_type=None)

        # Pick the lane with the most emergency detections (tie-break: highest max confidence)
        best_lane = max(
            emergency_hits.keys(),
            key=lambda l: (len(emergency_hits[l]), max(emergency_hits[l]))
        )
        confs = emergency_hits[best_lane]

        return EmergencyState(
            detected=True,
            lane=self.LANE_MAPPING.get(best_lane),
            vehicle_type=emergency_type,
            confidence=round(max(confs), 3),
            vehicle_count=len(confs),
        )

    def _classify_detections(self, detected_classes: List[str]) -> Tuple[int, int, int]:
        """Classify detected objects into vehicle/heavy/pedestrian counts."""
        veh_count = 0
        heavy_count = 0
        ped_count = 0
        for cls in detected_classes:
            if cls == "person":
                ped_count += 1
            elif cls in ["bus", "truck"]:
                veh_count += 1
                heavy_count += 1
            elif cls in ["car", "motorcycle", "bicycle"]:
                veh_count += 1
            elif cls in self._emergency_classes:
                # Emergency vehicles count as vehicles too
                veh_count += 1
        return veh_count, heavy_count, ped_count

    def _ensure_detector(self):
        if self.detector is None:
            logger.info(f"Loading YOLO model from {self.model_path}")
            self.detector = VehicleDetector(self.model_path, self.config_path)

    def process_video(self, input_video: str, output_video: str, process_every_n_frames: int = 5, use_tracking: bool = False, is_live: bool = False, frame_callback=None, conf=None, imgsz=None) -> Generator[TrafficState, None, None]:
        """
        Legacy wrapper: Opens VideoProcessor and processes it.
        """
        try:
            vid_proc = VideoProcessor(input_video, output_video, is_live=is_live, frame_callback=frame_callback)
        except ValueError as e:
            logger.error(f"Failed to open video {input_video}: {e}")
            raise
            
        yield from self.process_source(vid_proc, vid_proc, process_every_n_frames, use_tracking, conf=conf, imgsz=imgsz)

    def process_source(self, source, visualizer=None, process_every_n_frames: int = 5, use_tracking: bool = False, conf=None, imgsz=None) -> Generator[TrafficState, None, None]:
        """
        Processes frames from a generic source (which implements read_frame and release).
        If visualizer is provided, it handles drawing and writing output.
        """
        self._ensure_detector()

        frame_count = 0
        
        tracker = None
        if use_tracking:
            self.detector.reset_tracking()
            tracker = TrackManager(self.config_path)
            
        emergency_history = []
            
        try:
            perf_start_time = time.time()
            frame_times = []
            infer_times = []
            capture_times = []
            last_capture_time = time.time()

            while True:
                t0 = time.time()
                ret, frame = source.read_frame()
                t_capture = time.time()
                capture_times.append(t_capture - last_capture_time)
                last_capture_time = t_capture
                
                if not ret:
                    break
                    
                frame_count += 1
                
                if frame_count == 1:
                    cv2.imwrite(r"C:\project\tools\camera_diagnostics\phone_runtime_raw.jpg", frame)
                    logger.info(r"Saved raw frame to C:\project\tools\camera_diagnostics\phone_runtime_raw.jpg")
                
                # Frame rate control: bypass if tracking is enabled
                if not use_tracking and frame_count % process_every_n_frames != 0:
                    if visualizer and not getattr(visualizer, 'is_live', False):
                        visualizer.write_frame(frame) # Write original frame to maintain FPS
                    continue
                    
                # 1. Detect
                t1 = time.time()
                detections = self.detector.detect(frame, use_tracking=use_tracking, conf=conf, imgsz=imgsz)
                t2 = time.time()
                infer_times.append(t2 - t1)
                
                # 2. Assign to ROIs
                lane_assignments = []
                vehicles_per_lane: Dict[str, List[str]] = {lane: [] for lane in self.roi_mgr.lanes.keys()}
                
                # Get frame dimensions for normalized ROI lookup
                frame_height, frame_width = frame.shape[:2]
                
                for det in detections:
                    cx, cy = det['center']
                    cls = det['class']
                    
                    lane = self.roi_mgr.get_lane_for_point(cx, cy, frame_width, frame_height)
                    lane_assignments.append(lane)
                    
                    if lane:
                        vehicles_per_lane[lane].append(cls)
                        
                # 3. Translate to Canonical TrafficState
                timestamp = time.time()
                
                # Calculate total metrics
                total_vehicles = len(detections)
                assigned_vehicles = sum(len(vehicles) for vehicles in vehicles_per_lane.values())
                unassigned_vehicles = total_vehicles - assigned_vehicles
                
                total_classes = {}
                for det in detections:
                    cls = det['class']
                    total_classes[cls] = total_classes.get(cls, 0) + 1
                
                # Update tracking if enabled
                if tracker:
                    tracker.update(detections, lane_assignments, timestamp, frame_count)
                
                lane_states = {}
                for lane_str, lane_enum in self.LANE_MAPPING.items():
                    queued_count = 0
                    moving_count = 0
                    observed_average_wait = 0.0
                    observed_max_wait = 0.0
                    
                    if tracker:
                        from vision.tracker import MovementState
                        queued_count = sum(1 for t in tracker.tracks.values() if t.current_approach == lane_str and t.movement_state == MovementState.QUEUED)
                        moving_count = sum(1 for t in tracker.tracks.values() if t.current_approach == lane_str and t.movement_state == MovementState.MOVING)
                        
                        waits = []
                        for t in tracker.tracks.values():
                            if t.current_approach == lane_str and t.movement_state == MovementState.QUEUED and t.queued_at is not None:
                                wait = timestamp - t.queued_at
                                if wait < 0:
                                    wait = 0.0
                                waits.append(wait)
                        
                        if waits:
                            observed_average_wait = sum(waits) / len(waits)
                            observed_max_wait = max(waits)

                    if lane_str not in vehicles_per_lane or not vehicles_per_lane[lane_str]:
                        lane_states[lane_enum] = LaneState(
                            has_media=True,
                            status="ACTIVE",
                            queued_vehicle_count=queued_count,
                            moving_vehicle_count=moving_count,
                            observed_average_wait=observed_average_wait,
                            observed_max_wait=observed_max_wait
                        )
                        continue
                        
                    detected_classes = vehicles_per_lane[lane_str]
                    veh_count, heavy_count, ped_count = self._classify_detections(detected_classes)
                    occupancy = self.occ_calc.calculate_occupancy(lane_str, detected_classes)
                    
                    lane_states[lane_enum] = LaneState(
                        has_media=True,
                        status="ACTIVE",
                        vehicle_count=veh_count,
                        occupancy=round(occupancy, 3),
                        pedestrian_count=ped_count,
                        heavy_vehicle_count=heavy_count,
                        queued_vehicle_count=queued_count,
                        moving_vehicle_count=moving_count,
                        observed_average_wait=observed_average_wait,
                        observed_max_wait=observed_max_wait
                    )

                # 3b. Detect emergency vehicles from actual YOLO output
                emergency = self._detect_emergency_in_detections(detections, lane_assignments, emergency_history)
                
                state = TrafficState(
                    timestamp=timestamp,
                    frame_id=frame_count,
                    source=str(getattr(source, 'input_path', 'unknown')),
                    has_tracking_data=(tracker is not None),
                    total_vehicles=total_vehicles,
                    unassigned_vehicles=unassigned_vehicles,
                    total_classes=total_classes,
                    lanes=lane_states,
                    emergency=emergency
                )
                
                # 4. Visualize
                if visualizer:
                    # Construct state dict expected by Harshadha's drawing method
                    vis_state = {
                        "lanes": {
                            lane_str: {
                                "vehicle_count": lane_states[lane_enum].vehicle_count,
                                "occupancy": lane_states[lane_enum].occupancy
                            } for lane_str, lane_enum in self.LANE_MAPPING.items()
                        }
                    }
                    if hasattr(visualizer, 'update_overlay'):
                        visualizer.update_overlay(self.roi_mgr.get_polygons(frame_width, frame_height), detections, lane_assignments, vis_state, frame)
                    else:
                        visualizer.draw_polygons(frame, self.roi_mgr.get_polygons(frame_width, frame_height))
                        visualizer.draw_detections(frame, detections, lane_assignments)
                        visualizer.draw_state(frame, vis_state)
                        visualizer.write_frame(frame)
                
                t_end = time.time()
                frame_times.append(t_end - t0)
                
                if frame_count % 30 == 0:
                    avg_infer = sum(infer_times) / len(infer_times)
                    avg_total = sum(frame_times) / len(frame_times)
                    avg_cap_interval = sum(capture_times) / len(capture_times)
                    cap_fps = 1.0 / avg_cap_interval if avg_cap_interval > 0 else 0
                    out_fps = 1.0 / avg_total if avg_total > 0 else 0
                    logger.info(f"PERF: Capture FPS: {cap_fps:.1f} | Infer: {avg_infer*1000:.1f}ms | Total Latency: {avg_total*1000:.1f}ms | Output FPS: {out_fps:.1f}")
                    infer_times.clear()
                    frame_times.clear()
                    capture_times.clear()

                yield state
                
        except Exception as e:
            logger.error(f"Error during vision processing at frame {frame_count}: {e}")
            raise
        finally:
            source.release()
            if visualizer and visualizer is not source:
                visualizer.release()
            logger.info("Video source processing complete.")

    def process_image(self, input_image: str, output_image: str, frame_callback=None) -> TrafficState:
        """
        Process a single image file, returning a TrafficState snapshot and writing
        the annotated image to output_image.
        """
        self._ensure_detector()
        
        frame = cv2.imread(input_image)
        if frame is None:
            raise ValueError(f"Failed to read image {input_image}")
            
        # 1. Detect
        detections = self.detector.detect(frame)
        
        # 2. Assign to ROIs
        lane_assignments = []
        vehicles_per_lane: Dict[str, List[str]] = {lane: [] for lane in self.roi_mgr.lanes.keys()}
        
        # Get frame dimensions for normalized ROI lookup
        frame_height, frame_width = frame.shape[:2]

        for det in detections:
            cx, cy = det['center']
            cls = det['class']
            
            lane = self.roi_mgr.get_lane_for_point(cx, cy, frame_width, frame_height)
            lane_assignments.append(lane)
            
            if lane:
                vehicles_per_lane[lane].append(cls)
                
        # 3. Translate to Canonical TrafficState
        timestamp = time.time()
        
        # Calculate total metrics
        total_vehicles = len(detections)
        assigned_vehicles = sum(len(vehicles) for vehicles in vehicles_per_lane.values())
        unassigned_vehicles = total_vehicles - assigned_vehicles
        
        total_classes = {}
        for det in detections:
            cls = det['class']
            total_classes[cls] = total_classes.get(cls, 0) + 1
        
        lane_states = {}
        for lane_str, lane_enum in self.LANE_MAPPING.items():
            if lane_str not in vehicles_per_lane or not vehicles_per_lane[lane_str]:
                lane_states[lane_enum] = LaneState(
                    has_media=True,
                    status="ACTIVE"
                )
                continue
                
            detected_classes = vehicles_per_lane[lane_str]
            veh_count, heavy_count, ped_count = self._classify_detections(detected_classes)
            occupancy = self.occ_calc.calculate_occupancy(lane_str, detected_classes)
            
            lane_states[lane_enum] = LaneState(
                has_media=True,
                status="ACTIVE",
                vehicle_count=veh_count,
                occupancy=round(occupancy, 3),
                pedestrian_count=ped_count,
                heavy_vehicle_count=heavy_count
            )

        # 3b. Detect emergency vehicles from actual YOLO output
        emergency = self._detect_emergency_in_detections(detections, lane_assignments)
            
        state = TrafficState(
            timestamp=timestamp,
            frame_id=1,
            source="vision",
            has_tracking_data=False,
            total_vehicles=total_vehicles,
            unassigned_vehicles=unassigned_vehicles,
            total_classes=total_classes,
            lanes=lane_states,
            emergency=emergency
        )
        
        # 4. Visualize
        vis_state = {
            "lanes": {
                lane_str: {
                    "vehicle_count": lane_states[lane_enum].vehicle_count,
                    "occupancy": lane_states[lane_enum].occupancy
                } for lane_str, lane_enum in self.LANE_MAPPING.items()
            }
        }
        
        # Use VideoProcessor drawing methods without full instantiation
        from vision.video_processor import VideoProcessor
        vp = VideoProcessor.__new__(VideoProcessor)
        vp.draw_polygons(frame, self.roi_mgr.get_polygons(frame.shape[1], frame.shape[0]))
        vp.draw_detections(frame, detections, lane_assignments)
        vp.draw_state(frame, vis_state)
        
        cv2.imwrite(output_image, frame)
        if frame_callback:
            # Need to encode as JPEG for the stream
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                frame_callback(buffer.tobytes())
                
        logger.info(f"Image processing complete. Annotated output saved to {output_image}")
        
        return state

    def process_single_approach_video(
        self, input_video: str, approach: str, process_every_n_frames: int = 5, use_tracking: bool = False, is_live: bool = False
    ):
        """
        Legacy wrapper for approach processing.
        """
        try:
            vid_proc = VideoProcessor(input_video, output_path=None, is_live=is_live)
        except ValueError as e:
            raise ValueError(f"Could not open video file {input_video}") from e
            
        return self.process_single_approach_source(vid_proc, approach, process_every_n_frames, use_tracking)

    def process_single_approach_source(
        self, source, approach: str, process_every_n_frames: int = 5, use_tracking: bool = False
    ):
        """
        Process frames from a generic source for a single approach direction.
        """
        self._ensure_detector()
        approach = approach.lower()
        if approach not in self.SUPPORTED_APPROACHES:
            raise ValueError(f"Invalid approach '{approach}'. Must be one of: {self.SUPPORTED_APPROACHES}")

        frame_count = 0
        last_lane_state = LaneState()
        last_detections = []
        last_emergency = EmergencyState(detected=False)

        tracker = None
        if use_tracking:
            self.detector.reset_tracking()
            tracker = TrackManager(self.config_path)

        try:
            while True:
                ret, frame = source.read_frame()
                if not ret:
                    break
                frame_count += 1
                if not use_tracking and frame_count % process_every_n_frames != 0:
                    continue

                detections = self.detector.detect(frame, use_tracking=use_tracking)
                detected_classes = []

                for det in detections:
                    detected_classes.append(det['class'])

                veh_count, heavy_count, ped_count = self._classify_detections(detected_classes)
                occupancy = self.occ_calc.calculate_occupancy(approach, detected_classes)

                queued_count = 0
                moving_count = 0
                observed_average_wait = 0.0
                observed_max_wait = 0.0
                if tracker:
                    from vision.tracker import MovementState
                    queued_count = sum(1 for t in tracker.tracks.values() if t.current_approach == approach and t.movement_state == MovementState.QUEUED)
                    moving_count = sum(1 for t in tracker.tracks.values() if t.current_approach == approach and t.movement_state == MovementState.MOVING)
                    
                    waits = []
                    for t in tracker.tracks.values():
                        if t.current_approach == approach and t.movement_state == MovementState.QUEUED and t.queued_at is not None:
                            wait = time.time() - t.queued_at
                            if wait < 0:
                                wait = 0.0
                            waits.append(wait)
                            
                    if waits:
                        observed_average_wait = sum(waits) / len(waits)
                        observed_max_wait = max(waits)

                last_lane_state = LaneState(
                    vehicle_count=veh_count,
                    occupancy=round(occupancy, 3),
                    pedestrian_count=ped_count,
                    heavy_vehicle_count=heavy_count,
                    queued_vehicle_count=queued_count,
                    moving_vehicle_count=moving_count,
                    observed_average_wait=observed_average_wait,
                    observed_max_wait=observed_max_wait,
                    has_media=True,
                    status="ACTIVE"
                )
                last_detections = detections

                # Update tracking if enabled
                lane_assignments = [approach] * len(detections)
                if tracker:
                    tracker.update(detections, lane_assignments, time.time(), frame_count)

                # Check for emergency detections on this approach
                last_emergency = self._detect_emergency_in_detections(detections, lane_assignments)

        finally:
            source.release()

        logger.info(f"Single-approach video processing complete for {approach}: {last_lane_state.vehicle_count} vehicles")
        return last_lane_state, last_detections, last_emergency

    def process_single_approach_image(self, input_image: str, approach: str):
        """
        Process a single image for a single approach direction.
        All detections are assigned to the specified approach.
        Returns LaneState, detection details, and EmergencyState.
        """
        self._ensure_detector()
        approach = approach.lower()
        if approach not in self.SUPPORTED_APPROACHES:
            raise ValueError(f"Invalid approach '{approach}'. Must be one of: {self.SUPPORTED_APPROACHES}")

        frame = cv2.imread(input_image)
        if frame is None:
            raise ValueError(f"Failed to read image {input_image}")

        detections = self.detector.detect(frame)
        detected_classes = []

        for det in detections:
            detected_classes.append(det['class'])

        veh_count, heavy_count, ped_count = self._classify_detections(detected_classes)
        occupancy = self.occ_calc.calculate_occupancy(approach, detected_classes)

        lane_state = LaneState(
            vehicle_count=veh_count,
            occupancy=round(occupancy, 3),
            pedestrian_count=ped_count,
            heavy_vehicle_count=heavy_count,
            has_media=True,
            status="ACTIVE"
        )

        # Check for emergency detections on this approach
        lane_assignments = [approach] * len(detections)
        emergency = self._detect_emergency_in_detections(detections, lane_assignments)

        logger.info(f"Single-approach image processing complete for {approach}: {lane_state.vehicle_count} vehicles")
        return lane_state, detections, emergency
