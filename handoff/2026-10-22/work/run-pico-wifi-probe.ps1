$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'enter-pico-bootsel.ps1') -PortName COM11
$tool=Join-Path $PSScriptRoot 'picotool-2.3.1\picotool\picotool.exe'
$ready=$false
for($n=0;$n -lt 35;$n++){
    $null=& $tool info --ser PICO_SERIAL_REDACTED 2>&1
    if($LASTEXITCODE -eq 0){$ready=$true;break};Start-Sleep -Milliseconds 350
}
if(-not $ready){throw 'BOOTSEL timeout'}
& $tool load -v -x (Join-Path (Split-Path -Parent $PSScriptRoot) 'outputs\pico-wifi-ram-probe\pico_wifi_probe.uf2') --ser PICO_SERIAL_REDACTED | Out-Null
if($LASTEXITCODE -ne 0){throw 'RAM load failed'}
$candidate=$null;$deadline=[DateTime]::UtcNow.AddSeconds(15)
while([DateTime]::UtcNow -lt $deadline){
    $ports=@(Get-CimInstance Win32_SerialPort | Where-Object {$_.PNPDeviceID -like 'USB\VID_2E8A&PID_0009&MI_00\*'})
    if($ports.Count -gt 1){throw 'Multiple candidate Pico CDC ports'}
    if($ports.Count -eq 1){$candidate=$ports[0].DeviceID;break}
    Start-Sleep -Milliseconds 250
}
if(-not $candidate){throw 'Probe CDC port not found; RAM image auto-reboots after 60 seconds'}
$serial=[IO.Ports.SerialPort]::new($candidate,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.DtrEnable=$true;$serial.ReadTimeout=500;$serial.WriteTimeout=2000
try{
    $serial.Open();$serial.WriteLine('INFO');$identity='';$timer=[Diagnostics.Stopwatch]::StartNew()
    while($timer.Elapsed.TotalSeconds -lt 2){Start-Sleep -Milliseconds 100;$identity+=$serial.ReadExisting();if($identity -match 'pico-wifi-ram-probe no_flash=1'){break}}
    if($identity -notmatch 'pico-wifi-ram-probe no_flash=1'){throw 'Probe identity mismatch'}
    $identity
    $serial.WriteLine('PROBE');$result='';$timer.Restart()
    while($timer.Elapsed.TotalSeconds -lt 12){
        Start-Sleep -Milliseconds 100
        try{$result+=$serial.ReadExisting()}catch{break}
        if($result -match 'WIFI_C_PROBE_END'){break}
    }
    $result | Set-Content -LiteralPath (Join-Path (Split-Path -Parent $PSScriptRoot) 'outputs\pico-wifi-c-probe.txt') -Encoding utf8
    $result
}finally{try{if($serial.IsOpen){$serial.Close()}}catch{};$serial.Dispose()}
$deadline=[DateTime]::UtcNow.AddSeconds(15)
while('COM11' -notin [IO.Ports.SerialPort]::GetPortNames()){
    if([DateTime]::UtcNow -ge $deadline){throw 'Original MicroPython port has not returned'}
    Start-Sleep -Milliseconds 250
}
& (Join-Path $PSScriptRoot 'test-pico-repl.ps1') -PortName COM11
if($result -notmatch 'FW_VERSION_STATUS 0'){throw 'Wireless firmware query did not succeed; retain diagnostic log'}
