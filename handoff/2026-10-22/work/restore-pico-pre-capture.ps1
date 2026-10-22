param([switch]$ConfirmRestorePicoFlash)
$ErrorActionPreference='Stop'
if(-not $ConfirmRestorePicoFlash){throw 'Explicit approval required: restores entire 4MiB Flash snapshot, including its filesystem.'}
$root=Split-Path -Parent $PSScriptRoot
$backup=Get-Content -LiteralPath (Join-Path $root 'outputs\pico-pre-capture-backup.json') -Raw | ConvertFrom-Json
if($backup.bytes -ne 4194304 -or -not $backup.picotool_readback_verified){throw 'Invalid full backup manifest'}
if((Get-FileHash -LiteralPath $backup.path -Algorithm SHA256).Hash -ne $backup.sha256){throw 'Backup integrity failed'}
$tool=Join-Path $PSScriptRoot 'picotool-2.3.1\picotool\picotool.exe'
$selection=@('--ser','PICO_SERIAL_REDACTED')
$info=(& $tool info -a @selection | Out-String)
if($LASTEXITCODE -ne 0 -or $info -notmatch 'chipid:\s+0xPICO_SERIAL_REDACTED' -or $info -notmatch 'boot type:\s+bootsel'){throw 'Known Pico not in BOOTSEL'}
& $tool load -v $backup.path -t bin -o 0x10000000 @selection
if($LASTEXITCODE -ne 0){throw 'Restore incomplete; retain BOOTSEL and backup'}
& $tool reboot @selection
if($LASTEXITCODE -ne 0){throw 'Flash restored but reboot not confirmed'}
$deadline=[DateTime]::UtcNow.AddSeconds(20)
while('COM11' -notin [IO.Ports.SerialPort]::GetPortNames()){
    if([DateTime]::UtcNow -ge $deadline){throw 'Full Flash restored and verified, but COM11 has not reappeared yet'}
    Start-Sleep -Milliseconds 250
}
Start-Sleep -Milliseconds 500
& (Join-Path $PSScriptRoot 'test-pico-repl.ps1') -PortName COM11
[ordered]@{restored_at=(Get-Date).ToString('o');sha256=$backup.sha256;full_flash_verified=$true} | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $root 'outputs\pico-capture-restored.json')
