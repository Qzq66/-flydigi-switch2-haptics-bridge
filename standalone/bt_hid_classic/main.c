/*
 * Classic (BR/EDR) HID host probe for the Flydigi controller.
 *
 * Scope and safety:
 *  - RAM-only ELF (PICO_NO_FLASH); no UF2, no Flash writes, no Wi-Fi.
 *  - BTstack TLV storage is link-wrapped into an 8 KiB RAM bank.
 *  - General bonding allowed; host keys stay in RAM. Peripheral may retain a bond.
 *  - Only after an explicit "SCAN" serial line; the controller must be in its
 *    Bluetooth pairing screen.
 *  - Diagnostics only: no output or feature reports.
 *  - Every failure path powers the radio down and returns to BOOTSEL.
 */
#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "pico/stdio_usb.h"
#include "pico/bootrom.h"
#include "pico/cyw43_arch.h"
#include "btstack.h"
#include "classic/hid_host.h"
#include "ram_bank.h"
#include "security_trace.h"

#define BOOT_LIMIT_US       180000000ull
#define INQUIRY_SECONDS     8
#define MAX_INQUIRY_TRIES   1
#define CONNECT_LIMIT_US    25000000ull

static btstack_packet_callback_registration_t hci_reg;
static uint8_t hid_descriptor_storage[1024];
static uint16_t hid_cid;
static bd_addr_t target_addr;
static bd_addr_t allowed_addr;
static bool target_configured;
static bool have_target;
static int target_rssi;
static uint32_t target_cod;
static char target_name[64];

static int phase; /* 0 idle, 1 inquiry, 2 connecting, 3 hid open, 7 done */
static uint64_t boot_us;
static uint64_t phase_us;
static bool radio_initialized;
static unsigned inquiry_tries;


static void finish(const char *reason) {
    if (phase == 7) return;
    phase = 7;
    printf("BTH3 DONE reason=%s hid_cid=%u ram_errors=%u ram_writes=%u ram_erases=%u\n",
           reason, (unsigned)hid_cid, (unsigned)probe_ram_bank_errors(),
           (unsigned)probe_ram_bank_writes(), (unsigned)probe_ram_bank_erases());
}

static void hid_handler(uint8_t packet_type, uint16_t channel, uint8_t *packet, uint16_t size) {
    (void)channel;
    if (packet_type != HCI_EVENT_PACKET || size < 3 || (unsigned)packet[1]+2 > size) return;
    if (hci_event_packet_get_type(packet) != HCI_EVENT_HID_META) return;
    switch (hci_event_hid_meta_get_subevent_code(packet)) {
    case HID_SUBEVENT_INCOMING_CONNECTION:
        printf("BTH3 INCOMING cid=%u (not accepted)\n", (unsigned)hid_subevent_incoming_connection_get_hid_cid(packet));
        break;
    case HID_SUBEVENT_CONNECTION_OPENED: {
        if (size < 13) { finish("short_hid_open"); break; }
        uint8_t status = hid_subevent_connection_opened_get_status(packet);
        hid_cid = hid_subevent_connection_opened_get_hid_cid(packet);
        printf("BTH3 HID_OPEN status=0x%02x cid=%u\n", status, (unsigned)hid_cid);
        if (status != ERROR_CODE_SUCCESS) { finish("hid_open_failed"); break; }
        phase = 3; phase_us = time_us_64();
        break;
    }
    case HID_SUBEVENT_DESCRIPTOR_AVAILABLE: {
        if (size < 6) { finish("short_descriptor_event"); break; }
        uint8_t status = hid_subevent_descriptor_available_get_status(packet);
        uint16_t len = hid_descriptor_storage_get_descriptor_len(hid_cid);
        printf("BTH3 DESCRIPTOR status=0x%02x len=%u\n", status, (unsigned)len);
        if (status == ERROR_CODE_SUCCESS) {
            const uint8_t *desc = hid_descriptor_storage_get_descriptor_data(hid_cid);
            if (!desc || !len || len > sizeof(hid_descriptor_storage)) { finish("invalid_descriptor"); break; }
            printf("BTH3 DESCRIPTOR_HEX ");
            for (unsigned i=0;i<len;i++) printf("%02x", desc[i]);
            printf("\n");
            finish("descriptor_captured_no_output");
        } else {
            finish("descriptor_missing");
        }
        break;
    }
    case HID_SUBEVENT_SET_REPORT_RESPONSE:
        printf("BTH3 SET_REPORT_RESPONSE handshake=0x%02x\n",
               hid_subevent_set_report_response_get_handshake_status(packet));
        break;
    case HID_SUBEVENT_GET_REPORT_RESPONSE:
        break;
    case HID_SUBEVENT_CAN_SEND_NOW:
        break;
    case HID_SUBEVENT_CONNECTION_CLOSED:
        printf("BTH3 HID_CLOSED\n");
        if (phase != 7) finish("hid_closed");
        break;
    default:
        break;
    }
}

static void packet_handler(uint8_t packet_type, uint16_t channel, uint8_t *packet, uint16_t size) {
    (void)channel;
    if (packet_type != HCI_EVENT_PACKET || size < 2 || (unsigned)packet[1]+2 > size) return;
    switch (hci_event_packet_get_type(packet)) {
    case BTSTACK_EVENT_STATE:
        if (btstack_event_state_get_state(packet) != HCI_STATE_WORKING) break;
        if (phase != 1) break;
        printf("BTH3 LOCAL_CAPABILITY sc_active=%u configured_ssp=1 sc_default=1 auto_accept=0\n",gap_secure_connections_active());
        printf("BTH3 PHASE INQUIRY\n");
        inquiry_tries++;
        gap_inquiry_start(INQUIRY_SECONDS);
        break;
    case GAP_EVENT_INQUIRY_RESULT: {
        if (size < 27 || packet[26] > size-27u) break;
        bd_addr_t addr;
        gap_event_inquiry_result_get_bd_addr(packet, addr);
        if (!target_configured || memcmp(addr, allowed_addr, 6)) break;
        uint32_t cod = gap_event_inquiry_result_get_class_of_device(packet);
        int rssi = gap_event_inquiry_result_get_rssi_available(packet) ? gap_event_inquiry_result_get_rssi(packet) : 0;
        unsigned major = (cod >> 8) & 0x1Fu;
        unsigned minor = (cod >> 2) & 0x3Fu;
        char name[64];
        name[0] = 0;
        if (gap_event_inquiry_result_get_name_available(packet)) {
            unsigned n = gap_event_inquiry_result_get_name_len(packet);
            if (n > sizeof(name) - 1u) n = sizeof(name) - 1u;
            memcpy(name, gap_event_inquiry_result_get_name(packet), n);
            name[n] = 0;
        }
        printf("BTH3 INQ addr=%02x%02x%02x%02x%02x%02x cod=0x%06x major=%u minor=%u rssi=%d name=%s\n",
               addr[5], addr[4], addr[3], addr[2], addr[1], addr[0], (unsigned)cod, major, minor, rssi,
               name[0] ? name : "-");
        /* Major class 0x05 = peripheral; minor 1..4 = joystick / gamepad. */
        bool looks_like_pad = (major == 0x05u) && (minor >= 1u) && (minor <= 4u);
        if (!looks_like_pad) break;
        if (!have_target || rssi > target_rssi) {
            memcpy(target_addr, addr, 6);
            have_target = true;
            target_rssi = rssi;
            target_cod = cod;
            snprintf(target_name, sizeof(target_name), "%s", name[0] ? name : "-");
            printf("BTH3 TARGET addr=%02x%02x%02x%02x%02x%02x cod=0x%06x rssi=%d\n",
                   addr[5], addr[4], addr[3], addr[2], addr[1], addr[0], (unsigned)cod, rssi);
        }
        break;
    }
    case HCI_EVENT_CONNECTION_COMPLETE: {
        if (size < 13) break;
        bd_addr_t addr;
        hci_event_connection_complete_get_bd_addr(packet, addr);
        printf("BTH3 HCI_CONNECTED status=0x%02x addr=%02x%02x%02x%02x%02x%02x link=%u\n",
               hci_event_connection_complete_get_status(packet),
               addr[5], addr[4], addr[3], addr[2], addr[1], addr[0],
               (unsigned)hci_event_connection_complete_get_link_type(packet));
        if (hci_event_connection_complete_get_status(packet) == ERROR_CODE_SUCCESS &&
            hci_event_connection_complete_get_link_type(packet) == 1u) {
            if (!target_configured || memcmp(addr, allowed_addr, 6)) { finish("unexpected_peer"); break; }
            /* Let BTstack wait for command credits and remote features. */
            hci_con_handle_t handle = hci_event_connection_complete_get_connection_handle(packet);
            printf("BTH3 SECURITY_REQUEST handle=%u level=2 scheduler=btstack\n", (unsigned)handle);
            gap_request_security_level(handle, LEVEL_2);
        }
        break;
    }
    case HCI_EVENT_DISCONNECTION_COMPLETE:
        printf("BTH3 HCI_DISCONNECTED reason=0x%02x\n",
               hci_event_disconnection_complete_get_reason(packet));
        break;
    case HCI_EVENT_COMMAND_STATUS:
        if (size >= 6) printf("BTH3 COMMAND_STATUS opcode=0x%04x status=0x%02x\n",
            hci_event_command_status_get_command_opcode(packet), hci_event_command_status_get_status(packet));
        break;
    case HCI_EVENT_AUTHENTICATION_COMPLETE:
        if (size < 5) break;
        printf("BTH3 AUTH status=0x%02x\n",
               hci_event_authentication_complete_get_status(packet));
        break;
    case GAP_EVENT_SECURITY_LEVEL:
        if (size < 6) break;
        printf("BTH3 SECURITY_RESULT handle=%u level=%u status=0x%02x\n",
               (unsigned)gap_event_security_level_get_handle(packet),
               gap_event_security_level_get_security_level(packet),
               gap_event_security_level_get_status(packet));
        break;
    case HCI_EVENT_IO_CAPABILITY_REQUEST:
        printf("BTH3 IO_CAP_REQUEST local_io=3 oob=0 authreq=4 bondable=1 auto_accept=0 level=2\n");
        break;
    case HCI_EVENT_IO_CAPABILITY_RESPONSE:
        if (size < 11) { finish("short_io_response"); break; }
        printf("BTH3 IO_CAP_RESPONSE remote_io=%u remote_oob=%u remote_authreq=%u\n",
               hci_event_io_capability_response_get_io_capability(packet),
               hci_event_io_capability_response_get_oob_data_present(packet),
               hci_event_io_capability_response_get_authentication_requirements(packet));
        break;
    case HCI_EVENT_USER_CONFIRMATION_REQUEST:
        printf("BTH3 USER_CONFIRM action=none policy=unchanged\n");
        break;
    case HCI_EVENT_PIN_CODE_REQUEST:
        printf("BTH3 PIN_CODE_REQUEST\n");
        break;
    case HCI_EVENT_LINK_KEY_REQUEST:
        printf("BTH3 LINK_KEY_REQUEST\n");
        break;
    case GAP_EVENT_INQUIRY_COMPLETE:
        if (phase != 1) break;
        if (have_target) {
            gap_inquiry_stop();
            uint8_t status = hid_host_connect(target_addr, HID_PROTOCOL_MODE_REPORT, &hid_cid);
            printf("BTH3 CONNECT addr=%02x%02x%02x%02x%02x%02x status=0x%02x cod=0x%06x name=%s\n",
                   target_addr[5], target_addr[4], target_addr[3], target_addr[2], target_addr[1],
                   target_addr[0], status, (unsigned)target_cod, target_name);
            if (status != ERROR_CODE_SUCCESS) { finish("connect_start_failed"); break; }
            phase = 2; phase_us = time_us_64();
        } else if (inquiry_tries < MAX_INQUIRY_TRIES) {
            printf("BTH3 INQUIRY retry=%u\n", inquiry_tries + 1u);
            gap_inquiry_start(INQUIRY_SECONDS);
            inquiry_tries++;
        } else {
            finish("no_pad_found");
        }
        break;
    default:
        break;
    }
}

int main(void) {
    boot_us = time_us_64();
    stdio_init_all();
    char command[32];
    unsigned used = 0;
    bool banner = false;
    while (phase != 7) {
        if (stdio_usb_connected() && !banner) {
            printf("BTH3 READY v=7 mode=classic_hid pair=general_bonding_ram storage=ram output=disabled target=required command=SCAN\n");
            banner = true;
        }
        int ch = getchar_timeout_us(0);
        if (ch >= 0) {
            if (ch == '\r' || ch == '\n') {
                command[used] = 0;
                if (!strcmp(command, "CANCEL")) finish("cancelled");
                if (!strncmp(command, "TARGET ", 7) && strlen(command) == 19 && phase == 0) {
                    unsigned a[6];
                    if (sscanf(command+7, "%2x%2x%2x%2x%2x%2x", &a[0], &a[1], &a[2], &a[3], &a[4], &a[5]) == 6) {
                        for (unsigned i=0;i<6;i++) allowed_addr[i]=(uint8_t)a[i];
                        target_configured=true;
                        printf("BTH3 TARGET_LOCKED\n");
                    }
                }
                if (!strcmp(command, "SCAN") && phase == 0 && target_configured) {
                    phase = 1; phase_us = time_us_64();
                    if (cyw43_arch_init()) { finish("radio_init_failed"); break; }
                    radio_initialized = true;
                    security_trace_init();
                    l2cap_init();
                    sdp_init();
                    hid_host_init(hid_descriptor_storage, sizeof(hid_descriptor_storage));
                    hid_host_register_packet_handler(&hid_handler);
                    /* Baseline (restored): Just Works with general bonding. The
                     * DisplayYesNo/MITM variant crashed right after SCAN. */
                    gap_ssp_set_io_capability(SSP_IO_CAPABILITY_NO_INPUT_NO_OUTPUT);
                    gap_ssp_set_authentication_requirement(SSP_IO_AUTHREQ_MITM_PROTECTION_NOT_REQUIRED_GENERAL_BONDING);
                    gap_set_bondable_mode(1);
                    hci_reg.callback = &packet_handler;
                    hci_add_event_handler(&hci_reg);
                    hci_power_control(HCI_POWER_ON);
                }
                used = 0;
            } else if (used < sizeof(command) - 1u) {
                command[used++] = (char)ch;
            } else {
                used = 0;
            }
        }
        if (radio_initialized && phase != 7) cyw43_arch_poll();
        uint64_t now = time_us_64();
        if ((phase == 2 || phase == 3) && now - phase_us > CONNECT_LIMIT_US) finish("connect_timeout");
        if (now - boot_us > BOOT_LIMIT_US) finish("boot_limit");
        if (probe_ram_bank_errors()) finish("ram_bank_error");
        sleep_ms(1);
    }
    if (radio_initialized) {
    if (hid_cid) hid_host_disconnect(hid_cid);
    uint64_t until = time_us_64() + 300000ull;
    while (time_us_64() < until) cyw43_arch_poll();
    hci_power_control(HCI_POWER_OFF);
    cyw43_arch_deinit();
    }
    sleep_ms(200);
    reset_usb_boot(0, 0);
    return 0;
}
