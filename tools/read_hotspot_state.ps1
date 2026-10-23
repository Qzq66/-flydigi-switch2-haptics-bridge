$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]
$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
$profile=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if($null -eq $profile){throw 'No active network profile'}
$manager=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
$apple=@(Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.InterfaceDescription -eq 'Apple Mobile Device Ethernet'})
$sourceMatches=$apple.Count -eq 1 -and [guid]$profile.NetworkAdapter.NetworkAdapterId -eq [guid]$apple[0].InterfaceGuid
[ordered]@{hotspot_state=[string]$manager.TetheringOperationalState;clients=$manager.ClientCount;band=[string]$manager.GetCurrentAccessPointConfiguration().Band;iphone_usb_source=$sourceMatches} | ConvertTo-Json
