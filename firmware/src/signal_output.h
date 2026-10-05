#ifndef SIGNAL_OUTPUT_H
#define SIGNAL_OUTPUT_H

#include <stdint.h>

#define LATCH_PIN 5
#define CLOCK_PIN 18
#define DATA_PIN 23

enum class SignalColor {
    RED,
    YELLOW,
    GREEN
};

struct LogicalState {
    SignalColor north;
    SignalColor south;
    SignalColor east;
    SignalColor west;
};

void init_hardware();
uint16_t map_logical_to_physical(const LogicalState& state);
void execute_physical_state(uint16_t physical_state);
void execute_safe_state();

#endif // SIGNAL_OUTPUT_H
