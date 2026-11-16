/*
 * HOGP host probe: connect to the Flydigi controller over BLE HID, send one
 * short rumble output report sequence, disconnect, return to BOOTSEL.
 *
 * Scope and safety:
 *  - RAM-only ELF (PICO_NO_FLASH), no UF2, no Wi-Fi, no persistent settings.
 *  - Bluetooth TLV storage is linker-wrapped into an 8 KiB RAM bank.
 *  - Only after an explicit "SCAN" serial line; target must be in BLE pairing mode.
 *  - Pairing is Just Works and persisted only in RAM; nothing is written to Flash.
 *  - Every rumble candidate is bounded; zeros are sent before disconnect.
 *  - Any failure path powers the radio down and returns to BOOTSEL.
 */
#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "pico/bootrom.h"
#include "pico/cyw43_arch.h"
#include "btstack.h"
#include "ble/gatt-service/hids_host.h"
#include "ram_bank.h"

#define BOOT_LIMIT_US       180000000ull
#define SCAN_LIMIT_US       40000000ull
#define CONNECT_LIMIT_US    20000000ull
#define PAIR_LIMIT_US       30000000ull
#define HID_LIMIT_US        30000000ull
#define RUMBLE_STEP_US      1200000ull
#define RUMBLE_REPORT_ID    0x03u

static btstack_packet_callback_registration_t hci_reg;
static btstack_packet_callback_registration_t sm_reg;
static uint8_t hid_storage[768];
static hci_con_handle_t con_handle = HCI_CON_HANDLE_INVALID;
static uint16_t hids_cid;
static bd_addr_t best_addr;
static uint8_t best_type;
static int best_rssi;
static bool have_best;

/* 0 idle, 1 radio up, 2 scanning, 3 connecting, 4 pairing, 5 hid, 6 rumbling, 7 done */
static uint8_t phase;
static uint64_t boot_us, phase_us, step_us, connect_at_us;
static bool radio_up, radio_inited, hid_ready;
static unsigned rumble_index;
static unsigned connect_tries;

static const uint8_t RUMBLE[][8] = {
    {0x0F, 0x00, 0x00, 0x00, 0x00, 0x00, 0xC0, 0xC0},
    {0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xC0, 0xC0},
    {0x0F, 0x00, 0x00, 0x00, 0xC0, 0xC0, 0xC0, 0xC0},
    {0xC0, 0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00},
};
static const uint8_t RUMBLE_LEN[] = {8, 8, 8, 4};
static const uint8_t ZERO_REPORT[8] = {0};

static void finish(const char *reason) {
    if (phase == 7) return;
    printf("BTH2 DONE reason=%s phase=%u con=%u hid_ready=%d ram_errors=%lu ram_writes=%lu ram_erases=%lu\n",
           reason, phase, con_handle, hid_ready ? 1 : 0,
           (unsigned long)probe_ram_bank_errors(),
           (unsigned long)probe_ram_bank_writes(),
           (unsigned long)probe_ram_bank_erases());
    phase = 7;
}

/* Returns true when the AD payload advertises Microsoft (company id 0x0006)
 * or carries an Xbox controller name. */
static bool looks_like_xbox(const uint8_t *data, unsigned len) {
    unsigned i = 0;
    while (i + 1u < len) {
        unsigned field = data[i];
        if (field == 0 || i + 1u + field > len) break;
        uint8_t type = data[i + 1u];
        const uint8_t *value = data + i + 2u;
        unsigned vlen = field - 1u;
        if (type == 0xFFu && vlen >= 2u) {
            unsigned company = value[0] | (value[1] << 8);
            if (company == 0x0006u) return true;
        }
        if (type == 0x08u || type == 0x09u) {
            char name[32];
            unsigned n = vlen < 31u ? vlen : 31u;
            memcpy(name, value, n);
            name[n] = 0;
            if (strstr(name, "Xbox") || strstr(name, "xbox")) return true;
        }
        i += 1u + field;
    }
    return false;
}

/* Observed advertisements and scan responses, kept only in RAM. */
#define OBS_MAX 24
typedef struct {
    bd_addr_t addr;
    uint8_t type;
    uint8_t evt;
    int rssi;
    bool connectable;
    bool xbox;
    char name[32];
    uint64_t seen_us;
} obs_t;
static obs_t obs_tab[OBS_MAX];
static int obs_count;

static void copy_local_name(const uint8_t *data, unsigned dlen, char *out, unsigned cap) {
    out[0] = 0;
    unsigned i = 0;
    while (i + 1u < dlen) {
        unsigned field = data[i];
        if (field == 0 || i + 1u + field > dlen) break;
        uint8_t type = data[i + 1u];
        if ((type == 0x08u || type == 0x09u) && field > 1u) {
            unsigned n = field - 1u;
            if (n >= cap) n = cap - 1u;
            memcpy(out, data + i + 2u, n);
            out[n] = 0;
            for (unsigned k = 0; k < n; k++) {
                unsigned char c = (unsigned char)out[k];
                if (c < 0x20u || c > 0x7eu) out[k] = '?';
            }
            return;
        }
        i += 1u + field;
    }
}

static bool name_is_target(const char *n) {
    char b[32];
    unsigned k = 0;
    for (; n[k] && k < 31u; k++) {
        char c = n[k];
        if (c >= 'A' && c <= 'Z') c = (char)(c - 'A' + 'a');
        b[k] = c;
    }
    b[k] = 0;
    return strstr(b, "xbox") || strstr(b, "flydigi") || strstr(b, "apex") || strstr(b, "pro");
}

static void note_observation(const uint8_t *addr, uint8_t type, uint8_t evt, int rssi,
                             const uint8_t *data, unsigned dlen) {
    int idx = -1;
    for (int i = 0; i < obs_count; i++) {
        if (memcmp(obs_tab[i].addr, addr, 6) == 0) { idx = i; break; }
    }
    if (idx < 0) {
        if (obs_count < OBS_MAX) {
            idx = obs_count++;
        } else {
            idx = 0;
            for (int i = 1; i < OBS_MAX; i++) {
                if (obs_tab[i].seen_us < obs_tab[idx].seen_us) idx = i;
            }
        }
        memset(&obs_tab[idx], 0, sizeof(obs_tab[idx]));
        memcpy(obs_tab[idx].addr, addr, 6);
    }
    obs_tab[idx].type = type;
    obs_tab[idx].evt = evt;
    obs_tab[idx].rssi = rssi;
    obs_tab[idx].seen_us = time_us_64();
    if (evt == 0x00u || evt == 0x01u) obs_tab[idx].connectable = true;
    if (looks_like_xbox(data, dlen)) obs_tab[idx].xbox = true;
    char nm[32];
    copy_local_name(data, dlen, nm, sizeof(nm));
    if (nm[0]) snprintf(obs_tab[idx].name, sizeof(obs_tab[idx].name), "%s", nm);
}

static void hogp_handler(uint8_t packet_type, uint16_t channel, uint8_t *packet, uint16_t size) {
    (void)channel; (void)size;
    if (packet_type != HCI_EVENT_PACKET) return;
    uint8_t subevent = hci_event_packet_get_type(packet);
    switch (subevent) {
    case GATTSERVICE_SUBEVENT_HID_SERVICE_CONNECTED: {
        uint8_t status = gattservice_subevent_hid_service_connected_get_status(packet);
        hids_cid = gattservice_subevent_hid_service_connected_get_hids_cid(packet);
        printf("BTH2 HID connected status=%u cid=%u instances=%u\n", status, hids_cid,
               gattservice_subevent_hid_service_connected_get_num_instances(packet));
        if (status != 0) { finish("hid_connect_failed"); break; }
        uint8_t rc = hids_host_enable_notifications(hids_cid);
        printf("BTH2 HID notify rc=%u\n", rc);
        hid_ready = true;
        phase = 6; step_us = time_us_64();
        break;
    }
    case GATTSERVICE_SUBEVENT_HID_REPORT_WRITTEN: {
        printf("BTH2 HID report written cid=%u report_id=%u\n",
               gattservice_subevent_hid_report_written_get_hids_cid(packet),
               gattservice_subevent_hid_report_written_get_report_id(packet));
        break;
    }
    case GATTSERVICE_SUBEVENT_HID_SERVICE_DISCONNECTED:
        printf("BTH2 HID service disconnected\n");
        break;
    default:
        break;
    }
}

static void hci_handler(uint8_t packet_type, uint16_t channel, uint8_t *packet, uint16_t size) {
    (void)channel; (void)size;
    if (packet_type != HCI_EVENT_PACKET) return;
    switch (hci_event_packet_get_type(packet)) {
    case BTSTACK_EVENT_STATE:
        if (btstack_event_state_get_state(packet) == HCI_STATE_WORKING && phase == 1) {
            radio_up = true;
            printf("BTH2 PHASE SCAN\n");
            gap_set_scan_parameters(1, 0x60, 0x30);
            gap_start_scan();
            phase = 2; phase_us = time_us_64();
        }
        break;
    case GAP_EVENT_ADVERTISING_REPORT:
        if (phase != 2) break;
        {
            unsigned dlen = gap_event_advertising_report_get_data_length(packet);
            const uint8_t *data = gap_event_advertising_report_get_data(packet);
            bd_addr_t seen;
            gap_event_advertising_report_get_address(packet, seen);
            uint8_t type = gap_event_advertising_report_get_address_type(packet);
            uint8_t evt = gap_event_advertising_report_get_advertising_event_type(packet);
            int rssi = gap_event_advertising_report_get_rssi(packet);
            note_observation(seen, type, evt, rssi, data, dlen);
            char nm[32];
            copy_local_name(data, dlen, nm, sizeof(nm));
            printf("BTH2 OBS evt=%u addr=%02x%02x%02x%02x%02x%02x type=%u rssi=%d len=%u name=%s",
                   evt, seen[5], seen[4], seen[3], seen[2], seen[1], seen[0], type, rssi, dlen,
                   nm[0] ? nm : "-");
            if (evt != 0x03u) {
                printf(" data=");
                for (unsigned i = 0; i < dlen; i++) printf("%02x", data[i]);
            }
            printf("\n");
        }
        break;
    case HCI_EVENT_COMMAND_COMPLETE:
        if (hci_event_command_complete_get_return_parameters(packet)[0] != 0) {
            printf("BTH2 CMD opcode=0x%04x status=0x%02x\n",
                   hci_event_command_complete_get_command_opcode(packet),
                   hci_event_command_complete_get_return_parameters(packet)[0]);
        }
        break;
    case HCI_EVENT_LE_META:
        if (hci_event_le_meta_get_subevent_code(packet) == HCI_SUBEVENT_LE_CONNECTION_COMPLETE) {
            if (phase != 3) break;
            uint8_t status = hci_subevent_le_connection_complete_get_status(packet);
            if (status != 0) {
                printf("BTH2 CONNECT failed status=0x%02x\n", status);
                phase = 2; phase_us = time_us_64();
                gap_start_scan();
                break;
            }
            con_handle = hci_subevent_le_connection_complete_get_connection_handle(packet);
            printf("BTH2 CONNECTED handle=%u\n", con_handle);
            phase = 4; phase_us = time_us_64();
            sm_request_pairing(con_handle);
            printf("BTH2 PAIR request sent\n");
        }
        break;
    case HCI_EVENT_DISCONNECTION_COMPLETE:
        printf("BTH2 DISCONNECTED reason=0x%02x\n", hci_event_disconnection_complete_get_reason(packet));
        finish("peer_disconnected");
        break;
    default:
        break;
    }
}

static void sm_handler(uint8_t packet_type, uint16_t channel, uint8_t *packet, uint16_t size) {
    (void)channel; (void)size;
    if (packet_type != HCI_EVENT_PACKET) return;
    if (hci_event_packet_get_type(packet) == SM_EVENT_PAIRING_COMPLETE) {
        uint8_t status = sm_event_pairing_complete_get_status(packet);
        printf("BTH2 PAIRING status=%u\n", status);
        if (phase != 4) return;
        if (status != 0) { finish("pairing_failed"); return; }
        uint8_t rc = hids_host_connect(con_handle, hogp_handler, HID_PROTOCOL_MODE_REPORT, &hids_cid);
        printf("BTH2 HID connect rc=%u\n", rc);
        phase = 5; phase_us = time_us_64();
    }
}

static void rumble_tick(void) {
    if (phase != 6 || !hid_ready) return;
    uint64_t now = time_us_64();
    if (now - step_us < RUMBLE_STEP_US) return;
    step_us = now;
    if (rumble_index < sizeof(RUMBLE_LEN)) {
        uint8_t rc = hids_host_send_write_report(hids_cid, RUMBLE_REPORT_ID, HID_REPORT_TYPE_OUTPUT,
                                                 RUMBLE[rumble_index], RUMBLE_LEN[rumble_index]);
        printf("BTH2 RUMBLE try=%u len=%u rc=%u\n", rumble_index, RUMBLE_LEN[rumble_index], rc);
        rumble_index++;
        return;
    }
    /* Stop: zeros, then disconnect and leave. */
    hids_host_send_write_report(hids_cid, RUMBLE_REPORT_ID, HID_REPORT_TYPE_OUTPUT, ZERO_REPORT, sizeof ZERO_REPORT);
    printf("BTH2 RUMBLE stop\n");
    hids_host_disconnect(hids_cid);
    finish("rumbled");
}

int main(void) {
    boot_us = time_us_64();
    stdio_init_all();
    char command[12];
    unsigned used = 0;
    bool banner = false;
    while (phase != 7) {
        if (stdio_usb_connected() && !banner) {
            printf("BTH2 READY v=1 pair=just_works storage=ram report_id=0x%02x command=SCAN\n", RUMBLE_REPORT_ID);
            banner = true;
        }
        int ch = getchar_timeout_us(0);
        if (ch >= 0) {
            if (ch == '\r' || ch == '\n') {
                command[used] = 0;
                if (!strcmp(command, "CANCEL")) finish("cancelled");
                if (!strcmp(command, "SCAN") && phase == 0) {
                    phase = 1; phase_us = time_us_64();
                    if (cyw43_arch_init()) { finish("radio_init_failed"); break; }
                    radio_inited = true;
                    l2cap_init();
                    sm_init();
                    sm_set_io_capabilities(IO_CAPABILITY_NO_INPUT_NO_OUTPUT);
                    sm_set_authentication_requirements(SM_AUTHREQ_BONDING);
                    gatt_client_init();
                    hids_host_init(hid_storage, sizeof hid_storage);
                    hci_reg.callback = &hci_handler;
                    hci_add_event_handler(&hci_reg);
                    sm_reg.callback = &sm_handler;
                    sm_add_event_handler(&sm_reg);
                    hci_power_control(HCI_POWER_ON);
                }
                used = 0;
            } else if (used < sizeof command - 1) {
                command[used++] = (char)ch;
            } else {
                used = 0;
            }
        }
        if (phase) cyw43_arch_poll();
        rumble_tick();
        uint64_t now = time_us_64();
        if (phase == 3 && connect_at_us && now >= connect_at_us) {
            connect_at_us = 0;
            printf("BTH2 CONNECT start rssi=%d\n", best_rssi);
            if (gap_connect(best_addr, best_type)) finish("connect_start_failed");
        }
        if (phase == 2) {
            int pick = -1;
            int pick_score = -1;
            uint64_t now_us = time_us_64();
            for (int i = 0; i < obs_count; i++) {
                if (!obs_tab[i].connectable) continue;
                if (now_us - obs_tab[i].seen_us > 1500000ull) continue;
                int score = 0;
                if (name_is_target(obs_tab[i].name)) score += 3;
                if (obs_tab[i].xbox) score += 2;
                if (score >= 2 && score > pick_score) { pick_score = score; pick = i; }
            }
            if (pick >= 0) {
                memcpy(best_addr, obs_tab[pick].addr, 6);
                best_type = obs_tab[pick].type;
                best_rssi = obs_tab[pick].rssi;
                have_best = true;
                printf("BTH2 BEST name=%s score=%d rssi=%d\n",
                       obs_tab[pick].name[0] ? obs_tab[pick].name : "-", pick_score, best_rssi);
            }
        }
        if (phase == 2 && have_best) {
            gap_stop_scan();
            phase = 3;
            phase_us = now;
            connect_at_us = now + 300000ull;
        }
        if (phase == 2 && now - phase_us > SCAN_LIMIT_US) finish("scan_timeout");
        if (phase == 3 && now - phase_us > CONNECT_LIMIT_US) {
            hci_send_cmd(&hci_le_create_connection_cancel);
            if (connect_tries < 2) {
                connect_tries++;
                printf("BTH2 CONNECT retry=%u\n", connect_tries);
                have_best = false;
                phase = 2; phase_us = time_us_64();
                gap_start_scan();
            } else {
                finish("connect_timeout");
            }
        }
        if (phase == 4 && now - phase_us > PAIR_LIMIT_US) finish("pair_timeout");
        if (phase == 5 && now - phase_us > HID_LIMIT_US) finish("hid_timeout");
        if (phase == 6 && now - phase_us > 30000000ull) finish("rumble_timeout");
        if (now - boot_us > BOOT_LIMIT_US) finish("boot_limit");
        if (probe_ram_bank_errors()) finish("ram_bank_error");
        sleep_ms(1);
    }
    if (radio_up) hci_power_control(HCI_POWER_OFF);
    if (radio_inited) {
        uint64_t until = time_us_64() + 500000ull;
        while (hci_get_state() != HCI_STATE_OFF && time_us_64() < until) {
            cyw43_arch_poll();
            sleep_ms(1);
        }
        cyw43_arch_deinit();
    }
    sleep_ms(300);
    reset_usb_boot(0, 0);
    return 0;
}
