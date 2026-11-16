# Three diagnostic CLK4 unicast packets to the existing iPhone USB gateway only. Never opens a Pico or a controller.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidatePattern('^\d{8}-\d{6}$')][string]$RunId,[switch]$ValidateOnly)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'pktmon_capture_common_v3.ps1')
if($ValidateOnly){
    [ordered]@{mode='VALIDATE_ONLY';capture_started=$false;filters_changed=$false;maximum_packets=3;port=49724;pico_access=$false} | ConvertTo-Json
    exit 0
}
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$private=Join-Path $repo 'handoff/2026-10-22/work/private'
$RawRoot=Join-Path $private ('pktmon-smoke-v4-'+$RunId)
$public=Join-Path $repo ('docs/PKTMON_SMOKE_V4_'+$RunId+'.json')
if((Test-Path -LiteralPath $RawRoot) -or (Test-Path -LiteralPath $public)){throw 'Use fresh evidence paths'}
$null=New-Item -ItemType Directory -Path $RawRoot
$script:NativeIndex=0
$filter='FDCLK4-'+$RunId
$logName='packets-'+$RunId+'.etl';$etl=Join-Path $RawRoot $logName
$Report=[ordered]@{status='INCOMPLETE';capture_started=$false;capture_stopped=$false;filter_added=$false;filter_removed=$false;network_settings_changed=$false;motor_commands=0;pico_access=$false;commands=@();cleanup_errors=@();source_sha256=@{}}
foreach($name in @('run_pktmon_smoke_v4.ps1','pktmon_capture_common_v3.ps1','send_pktmon_smoke_v4.py','capture_clock.py')){
    $Report.source_sha256[$name]=(Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $name) -Algorithm SHA256).Hash.ToLowerInvariant()
}
$mutex=New-Object Threading.Mutex($false,'Global\FlydigiPktmonDiagnostic')
$locked=$false;$captureAttempted=$false;$senderOk=$false
try{
    $id=[Security.Principal.WindowsIdentity]::GetCurrent();$principal=New-Object Security.Principal.WindowsPrincipal($id)
    if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Windows administrator token required'}
    $locked=$mutex.WaitOne(0);if(-not $locked){throw 'Another owned diagnostic helper is active'}
    $adapters=@(Get-NetAdapter | Where-Object {$_.Status -eq 'Up' -and $_.InterfaceDescription -match 'Apple|iPhone'})
    if($adapters.Count -ne 1){throw 'Exactly one active iPhone USB adapter required; no settings changed'}
    $addresses=@(Get-NetIPAddress -InterfaceIndex $adapters[0].ifIndex -AddressFamily IPv4 | Where-Object {$_.IPAddress -notlike '169.254.*'})
    $routes=@(Get-NetRoute -InterfaceIndex $adapters[0].ifIndex -DestinationPrefix '0.0.0.0/0' | Where-Object {$_.NextHop -ne '0.0.0.0'})
    if($addresses.Count -ne 1 -or $routes.Count -ne 1){throw 'Unique existing USB address and gateway required'}
    $route=[ordered]@{source=$addresses[0].IPAddress;gateway=$routes[0].NextHop;interface_index=$adapters[0].ifIndex}
    [IO.File]::WriteAllText((Join-Path $RawRoot 'route.json'),($route|ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
    $state=Invoke-PktmonCaptureCommand @('status') 'before-status'
    $filters=Invoke-PktmonCaptureCommand @('filter','list') 'before-filters'
    if($state.Code -ne 0 -or -not (Test-PktmonIdle $state.Text)){throw 'Existing or unknown PktMon session; untouched'}
    if($filters.Code -ne 0 -or -not (Test-PktmonEmptyFilters $filters.Text)){throw 'Existing or unknown filters; untouched'}
    $add=Invoke-PktmonCaptureCommand @('filter','add',$filter,'-t','UDP','-p','49724') 'add-own-filter'
    if($add.Code -ne 0){throw 'Own filter creation failed'}
    $Report.filter_added=$true
    $own=Invoke-PktmonCaptureCommand @('filter','list') 'verify-own-filter'
    if($own.Code -ne 0 -or -not (Test-PktmonOwnFilter $own.Text $filter)){throw 'Cannot verify a sole owned filter; no capture started'}
    $captureAttempted=$true
    $start=Invoke-PktmonCaptureCommand @('start','--capture','--comp','all','--pkt-size','128','--file-size','16','--log-mode','circular','--file-name',$etl) 'start-own-capture'
    if($start.Code -ne 0){throw 'Capture start failed'}
    $Report.capture_started=$true
    $owned=Invoke-PktmonCaptureCommand @('status') 'verify-own-session'
    if($owned.Code -ne 0 -or -not (Test-PktmonOwnCapture $owned.Text $logName)){throw 'Cannot verify capture log ownership'}
    $session=Invoke-PktmonCaptureCommand @('query','PktMon','-ets') 'etw-session-before-send' 'logman.exe'
    $provider=Invoke-PktmonCaptureCommand @('query','providers','Microsoft-Windows-PktMon') 'etw-provider-before-send' 'logman.exe'
    if($session.Code -ne 0 -or $provider.Code -ne 0){throw 'Live ETW inspection unavailable; no diagnostic packets sent'}
    $beforeCounters=Invoke-PktmonCaptureCommand @('counters') 'counters-before-send'
    if($beforeCounters.Code -ne 0){throw 'Pre-send counters unavailable'}
    Start-Sleep -Milliseconds 250
    $python='C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe'
    $sender=New-Object Diagnostics.Process
    $sender.StartInfo.FileName=$python
    $sender.StartInfo.Arguments=('-B '+(Quote-PktmonArgument (Join-Path $PSScriptRoot 'send_pktmon_smoke_v4.py'))+' --run-id '+$RunId)
    $sender.StartInfo.UseShellExecute=$false;$sender.StartInfo.CreateNoWindow=$true
    try{
        if(-not $sender.Start()){throw 'Sender could not start'}
        if(-not $sender.WaitForExit(5000)){$sender.Kill();$null=$sender.WaitForExit(2000);throw 'Own three-packet sender timed out'}
        if($sender.ExitCode -ne 0){throw 'Three-packet sender failed'}
        $senderOk=$true
    }finally{$sender.Dispose()}
    Start-Sleep -Milliseconds 500
    $afterCounters=Invoke-PktmonCaptureCommand @('counters') 'counters-after-send'
    if($afterCounters.Code -ne 0){throw 'Post-send counters unavailable'}
    $sessionAfter=Invoke-PktmonCaptureCommand @('query','PktMon','-ets') 'etw-session-after-send' 'logman.exe'
    if($sessionAfter.Code -ne 0){throw 'Post-send ETW session inspection failed'}
}catch{$Report.error=$_.Exception.Message}
finally{
    if($locked){
        if($captureAttempted){
            try{
                $current=Invoke-PktmonCaptureCommand @('status') 'cleanup-status'
                if($current.Code -eq 0 -and (Test-PktmonOwnCapture $current.Text $logName)){
                    $Report.capture_started=$true
                    $stopped=Invoke-PktmonCaptureCommand @('stop') 'stop-owned'
                    $after=Invoke-PktmonCaptureCommand @('status') 'after-stop'
                    $Report.capture_stopped=($stopped.Code -eq 0 -and $after.Code -eq 0 -and (Test-PktmonIdle $after.Text))
                    if(-not $Report.capture_stopped){throw 'Owned capture stop not confirmed'}
                }elseif($current.Code -ne 0 -or -not (Test-PktmonIdle $current.Text)){throw 'Unknown capture owner; did not stop another session'}
            }catch{$Report.cleanup_errors+=$_.Exception.Message}
        }
        if($Report.filter_added){
            try{
                $state=Invoke-PktmonCaptureCommand @('status') 'filter-cleanup-status'
                $own=Invoke-PktmonCaptureCommand @('filter','list') 'filter-cleanup-list'
                if($state.Code -ne 0 -or -not (Test-PktmonIdle $state.Text) -or $own.Code -ne 0 -or -not (Test-PktmonOwnFilter $own.Text $filter)){throw 'Cannot prove idle and sole owned filter; filters preserved'}
                $removed=Invoke-PktmonCaptureCommand @('filter','remove') 'remove-sole-owned'
                $after=Invoke-PktmonCaptureCommand @('filter','list') 'after-filter-cleanup'
                $Report.filter_removed=($removed.Code -eq 0 -and $after.Code -eq 0 -and (Test-PktmonEmptyFilters $after.Text))
                if(-not $Report.filter_removed){throw 'Owned filter cleanup not confirmed'}
            }catch{$Report.cleanup_errors+=$_.Exception.Message}
        }
        $mutex.ReleaseMutex()
    }
    $mutex.Dispose()
}
if($Report.capture_stopped -and $Report.filter_removed -and $senderOk -and -not $Report.error -and $Report.cleanup_errors.Count -eq 0){
    try{
        $pcap=Invoke-PktmonCaptureCommand @('etl2pcap',$etl,'--out',(Join-Path $RawRoot 'packets.pcapng')) 'convert-flow'
        $drops=Invoke-PktmonCaptureCommand @('etl2pcap',$etl,'--drop-only','--out',(Join-Path $RawRoot 'drops.pcapng')) 'convert-drops'
        $stats=Invoke-PktmonCaptureCommand @('etl2txt',$etl,'--stats') 'etl-statistics'
        if($pcap.Code -ne 0 -or $drops.Code -ne 0 -or $stats.Code -ne 0){throw 'Capture conversion incomplete'}
        $Report.status='PKTMON_SMOKE_V4_ARTIFACTS_READY_NOT_YET_ANALYSED'
    }catch{$Report.error=$_.Exception.Message}
}
[IO.File]::WriteAllText($public,($Report|ConvertTo-Json -Depth 10),(New-Object Text.UTF8Encoding($false)))
[IO.File]::WriteAllText((Join-Path $private 'pktmon-smoke-v4-selection.json'),([ordered]@{run_id=$RunId;raw_root=$RawRoot;public_report=$public}|ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
Write-Output ($Report|ConvertTo-Json -Depth 10)
if($Report.status -ne 'PKTMON_SMOKE_V4_ARTIFACTS_READY_NOT_YET_ANALYSED'){exit 1}
