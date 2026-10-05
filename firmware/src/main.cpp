#include <Arduino.h>
#include "signal_output.h"
#include "protocol.h"

String inputBuffer = "";
int last_command_id = -1;

void setup() {
    // 1. Start Serial
    Serial.begin(115200);
    while (!Serial) {
        ; // wait for serial port to connect
    }

    // 2. Startup Safety: Immediately go to ALL_RED
    init_hardware();
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

    // Map logical to physical bits
    uint16_t physical_bits = map_logical_to_physical(result.state);

    // Latch physical state
    execute_physical_state(physical_bits);

    // Update last command id
    last_command_id = result.command_id;

    // Send ACK only AFTER successful latch
    Serial.print(create_ack(result.command_id));
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
}
