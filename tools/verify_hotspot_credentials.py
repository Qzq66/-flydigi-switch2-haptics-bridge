"""Read-only drift check: the hotspot must match the credentials compiled into the bridge.

The bridge joins one fixed SSID/passphrase baked into the firmware at build time.  If the
Windows hotspot is edited (or another checkout of this project creates its own network),
the bridge silently stops joining: the listener sees no UDP, the phase stays DISCOVERING and
the arm button never lights.  This check compares three things without printing any secret:

  * the private credential header used by the build tree
  * the saved bridge-network.xml used by pico-hotspot.ps1
  * the newest full-flash capture (the credentials really installed on the board)
  * the access point configuration Windows is currently broadcasting

Exit 0 only when all four agree.
"""
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PRIVATE = ROOT / 'handoff' / '2026-10-22' / 'work' / 'private'
HEADER = PRIVATE / 'bridge_credentials.h'
NETWORK = PRIVATE / 'bridge-network.xml'
READ_AP = r'''$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]
$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
$profile=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
$m=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
$ap=$m.GetCurrentAccessPointConfiguration()
[ordered]@{ssid=$ap.Ssid;passphrase=$ap.Passphrase;band=[string]$ap.Band;state=[string]$m.TetheringOperationalState;clients=$m.ClientCount}|ConvertTo-Json'''


def header_credentials():
    text = HEADER.read_text(encoding='utf-8', errors='replace')
    return (re.search(r'bridge_ssid\[\]\s*=\s*"([^"]*)"', text).group(1),
            re.search(r'bridge_key\[\]\s*=\s*"([^"]*)"', text).group(1))


def saved_network():
    # The XML stores the passphrase as an encrypted SecureString; let PowerShell decode it.
    script = (
        "$x=Import-Clixml -LiteralPath '%s';"
        "$p=[Runtime.InteropServices.Marshal]::PtrToStringBSTR("
        "[Runtime.InteropServices.Marshal]::SecureStringToBSTR($x.passphrase));"
        "[ordered]@{ssid=$x.ssid;passphrase=$p}|ConvertTo-Json" % str(NETWORK).replace("'", "''"))
    out = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', script],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def current_ap():
    out = subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', READ_AP],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def newest_capture():
    shots = sorted(PRIVATE.glob('v043-host-full-*.bin'))
    return shots[-1] if shots else None


def main():
    header = header_credentials()
    saved = saved_network()
    ap = current_ap()
    capture = newest_capture()
    firmware = capture.read_bytes() if capture else b''
    checks = {
        'header_matches_saved_network': (header[0], header[1]) == (saved['ssid'], saved['passphrase']),
        'hotspot_matches_saved_network': (ap['ssid'], ap['passphrase']) == (saved['ssid'], saved['passphrase']),
        'hotspot_is_on': ap['state'] == 'On',
        'band_is_2_4ghz': ap['band'] == 'TwoPointFourGigahertz',
        'capture_present': capture is not None,
        'credentials_present_in_capture': bool(firmware) and header[1].encode() in firmware,
    }
    report = dict(status='PASSED_HOTSPOT_MATCHES_FIRMWARE' if all(checks.values()) else 'INCOMPLETE',
                  checks=checks, capture=capture.name if capture else None,
                  clients=ap['clients'])
    out = ROOT / 'docs' / 'CAMPAIGN_HOTSPOT_DRIFT.json'
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    print(out)
    return 0 if report['status'].startswith('PASSED') else 1


if __name__ == '__main__':
    raise SystemExit(main())
