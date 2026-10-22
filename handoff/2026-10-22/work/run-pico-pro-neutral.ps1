# PC-only RAM test. Does not flash, erase, modify drivers, or touch Flydigi.
param([string]$PortName='COM11')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$busy=@(Get-Process -ErrorAction SilentlyContinue | Where-Object {$_.ProcessName -match '^(steam|BetterJoy|DS4Windows|DSX|reWASD)$'})
if($busy.Count){throw 'Close controller clients normally before testing; no application will be killed automatically.'}
$image=Join-Path $root 'outputs\pico-pro-neutral\pico_pro_neutral.uf2'
if((Get-FileHash -LiteralPath $image -Algorithm SHA256).Hash -ne '00D35AD59221C734F366233A99078449699ACD24CBC54D0227603D79AD34E561'){throw 'Candidate hash mismatch'}
$python='C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe'
& $python (Join-Path $PSScriptRoot 'verify-ram-uf2.py') $image
if($LASTEXITCODE -ne 0){throw 'UF2 SRAM check failed'}
$tool=Join-Path $PSScriptRoot 'picotool-2.3.1\picotool\picotool.exe'
$usb=@(Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -match '^USB\\VID_2E8A&PID_000F\\'})
if($usb.Count -eq 0){& (Join-Path $PSScriptRoot 'enter-pico-bootsel.ps1') -PortName $PortName}
$ready=$false
for($attempt=0;$attempt -lt 24;$attempt++){
    $info=(& $tool info -a 2>&1 | Out-String)
    if($LASTEXITCODE -eq 0){$ready=$true;break}
    Start-Sleep -Milliseconds 350
}
if(-not $ready -or $info -notmatch 'chipid:\s+0xPICO_SERIAL_REDACTED' -or $info -notmatch 'boot type:\s+bootsel'){
    throw 'Known physical Pico identity in BOOTSEL was not confirmed; no load attempted'
}
& $tool load -v -x $image
if($LASTEXITCODE -ne 0){throw 'RAM load failed'}
& $python (Join-Path $PSScriptRoot 'test-pico-pro-neutral.py')
if($LASTEXITCODE -ne 0){throw 'Protocol test incomplete; inspect report. RESETLAB or power cycle restores MicroPython.'}
Start-Sleep -Milliseconds 1300
& (Join-Path $PSScriptRoot 'test-pico-repl.ps1') -PortName $PortName
