#include "signal_output.h"
#include <iostream>
#include <string>

// Test helper
void test_mapping(std::string name, LogicalState state, uint16_t expected) {
    uint16_t actual = map_logical_to_physical(state);
    if (actual == expected) {
        std::cout << "[PASS] " << name << "\n";
    } else {
        std::cout << "[FAIL] " << name << " - Expected: " << expected << " Got: " << actual << "\n";
    }
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
        
    std::cout << "Done.\n";
    return 0;
}
