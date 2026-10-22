param([string]$PortName='COM11')
$ErrorActionPreference='Stop'
$serial=[IO.Ports.SerialPort]::new($PortName,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.DtrEnable=$true;$serial.WriteTimeout=2000
$code=@'
import machine, os, time
print('WIFI_PROBE_BEGIN')
watchdog = machine.WDT(timeout=8000)
try:
    import network
    print('NETWORK_MODULE_PRESENT', hasattr(network, 'WLAN'))
    wlan = network.WLAN(network.STA_IF)
    was_active = wlan.active()
    print('PREVIOUS_ACTIVE', was_active)
    if was_active:
        print('ABORT_EXISTING_WLAN_STATE')
    else:
        wlan.active(True)
        print('STANDARD_DRIVER_ACTIVE', wlan.active())
        mac = wlan.config('mac')
        print('MAC_VALID', len(mac)==6 and any(mac))
        print('ASSOCIATED', wlan.isconnected())
        wlan.active(False)
        print('WLAN_OFF', not wlan.active())
    print('WIFI_PROBE_END')
except Exception as e:
    print('WIFI_PROBE_ERROR', repr(e))
time.sleep_ms(300)
machine.reset()
'@
try{
    $serial.Open();$serial.Write([string][char]3+[char]3)
    Start-Sleep -Milliseconds 150;$null=$serial.ReadExisting()
    $serial.Write([string][char]1);Start-Sleep -Milliseconds 150;$null=$serial.ReadExisting()
    $serial.Write("import os; print(os.uname().machine)`n"+[char]4)
    Start-Sleep -Milliseconds 300;$identity=$serial.ReadExisting()
    if($identity -notmatch 'RP2350'){throw 'Not the expected RP2350 MicroPython port'}
    $serial.Write($code.Replace("`r",'')+"`n"+[char]4)
    $result='';$timer=[Diagnostics.Stopwatch]::StartNew()
    while($timer.Elapsed.TotalSeconds -lt 14){
        Start-Sleep -Milliseconds 100
        try{$result+=$serial.ReadExisting()}catch{break}
        if($result -match 'WIFI_PROBE_END' -or $result -match 'WIFI_PROBE_ERROR'){break}
    }
    $clean=$result.Replace([string][char]4,'').Replace([string][char]0,'')
    $out=Join-Path (Split-Path -Parent $PSScriptRoot) 'outputs\pico-wifi-probe.txt'
    $clean | Set-Content -LiteralPath $out -Encoding utf8
    $clean
    if($clean -notmatch 'STANDARD_DRIVER_ACTIVE True' -or $clean -notmatch 'MAC_VALID True' -or $clean -notmatch 'WLAN_OFF True'){throw 'Standard WLAN probe incomplete; no network settings saved'}
}finally{
    try{if($serial.IsOpen){$serial.Close()}}catch{}
    $serial.Dispose()
}
