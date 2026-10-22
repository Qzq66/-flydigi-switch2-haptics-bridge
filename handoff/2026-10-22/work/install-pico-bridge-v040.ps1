param([switch]$ConfirmPicoFlashWrite)
$ErrorActionPreference='Stop'
if(-not $ConfirmPicoFlashWrite){throw 'Pico Flash write confirmation flag required'}
$root=Split-Path -Parent $PSScriptRoot
$backup=Get-Content -LiteralPath (Join-Path $root 'outputs\pico-pre-capture-backup.json') -Raw | ConvertFrom-Json
$image=Join-Path $root 'outputs\pico-haptics-bridge-v040\flash\pico_pro_capture.bin'
$expected='0CEF76FE7ADE60477D5F375A83830AC5877C39B9E28ED677A9CD595049904F34'
if((Get-FileHash -LiteralPath $image -Algorithm SHA256).Hash -ne $expected){throw 'Reviewed Flash candidate changed'}
if((Get-Item -LiteralPath $image).Length -ne 354708){throw 'Candidate bounds changed'}
if(-not $backup.picotool_readback_verified -or -not $backup.proposed_log_region_erased -or $backup.bytes -ne 4194304){throw 'Backup proof incomplete'}
if((Get-FileHash -LiteralPath $backup.path -Algorithm SHA256).Hash -ne $backup.sha256){throw 'Backup hash mismatch'}
$original=[IO.File]::ReadAllBytes($backup.path)
for($at=0xe0000;$at -lt 0x100000;$at++){if($original[$at] -ne 255){throw 'Reserved log area not erased in backup'}}
if(Get-Process steam -ErrorAction SilentlyContinue){throw 'Exit Steam normally before this experiment'}
$tool=Join-Path $PSScriptRoot 'picotool-2.3.1\picotool\picotool.exe'
$selection=@('--ser','PICO_SERIAL_REDACTED')
$info=(& $tool info -a @selection | Out-String)
if($LASTEXITCODE -ne 0 -or $info -notmatch 'chipid:\s+0xPICO_SERIAL_REDACTED' -or $info -notmatch 'boot type:\s+bootsel'){throw 'Known Pico not in BOOTSEL'}
& $tool verify $backup.path -t bin -o 0x10000000 @selection
if($LASTEXITCODE -ne 0){throw 'Current full Flash differs from original backup; refused'}
& $tool load -v $image -t bin -o 0x10000000 @selection
if($LASTEXITCODE -ne 0){throw 'Flash verification failed; restore original backup'}
[ordered]@{installed_at=(Get-Date).ToString('o');candidate_sha256=$expected;backup_sha256=$backup.sha256;program_erase_bytes=356352;log_offsets=@('0xe0000','0xf0000');executed=$false;switch2_connected=$false;contains_dedicated_test_network_key=$true;contains_original_network_key=$false} | ConvertTo-Json | Set-Content (Join-Path $root 'outputs\pico-bridge-v040-install.json') -Encoding utf8
'Installed and verified; remains in BOOTSEL. Keep image private: dedicated test hotspot key embedded.'
