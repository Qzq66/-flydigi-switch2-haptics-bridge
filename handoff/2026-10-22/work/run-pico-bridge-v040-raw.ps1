param([switch]$LiveBench)
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'enter-pico-bootsel.ps1') -PortName COM11
$tool=Join-Path $PSScriptRoot 'picotool-2.3.1\picotool\picotool.exe'
$ready=$false
for($n=0;$n -lt 35;$n++){$null=& $tool info --ser PICO_SERIAL_REDACTED 2>&1;if($LASTEXITCODE -eq 0){$ready=$true;break};Start-Sleep -Milliseconds 350}
if(-not $ready){throw 'BOOTSEL timeout'}
$image=Join-Path (Split-Path $PSScriptRoot -Parent) 'outputs\pico-haptics-bridge-v040\ram\pico_pro_capture.uf2'
& $tool load -v -x $image --ser PICO_SERIAL_REDACTED | Out-Null
if($LASTEXITCODE -ne 0){throw 'RAM load failed'}
$test=if($LiveBench){'flydigi-live-bridge-bench.py'}else{'test-pico-bridge-v040.py'}
& 'C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe' (Join-Path $PSScriptRoot $test)
if($LASTEXITCODE -ne 0){throw 'USB WiFi integration failed'}
