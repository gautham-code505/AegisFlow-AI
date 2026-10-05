import json
import time
import serial

PORT = "COM4"
BAUD = 115200

ser = serial.Serial(PORT, BAUD, timeout=0.2)
time.sleep(2)

print("\n=== AegisFlow RESET-ONLY TEST ===")
print("COM4 connected.")
print("Sending one command first so the ESP32 has a known command_id...")
print("Then press EN/RST whenever you are ready.")
print("We are looking for: last_command_id = -1\n")

command = {
    "version": 1,
    "type": "SET_SIGNAL_STATE",
    "command_id": 1,
    "payload": {
        "lanes": {
            "north": "GREEN",
            "south": "RED",
            "east": "RED",
            "west": "RED"
        },
        "timestamp": 1.0
    }
}

ser.write((json.dumps(command) + "\n").encode())
ser.flush()

deadline = time.time() + 3
while time.time() < deadline:
    line = ser.readline().decode(errors="ignore").strip()
    if not line:
        continue
    print("RX:", line)
    try:
        msg = json.loads(line)
        if msg.get("type") == "ACK" and msg.get("command_id") == 1:
            print("\nACK received. ESP32 is now in known state.")
            break
    except json.JSONDecodeError:
        pass

print("\n>>> NOW PRESS EN/RST ON THE ESP32 <<<")
print("Press it once. Then wait.")
print("The test will keep running for 20 seconds.\n")

end = time.time() + 20

while time.time() < end:
    ping = {
        "version": 1,
        "type": "PING",
        "command_id": None,
        "payload": {}
    }

    ser.write((json.dumps(ping) + "\n").encode())
    ser.flush()

    wait_until = time.time() + 0.35

    while time.time() < wait_until:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue

        print("RX:", line)

        try:
            msg = json.loads(line)

            if msg.get("type") == "PONG":
                last_id = msg.get("payload", {}).get("last_command_id")
                print("    last_command_id =", last_id)

                if last_id == -1:
                    print("\n========================================")
                    print("RESET DETECTED SUCCESSFULLY")
                    print("ESP32 reported last_command_id = -1")
                    print("========================================")
                    ser.close()
                    raise SystemExit

        except json.JSONDecodeError:
            print("    (boot/non-JSON text)")

    time.sleep(0.2)

print("\n========================================")
print("RESET NOT DETECTED")
print("No PONG with last_command_id = -1")
print("========================================")

ser.close()
