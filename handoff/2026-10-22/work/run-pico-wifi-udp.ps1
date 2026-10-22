$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$credentials=Import-Clixml -LiteralPath (Join-Path $PSScriptRoot 'private\pico-hotspot-credentials.xml')
$nonceBytes=New-Object byte[] 8
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($nonceBytes)
$nonce=[BitConverter]::ToString($nonceBytes).Replace('-','')
& (Join-Path $PSScriptRoot 'enter-pico-bootsel.ps1') -PortName COM11
$tool=Join-Path $PSScriptRoot 'picotool-2.3.1\picotool\picotool.exe'
$ready=$false
for($n=0;$n -lt 35;$n++){$null=& $tool info --ser PICO_SERIAL_REDACTED 2>&1;if($LASTEXITCODE -eq 0){$ready=$true;break};Start-Sleep -Milliseconds 350}
if(-not $ready){throw 'BOOTSEL timeout'}
& $tool load -v -x (Join-Path $root 'outputs\pico-wifi-udp-ram\pico_wifi_udp.uf2') --ser PICO_SERIAL_REDACTED | Out-Null
if($LASTEXITCODE -ne 0){throw 'UDP RAM load failed'}
$candidate=$null;$deadline=[DateTime]::UtcNow.AddSeconds(15)
while([DateTime]::UtcNow -lt $deadline){
    $ports=@(Get-CimInstance Win32_SerialPort | Where-Object {$_.PNPDeviceID -like 'USB\VID_2E8A&PID_0009&MI_00\*'})
    if($ports.Count -gt 1){throw 'Multiple Pico CDC candidates'}
    if($ports.Count -eq 1){$candidate=$ports[0].DeviceID;break};Start-Sleep -Milliseconds 250
}
if(-not $candidate){throw 'UDP diagnostic CDC not found; firmware self-exits after 60 seconds'}
$serial=[IO.Ports.SerialPort]::new($candidate,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.DtrEnable=$true;$serial.WriteTimeout=2000
$probe='';$testCode=1
try{
    $serial.Open();$serial.WriteLine('INFO');$identity='';$timer=[Diagnostics.Stopwatch]::StartNew()
    while($timer.Elapsed.TotalSeconds -lt 2){Start-Sleep -Milliseconds 100;$identity+=$serial.ReadExisting();if($identity -match 'pico-wifi-udp-ram no_flash=1'){break}}
    if($identity -notmatch 'pico-wifi-udp-ram no_flash=1'){throw 'UDP diagnostic identity mismatch'}
    $ssidHex=[BitConverter]::ToString([Text.Encoding]::UTF8.GetBytes($credentials.ssid)).Replace('-','')
    $bstr=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($credentials.passphrase)
    try{
        $plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        $passHex=[BitConverter]::ToString([Text.Encoding]::UTF8.GetBytes($plain)).Replace('-','')
        $serial.WriteLine('JOIN '+$ssidHex+' '+$passHex+' '+$nonce)
    }finally{[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr);$plain=$null;$passHex=$null}
    $timer.Restart()
    while($timer.Elapsed.TotalSeconds -lt 30){
        Start-Sleep -Milliseconds 100
        try{$probe+=$serial.ReadExisting()}catch{break}
        if($probe -match 'UDP_READY (\d+\.\d+\.\d+\.\d+) 49723'){$picoAddress=$matches[1];break}
    }
    $probe | Set-Content -LiteralPath (Join-Path $root 'outputs\pico-wifi-udp-join.txt') -Encoding utf8
    $probe
    if(-not $picoAddress){throw 'Pico did not join hotspot; radio will auto-stop'}
    & 'C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe' (Join-Path $PSScriptRoot 'test-pico-wifi-udp.py') --ip $picoAddress --session $nonce
    $testCode=$LASTEXITCODE
}finally{
    try{if($serial.IsOpen){$serial.WriteLine('REBOOT');Start-Sleep -Milliseconds 200;$serial.Close()}}catch{}
    $serial.Dispose()
}
$deadline=[DateTime]::UtcNow.AddSeconds(15)
while('COM11' -notin [IO.Ports.SerialPort]::GetPortNames()){if([DateTime]::UtcNow -ge $deadline){throw 'Original MicroPython port not returned'};Start-Sleep -Milliseconds 250}
& (Join-Path $PSScriptRoot 'test-pico-repl.ps1') -PortName COM11
if($testCode -ne 0){throw 'Wireless diagnostic reported errors; retain measurements'}
