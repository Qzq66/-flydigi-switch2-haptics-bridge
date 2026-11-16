# Bluetooth discovery probe (offline prepared, not hardware-tested)

Purpose: establish discovery evidence for the standalone Flydigi receiver path.
This is not a controller bridge and cannot provide input or vibration.

## Scope and safety

- RP2350 / `pico2_w`, SDK 2.3.1, SDK-pinned isolated BTstack. No overclock.
- RAM-only ELF; no UF2, flash-loader target, Wi-Fi credentials or resident firmware changes.
- USB CDC only, no USB HID mouse/keyboard/controller interfaces.
- Waits for a literal `SCAN` serial line. No automatic scan on startup.
- Classic inquiry lasts approximately 10.24 seconds (14-second timeout); it transmits discovery traffic.
- Then BLE passive scanning for 12 seconds; no scan requests. Maximum 32 observations per transport.
- No outgoing connection, pairing, SDP/GATT enumeration, HID output or motor command.
- Bluetooth TLV storage factory is linker-wrapped to an 8 KiB RAM bank, avoiding SDK default Flash persistence.
- `CANCEL`, completion or the 90-second boot limit shuts down radio and returns to BOOTSEL.
- A power cycle can still start the pre-existing resident firmware. This probe does not change that firmware.

Final ELF call-site review found the RAM factory wrapper call and **zero calls** to
`flash_range_erase`, `flash_range_program`, `gap_connect` or `sm_request_pairing`.
Those names still appear as definitions in `nm` because linked SDK/BTstack objects keep
them; the safety claim is about call sites, not symbol absence. This is a source/link
review, not physical proof of unchanged Flash. A hardware run must still compare the
complete Flash before/after and perform the existing physical verify.

## Rebuild on this Windows workstation

The dependency manifest is [BTSTACK_SOURCE.json](../deps/BTSTACK_SOURCE.json).
The dependency sources and build directory are local, Git-ignored; they are not bundled into the repository.
Supply a local CMake executable as `$probeCmake`, then run from the repository root:

```powershell
& $probeCmake -S standalone/bt_discovery -B standalone/bt_discovery/build-ram -G Ninja `
  '-DPICO_SDK_PATH=C:/Users/quziqi/Documents/Codex/pico-work-20261022/pico-tools/pico-sdk' `
  '-DPICO_TOOLCHAIN_PATH=C:/Users/quziqi/Documents/Codex/pico-work-20261022/pico-tools' `
  '-DCMAKE_MAKE_PROGRAM=C:/Users/quziqi/Documents/Codex/pico-work-20261022/pico-tools/ninja/ninja.exe' `
  '-Dpioasm_DIR=C:/Users/quziqi/Documents/Codex/pico-work-20261022/pico-tools/sdk-tools-2.3.1/pioasm'
& $probeCmake --build standalone/bt_discovery/build-ram --target flydigi_bt_discovery --parallel 2
```

The prebuilt pioasm is required on this machine: compiling pioasm from source failed
because no native host C++ compiler was available. An initial USB config assertion
was corrected by declaring RHPORT0 device/full-speed mode. Failed build logs remain
in `build-ram/build-console.txt` and `build-fixed.txt`; successful output is in `build-fixed2.txt`.

## Offline log analysis

```text
python -B -m unittest discover -s tools -p test_bt_discovery.py -v
python -B tools/analyse_bt_discovery.py PRIVATE_CAPTURE --report NEW_REPORT.json
```

The raw serial capture contains nearby device names and addresses: keep it in `private/`.
The report uses transport/address-scoped peer IDs and removes names/addresses.
UUID 0x1812 is only a BLE HID advertisement hint; Classic peripheral class is only
a class hint. Names, absence of advertisements and hints cannot prove identity,
complete services, input support or fine-haptic output. Address randomization can
also prevent counting physical devices. Target identification may need private local review.

## Next现场 step (not executed)

User chose to save offline progress. No device enumeration, load, flash, scan or output
was performed. When resumed: confirm Pico BOOTSEL and actual full Flash baseline,
then arrange the controller's documented Bluetooth discovery mode without reset or
firmware update. RAM-load this reviewed ELF, capture one manually started scan,
return to BOOTSEL, verify unchanged Flash, and analyse locally. Do not connect to
Switch for this discovery test. Full SDP/GATT and report descriptors are a later,
separately scoped read-only connection step after identifying the target device.
