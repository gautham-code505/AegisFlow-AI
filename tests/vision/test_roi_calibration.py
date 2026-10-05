import pytest
import os
import json
import numpy as np
from vision.roi import ROIManager

@pytest.fixture
def test_config_path(tmp_path):
    config = {
        "camera_resolution": [640, 480],
        "lanes": {
            "north": {
                "capacity": 10,
                "polygon": [[250, 0], [390, 0], [390, 180], [250, 180]]
            },
            "south": {
                "capacity": 10,
                "polygon": [[250, 300], [390, 300], [390, 480], [250, 480]]
            }
        }
    }
    path = tmp_path / "test_roi_config.json"
    with open(path, "w") as f:
        json.dump(config, f)
    return str(path)

@pytest.fixture
def normalized_config_path(tmp_path):
    config = {
        # Note: no camera_resolution needed if already normalized
        "lanes": {
            "north": {
                "capacity": 10,
                "polygon": [[0.39, 0.0], [0.60, 0.0], [0.60, 0.375], [0.39, 0.375]]
            }
        }
    }
    path = tmp_path / "test_norm_config.json"
    with open(path, "w") as f:
        json.dump(config, f)
    return str(path)

def test_legacy_config_normalization(test_config_path):
    """Test that legacy 640x480 config is parsed into normalized coordinates."""
    roi_mgr = ROIManager(test_config_path)
    
    # Internal lanes should be normalized now
    north_poly = roi_mgr.lanes["north"]
    assert np.max(north_poly) <= 1.0
    
    # [250, 0] -> [250/640, 0/480] = [0.390625, 0]
    expected_x = 250 / 640.0
    assert np.isclose(north_poly[0][0][0], expected_x)

def test_normalized_config_remains_normalized(normalized_config_path):
    """Test that if the config is already normalized, it doesn't get divided again."""
    roi_mgr = ROIManager(normalized_config_path)
    north_poly = roi_mgr.lanes["north"]
    assert np.isclose(north_poly[0][0][0], 0.39)

def test_roi_geometric_invariance(test_config_path):
    """Test that a physical centroid resolves to the same ROI across resolutions."""
    roi_mgr = ROIManager(test_config_path)
    
    # Center of North approach at 640x480 is approximately (320, 90)
    assert roi_mgr.get_lane_for_point(320, 90, 640, 480) == "north"
    
    # Same physical point at 1280x960 (4:3 scaling) -> (640, 180)
    assert roi_mgr.get_lane_for_point(640, 180, 1280, 960) == "north"
    
    # Same physical point at 1920x1440 (4:3 scaling) -> (960, 270)
    # x scale = 1920 / 640 = 3.0 -> x = 960
    # y scale = 1440 / 480 = 3.0 -> y = 270
    assert roi_mgr.get_lane_for_point(960, 270, 1920, 1440) == "north"

def test_different_aspect_ratio_rejected(test_config_path):
    """Test 1280x720 (16:9) aspect ratio mismatch is explicitly rejected."""
    roi_mgr = ROIManager(test_config_path)
    
    # Even if point mathematically falls in the zone, physical meaning is lost
    assert roi_mgr.get_lane_for_point(640, 135, 1280, 720) is None
    
    # Visualization should also return empty to prevent drawing false geometries
    polys = roi_mgr.get_polygons(1280, 720)
    assert len(polys) == 0

def test_boundary_behavior(test_config_path):
    """Test point on the boundary is counted (cv2.pointPolygonTest == 0)."""
    roi_mgr = ROIManager(test_config_path)
    
    # The edge of North is at x=250 at 640x480
    assert roi_mgr.get_lane_for_point(250, 90, 640, 480) == "north"

def test_outside_behavior(test_config_path):
    """Test that points outside all ROIs return None."""
    roi_mgr = ROIManager(test_config_path)
    
    # (100, 100) is far left of North (x=250)
    assert roi_mgr.get_lane_for_point(100, 100, 640, 480) is None
    
    # At 1280x960, (200, 200) is also far left
    assert roi_mgr.get_lane_for_point(200, 200, 1280, 960) is None

def test_get_polygons_round_trip(test_config_path):
    """Test that get_polygons scales normalized coordinates back correctly."""
    roi_mgr = ROIManager(test_config_path)
    
    scaled_polys = roi_mgr.get_polygons(1280, 960) # Must use 4:3
    north = scaled_polys["north"]
    
    # [250/640 * 1280, 0] = [500, 0]
    assert north[0][0][0] == 500
    assert north[0][0][1] == 0
    # Type should be int32 for cv2.polylines
    assert north.dtype == np.int32
