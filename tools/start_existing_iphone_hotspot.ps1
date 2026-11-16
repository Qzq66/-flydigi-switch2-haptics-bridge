$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]
$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
$apple=@(Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.InterfaceDescription -eq 'Apple Mobile Device Ethernet'})
$profile=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if($apple.Count -ne 1 -or $null -eq $profile -or [guid]$profile.NetworkAdapter.NetworkAdapterId -ne [guid]$apple[0].InterfaceGuid){throw 'Current upstream must already be iPhone USB; no settings changed'}
$manager=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
if([string]$manager.GetCurrentAccessPointConfiguration().Band -ne 'TwoPointFourGigahertz'){throw 'Original hotspot must already use 2.4GHz; no settings changed'}
if([string]$manager.TetheringOperationalState -eq 'Off'){
    $operation=$manager.StartTetheringAsync()
    $method=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1} | Select-Object -First 1
    $task=$method.MakeGenericMethod([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult]).Invoke($null,@($operation))
    if(-not $task.Wait(15000)){throw 'Starting existing hotspot timed out'}
    if([string]$task.GetAwaiter().GetResult().Status -ne 'Success'){throw 'Starting existing hotspot failed'}
}
if([string]$manager.TetheringOperationalState -ne 'On'){throw 'Hotspot is not On'}
'Existing iPhone USB / 2.4GHz hotspot is On; SSID, password, band and upstream unchanged.'
