#include "signal_output.h"

#ifdef ARDUINO
#include <Arduino.h>
#else
// Mocks for testing on host
#include <iostream>
bool mock_latch = false;
uint16_t shifted_data = 0;

void pinMode(int pin, int mode) {}
void digitalWrite(int pin, int val) {
    if (pin == LATCH_PIN) mock_latch = (val != 0);
}
#define OUTPUT 1
#define LOW 0
#define HIGH 1
#define MSBFIRST 1

void shiftOut(int dataPin, int clockPin, int bitOrder, uint8_t val) {
    // Keep track of shifted data
    // First byte sent becomes high byte of shifted_data (IC2), second byte becomes low byte (IC1)
    shifted_data = (shifted_data << 8) | val;
}
#endif

uint16_t map_logical_to_physical(const LogicalState& state) {
    uint16_t out = 0;
    
    // North
    if (state.north == SignalColor::RED) out |= (1 << 0);
    else if (state.north == SignalColor::YELLOW) out |= (1 << 1);
    else if (state.north == SignalColor::GREEN) out |= (1 << 2);
    
    // East
    if (state.east == SignalColor::RED) out |= (1 << 3);
    else if (state.east == SignalColor::YELLOW) out |= (1 << 4);
    else if (state.east == SignalColor::GREEN) out |= (1 << 5);
    
    // South
    if (state.south == SignalColor::RED) out |= (1 << 6);
    else if (state.south == SignalColor::YELLOW) out |= (1 << 7);
    else if (state.south == SignalColor::GREEN) out |= (1 << 8);
    
    // West
    if (state.west == SignalColor::RED) out |= (1 << 9);
    else if (state.west == SignalColor::YELLOW) out |= (1 << 10);
    else if (state.west == SignalColor::GREEN) out |= (1 << 11);
    
    return out;
}

void init_hardware() {
    pinMode(LATCH_PIN, OUTPUT);
    pinMode(CLOCK_PIN, OUTPUT);
    pinMode(DATA_PIN, OUTPUT);
    
    execute_safe_state();
}

void execute_physical_state(uint16_t physical_state) {
#ifndef ARDUINO
    shifted_data = 0; // reset for test mock
#endif
    
    uint8_t ic2_byte = (physical_state >> 8) & 0xFF;
    uint8_t ic1_byte = physical_state & 0xFF;
    
    digitalWrite(LATCH_PIN, LOW);
    shiftOut(DATA_PIN, CLOCK_PIN, MSBFIRST, ic2_byte);
    shiftOut(DATA_PIN, CLOCK_PIN, MSBFIRST, ic1_byte);
    digitalWrite(LATCH_PIN, HIGH);
}

void execute_safe_state() {
    LogicalState all_red = {SignalColor::RED, SignalColor::RED, SignalColor::RED, SignalColor::RED};
    uint16_t safe_bits = map_logical_to_physical(all_red);
    execute_physical_state(safe_bits);
}
