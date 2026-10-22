# Requires explicit approval for this Pico's persistent Flash write.
param([switch]$ConfirmPicoFlashWrite)
$ErrorActionPreference='Stop'
if(-not $ConfirmPicoFlashWrite){throw 'Explicit approval required: -ConfirmPicoFlashWrite. No device was opened.'}
$root=Split-Path -Parent $PSScriptRoot
$backup=Get-Content -LiteralPath (Join-Path $root 'outputs\pico-pre-capture-backup.json') -Raw | ConvertFrom-Json
$image=Join-Path $root 'outputs\pico-pro-capture-v031\flash\pico_pro_capture.bin'
$expected='5D1BE32BCA07DFFFD65D03FA31B657B604C3D56DC397A85B25CC6BE44F7E8C95'
if((Get-FileHash -LiteralPath $image -Algorithm SHA256).Hash -ne $expected){throw 'Reviewed Flash candidate changed'}
if((Get-Item -LiteralPath $image).Length -ne 22872){throw 'Candidate bounds changed'}
if(-not $backup.picotool_readback_verified -or -not $backup.proposed_log_region_erased -or $backup.bytes -ne 4194304){throw 'Backup proof incomplete'}
if((Get-FileHash -LiteralPath $backup.path -Algorithm SHA256).Hash -ne $backup.sha256){throw 'Backup hash mismatch'}
if(Get-Process steam -ErrorAction SilentlyContinue){throw 'Exit Steam normally before the PC capture test'}
$tool=Join-Path $PSScriptRoot 'picotool-2.3.1\picotool\picotool.exe'
$selection=@('--ser','PICO_SERIAL_REDACTED')
$info=(& $tool info -a @selection | Out-String)
if($LASTEXITCODE -ne 0 -or $info -notmatch 'chipid:\s+0xPICO_SERIAL_REDACTED' -or $info -notmatch 'boot type:\s+bootsel'){throw 'Known Pico not in BOOTSEL'}
# Refuse if the current entire Flash differs from the approved backup.
& $tool verify $backup.path -t bin -o 0x10000000 @selection
if($LASTEXITCODE -ne 0){throw 'Current Flash changed since backup; write refused'}
& $tool load -v $image -t bin -o 0x10000000 @selection
if($LASTEXITCODE -ne 0){throw 'Flash install/verification failed; stay in BOOTSEL and restore backup'}
$result=[ordered]@{installed_at=(Get-Date).ToString('o');candidate_sha256=$expected;backup_sha256=$backup.sha256;program_erase_bytes=24576;log_offsets=@('0xf0000','0xf1000');executed=$false;switch2_connected=$false}
$result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'outputs\pico-capture-v031-install.json') -Encoding utf8
'Installed and verified. Device remains in BOOTSEL; no automatic test or Switch connection.'
