#include "signal_output.h"
#include <iostream>
#include <string>

int failures = 0;

// Test helper
void test_mapping(std::string name, LogicalState state, uint16_t expected) {
    uint16_t actual = map_logical_to_physical(state);
    if (actual == expected) {
        std::cout << "[PASS] " << name << "\n";
    } else {
        std::cout << "[FAIL] " << name << " - Expected: " << expected << " Got: " << actual << "\n";
        failures++;
    }
}

void check(std::string name, bool condition) {
    if (condition) {
        std::cout << "[PASS] " << name << "\n";
    } else {
        std::cout << "[FAIL] " << name << "\n";
        failures++;
    }
}

const SignalColor R = SignalColor::RED;
const SignalColor Y = SignalColor::YELLOW;
const SignalColor G = SignalColor::GREEN;

// LogicalState field order is {north, south, east, west}
void test_conflicts() {
    std::cout << "Running Conflict Check Tests...\n";
    check("ALL_RED is conflict-free", is_conflict_free({R, R, R, R}));
    check("NORTH+SOUTH GREEN is conflict-free", is_conflict_free({G, G, R, R}));
    check("EAST+WEST GREEN is conflict-free", is_conflict_free({R, R, G, G}));
    check("NORTH+SOUTH YELLOW is conflict-free", is_conflict_free({Y, Y, R, R}));
    check("NORTH GREEN + EAST GREEN is rejected", !is_conflict_free({G, R, G, R}));
    check("SOUTH GREEN + WEST GREEN is rejected", !is_conflict_free({R, G, R, G}));
    check("NORTH YELLOW + EAST GREEN is rejected", !is_conflict_free({Y, R, G, R}));
    check("ALL GREEN is rejected", !is_conflict_free({G, G, G, G}));
}

void test_clearance() {
    std::cout << "Running Watchdog Clearance Tests...\n";
    LogicalState y = to_clearance_yellow({G, G, R, R});
    check("GREEN becomes YELLOW", y.north == Y && y.south == Y && y.east == R && y.west == R);
    LogicalState same = to_clearance_yellow({R, R, Y, R});
    check("non-GREEN unchanged", same.north == R && same.south == R && same.east == Y && same.west == R);
    check("has_green detects GREEN", has_green({R, R, R, G}));
    check("has_green false for YELLOW/RED", !has_green({Y, R, R, R}));
}

int main() {
    std::cout << "Running Bit Mapping Tests...\n";
    
    // ALL_RED
    // N:RED(0), E:RED(3), S:RED(6), W:RED(9) -> bits 0,3,6,9 = 1 + 8 + 64 + 512 = 585 (0x249)
    test_mapping("ALL_RED", 
        {SignalColor::RED, SignalColor::RED, SignalColor::RED, SignalColor::RED}, 
        0x0249);
        
    // NORTH_GREEN
    // N:GREEN(2), E:RED(3), S:RED(6), W:RED(9) -> bits 2,3,6,9 = 4 + 8 + 64 + 512 = 588 (0x24C)
    test_mapping("NORTH_GREEN", 
        {SignalColor::GREEN, SignalColor::RED, SignalColor::RED, SignalColor::RED}, 
        0x024C);
        
    // NORTH_YELLOW
    // N:YELLOW(1), E:RED(3), S:RED(6), W:RED(9) -> bits 1,3,6,9 = 2 + 8 + 64 + 512 = 586 (0x24A)
    test_mapping("NORTH_YELLOW", 
        {SignalColor::YELLOW, SignalColor::RED, SignalColor::RED, SignalColor::RED}, 
        0x024A);

    // EAST_GREEN
    // N:RED(0), E:GREEN(5), S:RED(6), W:RED(9) -> bits 0,5,6,9 = 1 + 32 + 64 + 512 = 609 (0x261)
    test_mapping("EAST_GREEN", 
        {SignalColor::RED, SignalColor::RED, SignalColor::GREEN, SignalColor::RED}, 
        0x0261);

    // EAST_YELLOW
    // N:RED(0), E:YELLOW(4), S:RED(6), W:RED(9) -> bits 0,4,6,9 = 1 + 16 + 64 + 512 = 593 (0x251)
    test_mapping("EAST_YELLOW", 
        {SignalColor::RED, SignalColor::RED, SignalColor::YELLOW, SignalColor::RED}, 
        0x0251);

    // SOUTH_GREEN
    // N:RED(0), E:RED(3), S:GREEN(8), W:RED(9) -> bits 0,3,8,9 = 1 + 8 + 256 + 512 = 777 (0x309)
    test_mapping("SOUTH_GREEN", 
        {SignalColor::RED, SignalColor::GREEN, SignalColor::RED, SignalColor::RED}, 
        0x0309);

    // SOUTH_YELLOW
    // N:RED(0), E:RED(3), S:YELLOW(7), W:RED(9) -> bits 0,3,7,9 = 1 + 8 + 128 + 512 = 649 (0x289)
    test_mapping("SOUTH_YELLOW", 
        {SignalColor::RED, SignalColor::YELLOW, SignalColor::RED, SignalColor::RED}, 
        0x0289);

    // WEST_GREEN
    // N:RED(0), E:RED(3), S:RED(6), W:GREEN(11) -> bits 0,3,6,11 = 1 + 8 + 64 + 2048 = 2121 (0x849)
    test_mapping("WEST_GREEN", 
        {SignalColor::RED, SignalColor::RED, SignalColor::RED, SignalColor::GREEN}, 
        0x0849);

    // WEST_YELLOW
    // N:RED(0), E:RED(3), S:RED(6), W:YELLOW(10) -> bits 0,3,6,10 = 1 + 8 + 64 + 1024 = 1097 (0x449)
    test_mapping("WEST_YELLOW", 
        {SignalColor::RED, SignalColor::RED, SignalColor::RED, SignalColor::YELLOW}, 
        0x0449);
        
    test_conflicts();
    test_clearance();

    std::cout << "Done. Failures: " << failures << "\n";
    return failures == 0 ? 0 : 1;
}
