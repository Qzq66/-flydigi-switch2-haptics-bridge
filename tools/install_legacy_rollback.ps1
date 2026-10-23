param([Parameter(Mandatory=$true)][string]$PicoSerial,[Parameter(Mandatory=$true)][string]$Picotool)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$private=Join-Path $root 'handoff\2026-10-22\work\private'
$selection=Get-Content -LiteralPath (Join-Path $private 'rollback-selection.json') -Raw | ConvertFrom-Json
$expectedImage='0CEF76FE7ADE60477D5F375A83830AC5877C39B9E28ED677A9CD595049904F34'
$expectedBackup='09762691D3FDDF3BA592DB0BB6F520CB2384423F37194E7974089C9B0F700593'
if((Get-FileHash -LiteralPath $selection.firmware -Algorithm SHA256).Hash -ne $expectedImage -or (Get-Item -LiteralPath $selection.firmware).Length -ne 354708){throw 'Legacy candidate hash/bounds mismatch'}
if((Get-FileHash -LiteralPath $selection.original_flash -Algorithm SHA256).Hash -ne $expectedBackup -or (Get-Item -LiteralPath $selection.original_flash).Length -ne 4194304){throw 'Original Flash backup mismatch'}
if(Get-Process steam -ErrorAction SilentlyContinue){throw 'Steam is running; exit it normally first'}
$deviceSelection=@('--ser',$PicoSerial)
$info=(& $Picotool info -a @deviceSelection | Out-String)
if($LASTEXITCODE -ne 0 -or $info -notmatch ('chipid:\s+0x'+[regex]::Escape($PicoSerial.ToLower())) -or $info -notmatch 'boot type:\s+bootsel'){throw 'Expected Pico not in BOOTSEL'}
& $Picotool verify $selection.original_flash -t bin -o 0x10000000 @deviceSelection
if($LASTEXITCODE -ne 0){throw 'Current Flash differs from original backup; refusing overwrite'}
& $Picotool load -v $selection.firmware -t bin -o 0x10000000 @deviceSelection
if($LASTEXITCODE -ne 0){throw 'Legacy install verification failed; retain BOOTSEL and original backup'}
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
[ordered]@{status='LEGACY_V040_INSTALLED_VERIFIED_NOT_STARTED';installed_at=(Get-Date).ToString('o');firmware_sha256=$expectedImage;original_backup_sha256=$expectedBackup;current_original_flash_verified_before_write=$true;program_erase_bytes=356352;prompt_ms=120;prompt_offset=12;flydigi_commands=0;remains_in_bootsel=$true;hotspot_enabled=$false;switch2_tested=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root ('docs\WINDOWS_ROLLBACK_INSTALLED_'+$stamp+'.json')) -Encoding utf8
'Legacy firmware installed and readback verified. Remains in BOOTSEL; no output started.'
