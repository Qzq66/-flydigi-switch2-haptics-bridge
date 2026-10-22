# Restore only this task's saved hotspot configuration; never print credentials.
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]
$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
$null=[Windows.Foundation.IAsyncAction,Windows.Foundation,ContentType=WindowsRuntime]
function Wait-Action($operation){
    $method=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and $_.GetParameters().Count -eq 1} | Select-Object -First 1
    $task=$method.Invoke($null,@($operation));if(-not $task.Wait(10000)){throw 'Hotspot action timeout'};$task.GetAwaiter().GetResult()
}
function Wait-Result($operation){
    $method=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1} | Select-Object -First 1
    $task=$method.MakeGenericMethod([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult]).Invoke($null,@($operation))
    if(-not $task.Wait(10000)){throw 'Hotspot operation timeout'};return $task.GetAwaiter().GetResult()
}
$profile=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
$manager=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
if($manager.ClientCount -ne 0){throw 'Clients still connected; hotspot restoration refused'}
$private=Join-Path $PSScriptRoot 'private'
$original=Import-Clixml -LiteralPath (Join-Path $private 'pico-hotspot-credentials.xml')
$taskNetwork=Import-Clixml -LiteralPath (Join-Path $private 'bridge-network.xml')
$config=$manager.GetCurrentAccessPointConfiguration()
if($config.Ssid -ne $taskNetwork.ssid -and $config.Ssid -ne $original.ssid){throw 'Hotspot was independently changed; restoration refused'}
if([string]$manager.TetheringOperationalState -eq 'On'){
    $result=Wait-Result ($manager.StopTetheringAsync());if([string]$result.Status -ne 'Success'){throw 'Hotspot stop failed'}
}
$pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($original.passphrase)
try{
    $config.Ssid=$original.ssid;$config.Passphrase=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $config.Band=[Enum]::Parse([Windows.Networking.NetworkOperators.TetheringWiFiBand],$original.band)
    Wait-Action ($manager.ConfigureAccessPointAsync($config))
}finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}
if($original.was_on){$result=Wait-Result ($manager.StartTetheringAsync());if([string]$result.Status -ne 'Success'){throw 'Original hotspot restart failed'}}
$restored=$manager.GetCurrentAccessPointConfiguration()
$pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($original.passphrase)
try{$matchesOriginal=$restored.Ssid -eq $original.ssid -and $restored.Passphrase -eq [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) -and [string]$restored.Band -eq $original.band}
finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}
if(-not $matchesOriginal){throw 'Hotspot restoration comparison failed'}
[ordered]@{restored_at=(Get-Date).ToString('o');original_configuration_matches=$matchesOriginal;original_operational_state_matches=(([string]$manager.TetheringOperationalState -eq 'On') -eq $original.was_on);credentials_printed=$false} | ConvertTo-Json | Set-Content (Join-Path (Split-Path $PSScriptRoot -Parent) 'outputs\pico-hotspot-restored.json') -Encoding utf8
'Original hotspot configuration restored and compared; credentials not printed.'
