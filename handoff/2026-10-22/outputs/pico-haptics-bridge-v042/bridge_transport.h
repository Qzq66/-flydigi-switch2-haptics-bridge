#pragma once
#include <stdint.h>
#include <stdbool.h>
void bridge_init(void);
void bridge_poll(bool upstream,bool vibration);
void bridge_record(uint8_t const *motors);
bool bridge_client_ready(void);
uint8_t bridge_diagnostic_byte(uint32_t offset);
void bridge_close(void);
void bridge_begin_drain(void);
bool bridge_drain_confirmed(void);
bool bridge_copy_input(uint8_t *out);
