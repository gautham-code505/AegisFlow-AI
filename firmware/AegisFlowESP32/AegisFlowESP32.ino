/*
 * AegisFlow ESP32 — Arduino IDE Sketch
 * =====================================================
 * Board:   ESP32 Dev Module
 * Port:    COM4
 * Baud:    115200 (Serial Monitor)
 *
 * GPIO Assignments (DO NOT CHANGE):
 *   GPIO23 = DATA  (SN74HC595N serial data)
 *   GPIO18 = CLOCK (SN74HC595N shift clock)
 *   GPIO5  = LATCH (SN74HC595N output latch)
 *
 * Dependencies (install via Arduino Library Manager):
 *   ArduinoJson  >= 6.x  (by Benoit Blanchon)
 *
 * Sketch entry-point:
 *   setup() and loop() are implemented in main.cpp.
 *   This .ino file is the Arduino IDE project anchor only.
 *   Arduino IDE automatically compiles all .cpp files in this folder.
 *
 * Source files in this folder:
 *   main.cpp        — setup(), loop(), process_command()
 *   signal_output.h — GPIO pin definitions, LogicalState struct, function decls
 *   signal_output.cpp — map_logical_to_physical(), execute_physical_state(),
 *                       init_hardware(), execute_safe_state()
 *   protocol.h      — ParseResult struct, parse/create function decls
 *   protocol.cpp    — JSON parsing via ArduinoJson, ACK/NACK/ERROR builders
 */

// All implementation is in the .cpp files above.
// This file intentionally contains no code so that Arduino IDE does not
// produce a duplicate setup()/loop() definition error.
