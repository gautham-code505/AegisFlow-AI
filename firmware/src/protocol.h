#ifndef PROTOCOL_H
#define PROTOCOL_H

#include "signal_output.h"
#include <ArduinoJson.h>

struct ParseResult {
    bool valid;
    String type;
    int command_id;
    LogicalState state;
    String error_reason;
};

ParseResult parse_json_command(const String& json_str);
String create_ack(int command_id);
String create_nack(int command_id, const String& reason);
String create_error();
String create_pong(int last_command_id);

#endif // PROTOCOL_H
