# Read-only inventory. Does not start/stop capture, change filters or network settings.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidatePattern('^\d{8}-\d{6}$')][string]$RunId)
$ErrorActionPreference='Stop'
$repoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$privateRoot=Join-Path $repoRoot 'handoff/2026-10-22/work/private'
$publicPath=Join-Path $repoRoot ('docs/PKTMON_INVENTORY_'+$RunId+'.json')
$rawRoot=Join-Path $privateRoot ('pktmon-inventory-'+$RunId)
if((Test-Path -LiteralPath $rawRoot) -or (Test-Path -LiteralPath $publicPath)){throw 'Use a fresh RunId; evidence is never overwritten'}
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
$principal=New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$report=[ordered]@{
    status='INCOMPLETE'; readonly=$true; administrator=$isAdmin; raw_bytes_preserved=$true
    capture_started=$false; capture_stopped=$false; filters_changed=$false; network_settings_changed=$false
    motor_commands=0; pico_access=$false
    script_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    queries=@()
}
function Invoke-ReadOnlyPktmon([string[]]$QueryArguments,[string]$FileName){
    $queryText=[string]::Join(' ',$QueryArguments)
    if($queryText -notin @('status','filter list','list --json')){throw 'Only read-only inventory queries are allowed'}
    $process=New-Object Diagnostics.Process
    $process.StartInfo.FileName=Join-Path $env:SystemRoot 'System32/PktMon.exe'
    $process.StartInfo.Arguments=$queryText
    $process.StartInfo.UseShellExecute=$false
    $process.StartInfo.CreateNoWindow=$true
    $process.StartInfo.RedirectStandardOutput=$true
    $process.StartInfo.RedirectStandardError=$true
    $stdoutBuffer=New-Object IO.MemoryStream
    $stderrBuffer=New-Object IO.MemoryStream
    $outputPath=Join-Path $rawRoot $FileName
    try{
        if(-not $process.Start()){throw 'Read-only query could not start'}
        $stdoutTask=$process.StandardOutput.BaseStream.CopyToAsync($stdoutBuffer)
        $stderrTask=$process.StandardError.BaseStream.CopyToAsync($stderrBuffer)
        if(-not $process.WaitForExit(15000)){
            # This is only our own read-only query process, never an existing capture.
            $process.Kill();$null=$process.WaitForExit(3000)
            throw 'Read-only PktMon query timed out'
        }
        $stdoutTask.GetAwaiter().GetResult();$stderrTask.GetAwaiter().GetResult()
        [IO.File]::WriteAllBytes($outputPath,$stdoutBuffer.ToArray())
        $stderrPath=$outputPath+'.stderr'
        [IO.File]::WriteAllBytes($stderrPath,$stderrBuffer.ToArray())
        return [ordered]@{query=$queryText;exit_code=$process.ExitCode;raw_file=$FileName;sha256=(Get-FileHash -LiteralPath $outputPath -Algorithm SHA256).Hash.ToLowerInvariant();stderr_file=($FileName+'.stderr');stderr_sha256=(Get-FileHash -LiteralPath $stderrPath -Algorithm SHA256).Hash.ToLowerInvariant();stdout_bytes=$stdoutBuffer.Length;stderr_bytes=$stderrBuffer.Length}
    }finally{$process.Dispose();$stdoutBuffer.Dispose();$stderrBuffer.Dispose()}
}
try{
    if(-not $isAdmin){throw 'Windows administrator token required to read PktMon driver state'}
    $null=New-Item -ItemType Directory -Path $rawRoot
    $report.queries+=Invoke-ReadOnlyPktmon @('status') 'status.txt'
    $report.queries+=Invoke-ReadOnlyPktmon @('filter','list') 'filters.txt'
    $report.queries+=Invoke-ReadOnlyPktmon @('list','--json') 'components.json'
    if(@($report.queries | Where-Object {$_.exit_code -ne 0}).Count -gt 0){throw 'An inventory query failed; no capture or filter change attempted'}
    $report.status='PKTMON_READONLY_INVENTORY_COLLECTED'
    $selection=[ordered]@{run_id=$RunId;raw_root=$rawRoot;public_report=$publicPath}
    [IO.File]::WriteAllText((Join-Path $privateRoot 'pktmon-inventory-selection.json'),($selection|ConvertTo-Json),(New-Object Text.UTF8Encoding($false)))
}catch{$report.error=$_.Exception.Message}
[IO.File]::WriteAllText($publicPath,($report|ConvertTo-Json -Depth 8),(New-Object Text.UTF8Encoding($false)))
Write-Output ($report|ConvertTo-Json -Depth 8)
if($report.status -ne 'PKTMON_READONLY_INVENTORY_COLLECTED'){exit 1}
