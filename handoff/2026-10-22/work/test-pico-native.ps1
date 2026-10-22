param([Parameter(Mandatory=$true)][string]$PortName)
$ErrorActionPreference='Stop'
$serial=[IO.Ports.SerialPort]::new($PortName,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.DtrEnable=$true
$serial.ReadTimeout=3000
$serial.WriteTimeout=3000
$serial.NewLine="`n"
$results=[Collections.Generic.List[string]]::new()
function Request([string]$command,[string]$prefix){
    $serial.WriteLine($command)
    for($attempt=0;$attempt -lt 5;$attempt++){
        $line=$serial.ReadLine().Trim()
        if($line.StartsWith($prefix)){return $line}
    }
    throw "No expected response to $command"
}
try{
    $serial.Open()
    Start-Sleep -Milliseconds 500
    $serial.DiscardInBuffer()
    $info=Request 'INFO' 'INFO '
    if($info -notmatch 'name=pico-usb-smoke-ram' -or $info -notmatch 'no_flash=1'){throw 'Unexpected firmware'}
    $results.Add($info)
    $times=[Collections.Generic.List[double]]::new()
    for($n=0;$n -lt 100;$n++){
        $token='test-{0:D3}-{1:X8}' -f $n,(Get-Random -Maximum 2147483647)
        $watch=[Diagnostics.Stopwatch]::StartNew()
        $reply=Request "PING $token" 'PONG '
        $watch.Stop()
        if($reply -ne "PONG $token"){throw 'PING reply mismatch'}
        $times.Add($watch.Elapsed.TotalMilliseconds)
    }
    $results.Add('USB_REQUEST_RESPONSE passed=100 total=100')
    $stats=$times | Measure-Object -Minimum -Maximum -Average
    $results.Add(('HOST_ROUNDTRIP_MS min={0:F3} avg={1:F3} max={2:F3}' -f $stats.Minimum,$stats.Average,$stats.Maximum))
    $jedec=Request 'JEDEC' 'JEDEC '
    $results.Add($jedec)
    $sfdp=Request 'SFDP' 'SFDP '
    $results.Add($sfdp)
    $hex=$sfdp.Substring(5)
    $bytes=[byte[]]::new($hex.Length/2)
    for($i=0;$i -lt $bytes.Length;$i++){$bytes[$i]=[Convert]::ToByte($hex.Substring($i*2,2),16)}
    if($bytes.Length -ge 16 -and [Text.Encoding]::ASCII.GetString($bytes,0,4) -eq 'SFDP'){
        for($header=0;$header -le $bytes[6];$header++){
            $offset=8+8*$header
            if($offset+7 -ge $bytes.Length){break}
            if($bytes[$offset] -eq 0 -and $bytes[$offset+7] -eq 255){
                $ptr=[int]$bytes[$offset+4]+256*[int]$bytes[$offset+5]+65536*[int]$bytes[$offset+6]
                if($ptr+7 -ge $bytes.Length){continue}
                $density=[BitConverter]::ToUInt32($bytes,$ptr+4)
                if($density -band 0x80000000L){$bits=[Math]::Pow(2,($density -band 0x7fffffffL))}else{$bits=[double]$density+1}
                $results.Add(('SFDP_DENSITY_BYTES {0:F0}' -f ($bits/8)))
            }
        }
    }else{$results.Add('SFDP_NOT_AVAILABLE')}
    $results.Add((Request 'REBOOT' 'REBOOT'))
}finally{
    try{if($serial.IsOpen){$serial.Close()}}catch{}
    try{$serial.Dispose()}catch{}
    $output=Join-Path (Split-Path -Parent $PSScriptRoot) 'outputs\pico-native-test.txt'
    $results | Set-Content -LiteralPath $output -Encoding utf8
    $results
}
