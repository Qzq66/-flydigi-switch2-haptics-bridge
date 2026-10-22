param([switch]$StartHotspot,[switch]$BridgeNetwork)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null=[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]
$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
$null=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime]
$profile=[Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if($null -eq $profile){throw 'No shareable Internet connection profile'}
$manager=[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
$configuration=$manager.GetCurrentAccessPointConfiguration()
'TETHERING_STATE '+$manager.TetheringOperationalState
'BAND '+$configuration.Band
'MAX_CLIENTS '+$manager.MaxClientCount
'CLIENTS '+$manager.ClientCount
'SUPPORTS_2_4 '+$configuration.IsBandSupported([Windows.Networking.NetworkOperators.TetheringWiFiBand]::TwoPointFourGigahertz)
if($StartHotspot -or $BridgeNetwork){
    if($manager.ClientCount -ne 0){throw 'Existing hotspot clients; do not interrupt them'}
    $root=Split-Path -Parent $PSScriptRoot
    $private=Join-Path $PSScriptRoot 'private'
    New-Item -ItemType Directory -Force -Path $private | Out-Null
    '*' | Set-Content -LiteralPath (Join-Path $private '.gitignore') -Encoding ascii
    $record=[pscustomobject]@{ssid=$configuration.Ssid;passphrase=(ConvertTo-SecureString $configuration.Passphrase -AsPlainText -Force);band=[string]$configuration.Band;was_on=([string]$manager.TetheringOperationalState -eq 'On')}
    $secret=Join-Path $private 'pico-hotspot-credentials.xml'
    if(-not(Test-Path $secret)){$record | Export-Clixml -LiteralPath $secret}else{$record=Import-Clixml -LiteralPath $secret}
    $null=[Windows.Foundation.IAsyncAction,Windows.Foundation,ContentType=WindowsRuntime]
    function Wait-Action($operation){
        $method=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and -not $_.IsGenericMethod -and $_.GetParameters().Count -eq 1} | Select-Object -First 1
        $task=$method.Invoke($null,@($operation))
        if(-not $task.Wait(10000)){throw 'Hotspot action timeout'}
        $task.GetAwaiter().GetResult()
    }
    function Wait-Result($operation){
        $method=[System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {$_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and $_.GetParameters().Count -eq 1} | Select-Object -First 1
        $task=$method.MakeGenericMethod([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult]).Invoke($null,@($operation))
        if(-not $task.Wait(10000)){throw 'Hotspot operation timeout'}
        $task.GetAwaiter().GetResult()
    }
    $newNetwork=$false
    if($BridgeNetwork){
        $bridgeFile=Join-Path $private 'bridge-network.xml'
        if(Test-Path $bridgeFile){$bridge=Import-Clixml $bridgeFile}else{
            $random=New-Object byte[] 24
            [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($random)
            $hex=[BitConverter]::ToString($random).Replace('-','')
            $bridge=[pscustomobject]@{ssid=('PicoBridge-Test-'+$hex.Substring(0,4));passphrase=(ConvertTo-SecureString $hex.Substring(4,32) -AsPlainText -Force);session=$hex.Substring(32,16)}
            $bridge | Export-Clixml $bridgeFile
        }
        $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($bridge.passphrase)
        try{
            $key=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
            $newNetwork=($configuration.Ssid -ne $bridge.ssid -or $configuration.Passphrase -ne $key)
            $configuration.Ssid=$bridge.ssid;$configuration.Passphrase=$key
            $header="static const char bridge_ssid[]=`""+$bridge.ssid+"`";`nstatic const char bridge_key[]=`""+$key+"`";`n#define BRIDGE_SESSION UINT64_C(0x"+$bridge.session+")`n"
            [IO.File]::WriteAllText((Join-Path $private 'bridge_credentials.h'),$header,[Text.Encoding]::ASCII)
            [ordered]@{session=$bridge.session;private_task_network=$true;credentials_include_in_test_image=$true} | ConvertTo-Json | Set-Content (Join-Path $private 'bridge-session.json') -Encoding utf8
        }finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer);$key=$null;$header=$null}
    }
    if([string]$configuration.Band -ne 'TwoPointFourGigahertz' -or $newNetwork){
        if([string]$manager.TetheringOperationalState -eq 'On'){
            $stopped=Wait-Result ($manager.StopTetheringAsync())
            if([string]$stopped.Status -ne 'Success'){throw ('Hotspot stop failed: '+$stopped.Status)}
        }
        $configuration.Band=[Windows.Networking.NetworkOperators.TetheringWiFiBand]::TwoPointFourGigahertz
        Wait-Action ($manager.ConfigureAccessPointAsync($configuration))
    }
    if([string]$manager.TetheringOperationalState -ne 'On'){
        $started=Wait-Result ($manager.StartTetheringAsync())
        if([string]$started.Status -ne 'Success'){throw ('Hotspot start failed: '+$started.Status)}
    }
    [ordered]@{recorded_at=(Get-Date).ToString('o');state=[string]$manager.TetheringOperationalState;band=[string]$manager.GetCurrentAccessPointConfiguration().Band;credentials_storage='DPAPI encrypted for current Windows user';prior_band=$record.band;prior_state_on=$record.was_on;dedicated_test_network=[bool]$BridgeNetwork;changed_password=[bool]$BridgeNetwork;other_clients_at_start=0} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $root 'outputs\pico-hotspot-status.json') -Encoding utf8
    'HOTSPOT_READY '+$manager.GetCurrentAccessPointConfiguration().Band
}
