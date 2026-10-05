import time
import sys
import os
import logging
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app import app
from backend import core

def run():
    logging.basicConfig(level=logging.INFO)
    print("Starting TestClient...")
    with TestClient(app) as client:
        print(f"Adapter status: {core.physical_adapter.status}")
        for _ in range(30):
            if core.physical_adapter.status.value == "CONNECTED":
                print("Connected!")
                break
            time.sleep(0.1)
        else:
            print("Failed to connect.")
            return

        print("Sending heavy-north...")
        resp = client.post("/api/v1/demo/heavy-north")
        print("Response:", resp.json())
        
        prev_ack = core.physical_adapter.last_acked_command_id
        for _ in range(50):
            if core.physical_adapter.last_acked_command_id != prev_ack:
                print(f"ACK received! {core.physical_adapter.last_acked_command_id}")
                break
            time.sleep(0.1)
        
if __name__ == "__main__":
    run()
