# Generic Switch-mode RAM input observer

Offline-built; not hardware-tested. Independent of the XInput probes and resident
Switch USB bridge. The PC-facing USB interface is CDC only, not a gamepad.

Scope: classic BR/EDR HID, principally third-party first-generation Switch Pro
compatible modes. This is not a universal Switch 2 BLE/HD Rumble 2 implementation.
No brand or VID/PID filter implies universal compatibility.

## Commands and phases

1. RAM load, then wait for `SWP1 READY v=1`.
2. Send `RADIO`; wait for `SWP1 RADIO_READY`.
3. For the first field trial send **only `DISCOVER`**. One approximately 10.24-second
   inquiry emits at most 32 observations, then returns to BOOTSEL. No connection,
   pairing or output reports are initiated in this phase. Raw names/addresses stay private.
4. A later, separately prepared connection trial must identify the actual Switch-mode
   target. Do not reuse the XInput-mode address without evidence. `TARGET <12 hex>`
   uses canonical byte order, exactly as `SWP1 DEVICE addr=` prints it.
5. After target lock, `CONNECT` opens standard HID control PSM 0x11 and interrupt
   PSM 0x13 directly. The explicit choice avoids making SDP success mandatory for
   known compatible third-party modes. There is no automatic target selection.
6. Wait for `INPUT_READY`; `CAPTURE` starts a 15-second observation window, at most
   80 samples, separated by at least 200 ms. Total input-report count is also recorded.
   An allocated CID is not considered open until the channel-open success event.
7. `CANCEL`, error or the 90-second boot limit returns to BOOTSEL. Connection setup
   has a 25-second limit; discovery has a 14-second limit. No automatic retry.

## Safety and limits

- RAM ELF only, no UF2; SDK Bluetooth storage is wrapped to the existing RAM bank.
- Before any load, verify actual BOOTSEL identity and complete Flash snapshot.
  After the run, reread and physically verify unchanged Flash. The first prepared
  field runner is `work/switch_discovery_probe.ps1` and performs those checks.
- No HID Output/Feature reports, report-mode command, motor enable, LED, IMU or
  flash configuration commands. Bluetooth/L2CAP control traffic still occurs.
- Explicit connection mode retains the reviewed General Bonding, LEVEL_2 policy;
  local keys in RAM, no automatic confirmation. The peripheral may retain a bond.
  Discovery does not connect. Incoming/reverse HID connections are not accepted.
- The probe has no transport send import in its application object. Firmware
  call audit found no Flash erase/program or HID report-send call sites. ELF load
  segments fit RP2350 SRAM. These checks do not replace runtime/physical verification.
- Some controllers need a report-mode initialization command to emit input. Channel
  success without reports must be reported as such, not as unsupported hardware.
- Captured A1 HID data is observed, not yet decoded into verified A/B/stick mappings.
  Timing/button changes must be assessed from actual data. There is no game forwarding
  or haptic capability claim.

## Build

Use the same SDK/toolchain/pinned BTstack as `../bt_hid_classic`, with a separate
`build-ram` directory and target `switch_input_probe`. No upstream Bluepad32 code
was copied into this firmware. Standard PSMs/command roles were reviewed against
the pinned source documented in `docs/SWITCH_HOST_REFERENCE_2026-11-16.md`.

Offline size: text 353380 + BSS 20396 = 373776 bytes. Reproducibility hashes,
RAM segments and call checks are in
`docs/campaigns/realtime-2026-11-15/switch-input-probe-offline-20261116.json`.
No hardware or runtime functional test has been performed.
