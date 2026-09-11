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
        self, detections: List[dict], lane_assignments: List[Optional[str]]
    ) -> EmergencyState:
        """
        Scan detections for emergency vehicles.
        Returns EmergencyState populated from actual YOLO detections.
        Only triggers if the model genuinely outputs an emergency class.
        """
        emergency_hits: Dict[str, List[float]] = {}  # lane -> [confidences]
        emergency_type: Optional[str] = None

        for det, lane in zip(detections, lane_assignments):
            if det.get("is_emergency", False) and lane:
                if lane not in emergency_hits:
                    emergency_hits[lane] = []
                emergency_hits[lane].append(det["confidence"])
                emergency_type = det["class"].upper()

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

    def process_video(self, input_video: str, output_video: str, process_every_n_frames: int = 5, use_tracking: bool = False, is_live: bool = False) -> Generator[TrafficState, None, None]:
        """
        Process a video file, yielding TrafficState snapshots for each processed frame, 
        and writing the annotated video to output_video.
        If use_tracking is True, processes consecutive frames without skipping.
        """
        self._ensure_detector()
        
        try:
            vid_proc = VideoProcessor(input_video, output_video, is_live=is_live)
        except ValueError as e:
            logger.error(f"Failed to open video {input_video}: {e}")
            raise

        frame_count = 0
        
        tracker = None
        if use_tracking:
            self.detector.reset_tracking()
            tracker = TrackManager(self.config_path)
            
        try:
            while True:
                ret, frame = vid_proc.read_frame()
                if not ret:
                    break
                    
                frame_count += 1
                
                # Frame rate control: bypass if tracking is enabled
                if not use_tracking and frame_count % process_every_n_frames != 0:
                    vid_proc.write_frame(frame) # Write original frame to maintain FPS
                    continue
                    
                # 1. Detect
                detections = self.detector.detect(frame, use_tracking=use_tracking)
                
                # 2. Assign to ROIs
                lane_assignments = []
                vehicles_per_lane: Dict[str, List[str]] = {lane: [] for lane in self.roi_mgr.lanes.keys()}
                
                for det in detections:
                    cx, cy = det['center']
                    cls = det['class']
                    
                    lane = self.roi_mgr.get_lane_for_point(cx, cy)
                    lane_assignments.append(lane)
                    
                    if lane:
                        vehicles_per_lane[lane].append(cls)
                        
                # 3. Translate to Canonical TrafficState
                timestamp = time.time()
                
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

                    if lane_str not in vehicles_per_lane:
                        lane_states[lane_enum] = LaneState(
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
                emergency = self._detect_emergency_in_detections(detections, lane_assignments)
                    
                state = TrafficState(
                    timestamp=timestamp,
                    frame_id=frame_count,
                    source=input_video,
                    has_tracking_data=(tracker is not None),
                    lanes=lane_states,
                    emergency=emergency
                )
                
                # 4. Visualize
                # Construct state dict expected by Harshadha's drawing method
                vis_state = {
                    "lanes": {
                        lane_str: {
                            "vehicle_count": lane_states[lane_enum].vehicle_count,
                            "occupancy": lane_states[lane_enum].occupancy
                        } for lane_str, lane_enum in self.LANE_MAPPING.items()
                    }
                }
                
                vid_proc.draw_polygons(frame, self.roi_mgr.get_polygons())
                vid_proc.draw_detections(frame, detections, lane_assignments)
                vid_proc.draw_state(frame, vis_state)
                vid_proc.write_frame(frame)
                
                yield state
                
        except Exception as e:
            logger.error(f"Error during vision processing at frame {frame_count}: {e}")
            raise
        finally:
            vid_proc.release()
            logger.info(f"Video processing complete. Annotated output saved to {output_video}")

    def process_image(self, input_image: str, output_image: str) -> TrafficState:
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
        
        for det in detections:
            cx, cy = det['center']
            cls = det['class']
            
            lane = self.roi_mgr.get_lane_for_point(cx, cy)
            lane_assignments.append(lane)
            
            if lane:
                vehicles_per_lane[lane].append(cls)
                
        # 3. Translate to Canonical TrafficState
        timestamp = time.time()
        
        lane_states = {}
        for lane_str, lane_enum in self.LANE_MAPPING.items():
            if lane_str not in vehicles_per_lane:
                lane_states[lane_enum] = LaneState()
                continue
                
            detected_classes = vehicles_per_lane[lane_str]
            veh_count, heavy_count, ped_count = self._classify_detections(detected_classes)
            occupancy = self.occ_calc.calculate_occupancy(lane_str, detected_classes)
            
            lane_states[lane_enum] = LaneState(
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
        vp.draw_polygons(frame, self.roi_mgr.get_polygons())
        vp.draw_detections(frame, detections, lane_assignments)
        vp.draw_state(frame, vis_state)
        
        cv2.imwrite(output_image, frame)
        logger.info(f"Image processing complete. Annotated output saved to {output_image}")
        
        return state

    def process_single_approach_video(
        self, input_video: str, approach: str, process_every_n_frames: int = 5, use_tracking: bool = False, is_live: bool = False
    ):
        """
        Process a video file for a single approach direction.
        All detections in the video are assigned to the specified approach.
        Returns the final LaneState, detection details, and EmergencyState from the last processed frame.
        If use_tracking is True, processes consecutive frames without skipping.
        """
        self._ensure_detector()
        approach = approach.lower()
        if approach not in self.SUPPORTED_APPROACHES:
            raise ValueError(f"Invalid approach '{approach}'. Must be one of: {self.SUPPORTED_APPROACHES}")

        try:
            vid_proc = VideoProcessor(input_video, output_path=None, is_live=is_live)
        except ValueError as e:
            raise ValueError(f"Could not open video file {input_video}") from e

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
                ret, frame = vid_proc.read_frame()
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
            vid_proc.release()

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
