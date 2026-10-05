#include "protocol.h"

SignalColor parse_color(const String& color_str, bool& ok) {
    if (color_str == "RED") return SignalColor::RED;
    if (color_str == "YELLOW") return SignalColor::YELLOW;
    if (color_str == "GREEN") return SignalColor::GREEN;
    ok = false;
    return SignalColor::RED;
}

ParseResult parse_json_command(const String& json_str) {
    ParseResult result;
    result.valid = false;
    result.command_id = -1;

    // Use ArduinoJson to parse
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, json_str);

    if (error) {
        result.error_reason = "Malformed JSON";
        return result;
    }

    if (!doc.containsKey("version") || doc["version"] != 1) {
        result.error_reason = "Unsupported protocol version";
        return result;
    }

    if (!doc.containsKey("type")) {
        result.error_reason = "Missing type";
        return result;
    }
    
    result.type = doc["type"].as<String>();

    if (result.type == "PING") {
        result.valid = true;
        result.command_id = -2; // special ID for PING
        return result;
    }

    if (result.type != "SET_SIGNAL_STATE") {
        result.error_reason = "Unknown message type";
        return result;
    }

    if (!doc.containsKey("command_id")) {
        result.error_reason = "Missing command_id";
        return result;
    }
    
    result.command_id = doc["command_id"].as<int>();

    if (!doc.containsKey("payload") || !doc["payload"].containsKey("lanes")) {
        result.error_reason = "Missing payload or lanes";
        return result;
    }

    JsonObject lanes = doc["payload"]["lanes"];
    
    if (!lanes.containsKey("north") || !lanes.containsKey("south") || 
        !lanes.containsKey("east") || !lanes.containsKey("west")) {
        result.error_reason = "Missing lane";
        return result;
    }

    bool color_ok = true;
    result.state.north = parse_color(lanes["north"].as<String>(), color_ok);
    result.state.south = parse_color(lanes["south"].as<String>(), color_ok);
    result.state.east = parse_color(lanes["east"].as<String>(), color_ok);
    result.state.west = parse_color(lanes["west"].as<String>(), color_ok);

    if (!color_ok) {
        result.error_reason = "Invalid signal color";
        return result;
    }

    result.valid = true;
    return result;
}

String create_ack(int command_id) {
    StaticJsonDocument<128> doc;
    doc["version"] = 1;
    doc["type"] = "ACK";
    doc["command_id"] = command_id;
    JsonObject payload = doc.createNestedObject("payload");
    
    String output;
    serializeJson(doc, output);
    return output + "\n";
}

String create_nack(int command_id, const String& reason) {
    StaticJsonDocument<256> doc;
    doc["version"] = 1;
    doc["type"] = "NACK";
    doc["command_id"] = command_id;
    JsonObject payload = doc.createNestedObject("payload");
    payload["reason"] = reason;
    
    String output;
    serializeJson(doc, output);
    return output + "\n";
}

String create_error() {
    StaticJsonDocument<128> doc;
    doc["version"] = 1;
    doc["type"] = "ERROR";
    doc["command_id"] = -1; // Unknown command id
    JsonObject payload = doc.createNestedObject("payload");
    
    String output;
    serializeJson(doc, output);
    return output + "\n";
}

String create_pong(int last_command_id) {
    StaticJsonDocument<128> doc;
    doc["version"] = 1;
    doc["type"] = "PONG";
    JsonObject payload = doc.createNestedObject("payload");
    payload["last_command_id"] = last_command_id;
    
    String output;
    serializeJson(doc, output);
    return output + "\n";
}
