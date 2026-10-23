param([Parameter(Mandatory=$true)][string]$PicoSerial,[Parameter(Mandatory=$true)][string]$Picotool)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$private=Join-Path $root 'handoff\2026-10-22\work\private'
$old=Get-Content -LiteralPath (Join-Path $private 'rollback-selection.json') -Raw | ConvertFrom-Json
if((Get-FileHash -LiteralPath $old.original_flash -Algorithm SHA256).Hash -ne '09762691D3FDDF3BA592DB0BB6F520CB2384423F37194E7974089C9B0F700593'){throw 'Original MicroPython recovery backup integrity failed'}
& $Picotool verify $old.firmware -t bin -o 0x10000000 --ser $PicoSerial
if($LASTEXITCODE -ne 0){throw 'Expected v040 program not present'}
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$path=Join-Path $private ('v040-before-v042-'+$stamp+'.bin')
if(Test-Path -LiteralPath $path){throw 'Backup already exists'}
& $Picotool save -r 0x10000000 0x10400000 -v $path -t bin --ser $PicoSerial
if($LASTEXITCODE -ne 0 -or (Get-Item -LiteralPath $path).Length -ne 4194304){throw 'Full current Flash backup incomplete'}
$sha=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
[ordered]@{path=$path;sha256=$sha;bytes=4194304;picotool_readback_verified=$true;original_recovery_verified=$true} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $private 'v042-pre-flash-selection.json') -Encoding utf8
[ordered]@{status='FULL_CURRENT_FLASH_BACKED_UP';created_at=(Get-Date).ToString('o');bytes=4194304;sha256=$sha;picotool_readback_verified=$true;includes_current_v040_and_logs=$true;original_micropython_recovery_verified=$true;backup_location='ignored work/private';device_writes=0} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root ('docs\WINDOWS_V042_PRE_FLASH_BACKUP_'+$stamp+'.json')) -Encoding utf8
'Current full Flash backed up and readback verified. Original recovery backup also verified.'
