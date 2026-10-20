#include <Arduino.h>
#include "signal_output.h"
#include "protocol.h"

// Communication watchdog
// ----------------------
// The backend is the authority for signal state, but if it stops talking
// (backend crash, USB unplugged, laptop asleep) the LEDs must not freeze on
// whatever they last showed. If no valid message (SET_SIGNAL_STATE or PING)
// arrives for COMMS_TIMEOUT_MS, the firmware clears the junction locally:
// any GREEN goes YELLOW for WATCHDOG_YELLOW_MS, then ALL_RED.
// The backend sends a state every ~1 s and PINGs when idle, so 3 s of
// silence means the host is gone. Values mirror the backend's 3 s stale-input
// threshold and the 3 s YELLOW_SECONDS clearance.
const unsigned long COMMS_TIMEOUT_MS = 3000;
const unsigned long WATCHDOG_YELLOW_MS = 3000;

enum class WatchdogPhase {
    NORMAL,          // following host commands
    YELLOW_CLEARANCE,// host silent; showing local yellow clearance
    SAFE_ALL_RED     // host silent; holding ALL_RED until a new command
};

String inputBuffer = "";
int last_command_id = -1;

const LogicalState ALL_RED_STATE = {SignalColor::RED, SignalColor::RED, SignalColor::RED, SignalColor::RED};
LogicalState current_state = ALL_RED_STATE;
unsigned long last_valid_rx_ms = 0;
unsigned long clearance_start_ms = 0;
WatchdogPhase watchdog_phase = WatchdogPhase::NORMAL;

void latch_state(const LogicalState& state) {
    execute_physical_state(map_logical_to_physical(state));
    current_state = state;
}

void enter_safe_all_red() {
    execute_safe_state();
    current_state = ALL_RED_STATE;
    watchdog_phase = WatchdogPhase::SAFE_ALL_RED;
}

void setup() {
    // 1. Start Serial
    Serial.begin(115200);
    while (!Serial) {
        ; // wait for serial port to connect
    }

    // 2. Startup Safety: Immediately go to ALL_RED
    init_hardware();
    current_state = ALL_RED_STATE;
    last_valid_rx_ms = millis();
}

void process_command(const String& cmd_str) {
    ParseResult result = parse_json_command(cmd_str);

    if (!result.valid) {
        if (result.command_id != -1) {
            Serial.print(create_nack(result.command_id, result.error_reason));
        } else {
            Serial.print(create_error());
        }
        return;
    }

    // Any valid message proves the host is alive.
    last_valid_rx_ms = millis();

    if (result.type == "PING") {
        Serial.print(create_pong(last_command_id));
        return;
    }

    // Handle duplicate command IDs to prevent re-executing
    // Note: In a real system we might just re-latch, but we shouldn't fail.
    // We will just execute and ACK it.
    if (result.command_id == last_command_id) {
        // Just ACK it again in case the first ACK was lost
        Serial.print(create_ack(result.command_id));
        return;
    }

    // Defense-in-depth: never latch conflicting N/S and E/W signals.
    if (!is_conflict_free(result.state)) {
        Serial.print(create_nack(result.command_id, "Conflicting signal state"));
        return;
    }

    // Finish a watchdog yellow clearance before accepting new commands.
    if (watchdog_phase == WatchdogPhase::YELLOW_CLEARANCE) {
        Serial.print(create_nack(result.command_id, "Watchdog clearance in progress"));
        return;
    }

    // Map logical to physical bits and latch
    latch_state(result.state);
    watchdog_phase = WatchdogPhase::NORMAL;

    // Update last command id
    last_command_id = result.command_id;

    // Send ACK only AFTER successful latch
    Serial.print(create_ack(result.command_id));
}

void run_comms_watchdog() {
    unsigned long now = millis();

    if (watchdog_phase == WatchdogPhase::NORMAL && now - last_valid_rx_ms > COMMS_TIMEOUT_MS) {
        // Report -1 in the next PONG so the backend resynchronises its state.
        last_command_id = -1;
        if (has_green(current_state)) {
            latch_state(to_clearance_yellow(current_state));
            clearance_start_ms = now;
            watchdog_phase = WatchdogPhase::YELLOW_CLEARANCE;
        } else {
            enter_safe_all_red();
        }
    } else if (watchdog_phase == WatchdogPhase::YELLOW_CLEARANCE && now - clearance_start_ms >= WATCHDOG_YELLOW_MS) {
        enter_safe_all_red();
    }
}

void loop() {
    // Read serial data until newline
    while (Serial.available() > 0) {
        char inChar = (char)Serial.read();

        if (inChar == '\n') {
            process_command(inputBuffer);
            inputBuffer = "";
        } else if (inChar != '\r') {
            inputBuffer += inChar;

            // Protect against buffer overflow from runaway serial input
            if (inputBuffer.length() > 512) {
                inputBuffer = "";
                Serial.print(create_error());
            }
        }
    }

    run_comms_watchdog();
}
