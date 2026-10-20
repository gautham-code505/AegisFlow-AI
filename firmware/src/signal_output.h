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

// Defense-in-depth: true when no NORTH/SOUTH signal is non-RED at the same
// time as an EAST/WEST signal. The backend ConflictMatrix is primary; the
// firmware refuses to latch a state that violates it.
bool is_conflict_free(const LogicalState& state);
bool has_green(const LogicalState& state);
// Same state with every GREEN replaced by YELLOW (local clearance interval).
LogicalState to_clearance_yellow(const LogicalState& state);

#endif // SIGNAL_OUTPUT_H
