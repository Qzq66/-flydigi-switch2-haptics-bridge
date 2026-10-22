param([string]$PortName = 'COM11')
$ErrorActionPreference='Stop'
$serial = [System.IO.Ports.SerialPort]::new($PortName,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$serial.ReadTimeout=2000
$serial.WriteTimeout=2000
$serial.DtrEnable=$true
$code = @'
import sys, os, gc, time, machine
print('PICO_TEST_BEGIN')
print('IMPLEMENTATION', sys.implementation)
print('UNAME', os.uname())
print('CPU_HZ', machine.freq())
gc.collect()
print('GC_FREE', gc.mem_free())
v = os.statvfs('/')
print('FILESYSTEM_BLOCK_BYTES', v[0], 'BLOCKS', v[2], 'FREE_BLOCKS', v[3])
for n in range(10):
    print('USB_PING', n, sum(range(1001)))
    time.sleep_ms(50)
print('PICO_TEST_END')
'@
try {
    $serial.Open()
    $serial.Write([string][char]3 + [char]3)
    Start-Sleep -Milliseconds 200
    $null=$serial.ReadExisting()
    $serial.Write([string][char]1)
    Start-Sleep -Milliseconds 150
    $null=$serial.ReadExisting()
    $serial.Write($code.Replace("`r",'')+"`n"+[char]4)
    $result=''
    $timer=[Diagnostics.Stopwatch]::StartNew()
    while($timer.Elapsed.TotalSeconds -lt 10) {
        Start-Sleep -Milliseconds 100
        $result += $serial.ReadExisting()
        if($result -match 'PICO_TEST_END' -and $result.Contains([string][char]4)){break}
    }
    $serial.Write([string][char]2)
    $clean=$result.Replace([string][char]4,'').Replace([string][char]0,'')
    $outFile=Join-Path (Split-Path -Parent $PSScriptRoot) 'outputs\pico-usb-repl-test.txt'
    $clean | Set-Content -LiteralPath $outFile -Encoding utf8
    $clean
    if($clean -notmatch 'PICO_TEST_END' -or ([regex]::Matches($clean,'USB_PING \d+ 500500')).Count -ne 10 -or $clean -match 'Traceback'){throw 'REPL test failed; inspect output'}
} finally {
    if($serial.IsOpen){$serial.Close()}
    $serial.Dispose()
}
