param([Parameter(Mandatory=$true)][string]$PicoSerial,[Parameter(Mandatory=$true)][string]$Picotool,[Parameter(Mandatory=$true)][string]$ExpectedSha256)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$private=Join-Path $root 'handoff\2026-10-22\work\private'
$backup=Get-Content -LiteralPath (Join-Path $private 'v042-pre-flash-selection.json') -Raw | ConvertFrom-Json
$image=Join-Path $root 'build\pico-v042-live-flash\pico_pro_capture.bin'
$manifest=Get-Content -LiteralPath ([IO.Path]::ChangeExtension($image,'.manifest.json')) -Raw | ConvertFrom-Json
$actual=(Get-FileHash -LiteralPath $image -Algorithm SHA256).Hash
if($actual -ne $ExpectedSha256 -or $actual -ne $manifest.sha256 -or $manifest.profile -ne 'flash'){throw 'Reviewed v042 image mismatch'}
if((Get-Item -LiteralPath $image).Length -ne $manifest.bytes -or $manifest.bytes -gt 0xe0000 -or [Convert]::ToInt32($manifest.program_erase_end,16) -gt 0xe0000 -or -not $manifest.program_excludes_logs_and_filesystem){throw 'Program overlaps reserved region'}
if($backup.bytes -ne 4194304 -or -not $backup.picotool_readback_verified -or -not $backup.original_recovery_verified -or (Get-FileHash -LiteralPath $backup.path -Algorithm SHA256).Hash -ne $backup.sha256){throw 'Complete recovery material not verified'}
if(Get-Process steam -ErrorAction SilentlyContinue){throw 'Exit Steam normally before using the experimental USB device'}
& $Picotool verify $backup.path -t bin -o 0x10000000 --ser $PicoSerial
if($LASTEXITCODE -ne 0){throw 'Current Flash differs from saved v040 snapshot; refused'}
& $Picotool load -v $image -t bin -o 0x10000000 --ser $PicoSerial
if($LASTEXITCODE -ne 0){throw 'v042 install readback failed; keep BOOTSEL and verified full backup'}
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
[ordered]@{status='V042_FLASH_INSTALLED_VERIFIED_NOT_STARTED';installed_at=(Get-Date).ToString('o');firmware_sha256=$actual;program_bytes=$manifest.bytes;program_erase_end=$manifest.program_erase_end;backup_sha256=$backup.sha256;full_current_backup_verified=$true;log_regions_preserved=$true;filesystem_preserved=$true;remains_in_bootsel=$true;flydigi_commands=0} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root ('docs\WINDOWS_V042_FLASH_INSTALLED_'+$stamp+'.json')) -Encoding utf8
'v042 Flash installed and readback verified. Remains in BOOTSEL; no test started.'
