#pragma once
#include <stdbool.h>
#include <stdint.h>
enum { BRIDGE_LIVE_MS=120000, BRIDGE_BOOT_MS=180000,
       BRIDGE_REGISTRATION_LIMIT_MS=175000, BRIDGE_REBOOT_MS=240000 };
static inline bool session_due(uint64_t boot_ms,bool live_started,uint64_t live_ms,bool journal_full){
    return journal_full || boot_ms>=BRIDGE_BOOT_MS || (live_started && live_ms>=BRIDGE_LIVE_MS);
}
