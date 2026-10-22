#pragma once
#include <stdbool.h>
#include <stdint.h>
#define CAPTURE_SLOT0_OFFSET 0x000e0000u
#define CAPTURE_SLOT1_OFFSET 0x000f0000u
#define CAPTURE_SLOT_SIZE 65536u
void capture_init(uint64_t now);
void capture_mounted(void);
void capture_record(uint64_t now,uint8_t id,uint8_t const *p,uint16_t size);
bool capture_due(uint64_t now);
void capture_preview(uint8_t const *diagnostics,uint64_t now);
uint8_t capture_preview_byte(uint32_t offset);
void capture_finish(uint8_t const *diagnostics,uint64_t now);
