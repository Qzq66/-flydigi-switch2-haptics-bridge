$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'pktmon_capture_common.ps1')
$own="Packet filters:`r`n # Name Port`r`n 1 FDCLK-20000101-000000 49724`r`n"
if(-not (Test-PktmonOwnFilter $own 'FDCLK-20000101-000000')){throw 'Own single filter not recognised'}
if(Test-PktmonOwnFilter ($own+" 2 other 443`r`n") 'FDCLK-20000101-000000'){throw 'Must not remove other filters'}
if(Test-PktmonOwnFilter $own 'FDCLK-20000101'){throw 'Must not match name prefix'}
if(-not (Test-PktmonOwnCapture 'Log file: packets-20000101-000000.etl' 'packets-20000101-000000.etl')){throw 'Own log not recognised'}
if(Test-PktmonOwnCapture 'Log file: another.etl' 'packets-20000101-000000.etl'){throw 'Must not stop another capture'}
$rejected=$false
try{Quote-PktmonArgument "bad`nargument"}catch{$rejected=$true}
if(-not $rejected){throw 'Newline argument accepted'}
foreach($name in @('pktmon_capture_common.ps1','run_pktmon_smoke.ps1')){
    $parseTokens=$null;$parseErrors=$null
    $null=[System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $name),[ref]$parseTokens,[ref]$parseErrors)
    if($parseErrors.Count -gt 0){throw ('PowerShell syntax: '+$name)}
}
[ordered]@{status='PASSED_CAPTURE_GUARDS_AND_SYNTAX';checks=8;capture_started=$false;filters_changed=$false} | ConvertTo-Json
