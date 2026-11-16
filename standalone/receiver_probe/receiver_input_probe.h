#pragma once
#include <stdint.h>
#define RECEIVER_PROBE_PACKETS 32u
#define RECEIVER_PROBE_PACKET_BYTES 64u
/* Raw packets only. These are not XINPUT_GAMEPAD structures. */
typedef struct {
    uint16_t vid, pid, packet_size;
    uint8_t interface_number, endpoint_in;
    uint32_t packets, disconnects;
    uint8_t error, complete;
    uint8_t lengths[RECEIVER_PROBE_PACKETS];
    uint8_t data[RECEIVER_PROBE_PACKETS][RECEIVER_PROBE_PACKET_BYTES];
} receiver_probe_snapshot_t;
/* Read via a future explicitly selected diagnostic transport. No native I/O. */
receiver_probe_snapshot_t const *receiver_probe_snapshot(void);
