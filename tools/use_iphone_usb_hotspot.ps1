$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$private=Join-Path $root 'handoff\2026-10-22\work\private'
$selection=Get-Content -LiteralPath (Join-Path $private 'rollback-selection.json') -Raw | ConvertFrom-Json
$apple=@(Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.InterfaceDescription -eq 'Apple Mobile Device Ethernet'})
if($apple.Count -ne 1){throw 'Expected one active iPhone USB Ethernet adapter'}
$expectedGuid=[guid]$apple[0].InterfaceGuid
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]
$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
function Wait-Result($operation){
    $method=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1} | Select-Object -First 1
    $task=$method.MakeGenericMethod([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult]).Invoke($null,@($operation))
    if(-not $task.Wait(10000)){throw 'Hotspot stop timeout'}
    return $task.GetAwaiter().GetResult()
}
$profile=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if($null -eq $profile){throw 'No current sharing profile; refusing source change'}
$manager=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
if($manager.ClientCount -ne 0){throw 'Hotspot has connected clients; refusing restart'}
if([string]$manager.TetheringOperationalState -eq 'On'){
    $stopped=Wait-Result ($manager.StopTetheringAsync())
    if([string]$stopped.Status -ne 'Success'){throw 'Hotspot stop failed'}
}
& netsh wlan disconnect interface=WLAN | Out-Null
if($LASTEXITCODE -ne 0){throw 'Could not disconnect upstream WLAN association'}
$until=[DateTime]::UtcNow.AddSeconds(10)
do {
    $profile=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
    if($null -ne $profile -and [guid]$profile.NetworkAdapter.NetworkAdapterId -eq $expectedGuid){break}
    Start-Sleep -Milliseconds 250
} while([DateTime]::UtcNow -lt $until)
if($null -eq $profile -or [guid]$profile.NetworkAdapter.NetworkAdapterId -ne $expectedGuid){throw 'Internet sharing profile is not iPhone USB; no test started'}
$entry=Join-Path $selection.root 'work\pico-hotspot.ps1'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $entry -BridgeNetwork
if($LASTEXITCODE -ne 0){throw 'Legacy hotspot could not start from iPhone USB'}
$manager=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
[ordered]@{status='IPHONE_USB_SOURCE_PC_HOTSPOT_READY';created_at=(Get-Date).ToString('o');internet_source='Apple Mobile Device Ethernet';source_verified_by_adapter_guid=$true;hotspot_state=[string]$manager.TetheringOperationalState;band=[string]$manager.GetCurrentAccessPointConfiguration().Band;clients=$manager.ClientCount;upstream_wlan_disconnected=$true;driver_settings_changed=$false;pico_flash_written=$false;motor_output_started=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root ('docs\WINDOWS_IPHONE_USB_HOTSPOT_'+$stamp+'.json')) -Encoding utf8
'iPhone USB sharing profile verified; old PC 2.4GHz hotspot ready. No motor output.'
