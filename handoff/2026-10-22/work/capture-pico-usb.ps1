param([Parameter(Mandatory=$true)][ValidatePattern('^[a-z0-9-]+$')][string]$Label)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$devices=@(Get-PnpDevice -PresentOnly)
$selected=@($devices | Where-Object { $_.Class -in @('USB','Keyboard','Mouse','Ports') -or $_.InstanceId -match '^USB\\VID_2E8A' })
$cache=@{}
function Properties([string]$id) {
    if(-not $cache.ContainsKey($id)){
        $props=@(Get-PnpDeviceProperty -InstanceId $id -ErrorAction SilentlyContinue)
        $cache[$id]=@{}
        foreach($p in $props){$cache[$id][$p.KeyName]=$p.Data}
    }
    return $cache[$id]
}
$rows=@(foreach($d in $selected){
    $props=Properties $d.InstanceId
    $chain=@()
    $parent=$props['DEVPKEY_Device_Parent']
    for($depth=0;$depth -lt 8 -and $parent;$depth++){
        $chain+=$parent
        $pp=Properties $parent
        $parent=$pp['DEVPKEY_Device_Parent']
    }
    [pscustomobject]@{
        status=$d.Status;class=$d.Class;name=$d.FriendlyName;id=$d.InstanceId
        problem=$props['DEVPKEY_Device_ProblemCode']
        location_paths=$props['DEVPKEY_Device_LocationPaths']
        service=$props['DEVPKEY_Device_Service'];parents=$chain
    }
})
$baseline=@(Get-Content -LiteralPath (Join-Path $root 'outputs/pico-usb-baseline-20261022.json') -Raw | ConvertFrom-Json)
$nowIds=@($devices.InstanceId)
$report=[ordered]@{
    recorded_at=(Get-Date).ToString('o');label=$Label
    readonly=$true;device_enable_disable_commands=0;driver_changes=0
    baseline_devices_missing=@($baseline | Where-Object {$_.InstanceId -notin $nowIds})
    new_usb_hid_devices=@($devices | Where-Object {$_.InstanceId -match '^(USB|HID)\\' -and $_.InstanceId -notin $baseline.InstanceId} | Select-Object Status,Class,FriendlyName,InstanceId)
    devices=$rows
}
$file=Join-Path $root ('outputs/pico-usb-'+$Label+'-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.json')
$report | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $file -Encoding UTF8
'REPORT '+$file
'MISSING_BASELINE '+@($report.baseline_devices_missing).Count
$report.new_usb_hid_devices | Select-Object Status,Class,FriendlyName
$rows | Where-Object {$_.id -match '^USB\\VID_2E8A'} | ConvertTo-Json -Depth 8
