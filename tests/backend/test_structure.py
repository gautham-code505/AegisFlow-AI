import sys
import os

# Prevent actual FastAPI startup
os.environ["TESTING"] = "1"

def test_structural_imports():
    """Verify backend modules don't import app.py"""
    import backend.core
    import backend.runtime
    import backend.api.endpoints
    import backend.api.legacy
    import backend.api.websocket
    
    # Check if app is in any of their __dict__ or if they imported it
    assert not hasattr(backend.core, 'app')
    assert not hasattr(backend.runtime, 'app')
    assert not hasattr(backend.api.endpoints, 'app')
    assert not hasattr(backend.api.legacy, 'app')
    assert not hasattr(backend.api.websocket, 'app')

def test_app_composition_root():
    """Verify app.py acts as composition root and re-exports required globals"""
    import backend.app
    assert hasattr(backend.app, 'camera_manager')
    assert hasattr(backend.app, 'state_store')
    assert hasattr(backend.app, '_decision_event')
    assert hasattr(backend.app, '_approach_lane_states')
