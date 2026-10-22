# Read-only. Pico must already be in BOOTSEL, ideally held during reconnect.
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$tool=Join-Path $PSScriptRoot 'picotool-2.3.1\picotool\picotool.exe'
$selection=@('--ser','PICO_SERIAL_REDACTED')
$info=(& $tool info -a @selection | Out-String)
if($LASTEXITCODE -ne 0 -or $info -notmatch 'chipid:\s+0xPICO_SERIAL_REDACTED' -or $info -notmatch 'boot type:\s+bootsel'){throw 'Known Pico not in BOOTSEL'}
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$binary=Join-Path $root ('outputs\pico-persistent-capture-'+$stamp+'.bin')
$decoded=[IO.Path]::ChangeExtension($binary,'.json')
& $tool save -r 0x100F0000 0x100F2000 -v $binary -t bin @selection
if($LASTEXITCODE -ne 0){throw 'Capture readback failed'}
& 'C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe' (Join-Path $PSScriptRoot 'pico_capture_log.py') $binary --output $decoded
if($LASTEXITCODE -ne 0){throw 'No valid capture; raw bytes retained. Do not count as passed.'}
'Decoded capture: '+$decoded
