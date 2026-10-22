param([string]$PortName='COM11')
$ErrorActionPreference='Stop'
$serial=[IO.Ports.SerialPort]::new($PortName,115200,[IO.Ports.Parity]::None,8,[IO.Ports.StopBits]::One)
$serial.DtrEnable=$true
try{
    $serial.Open()
    $serial.Write([string][char]3+[char]3)
    Start-Sleep -Milliseconds 150
    $null=$serial.ReadExisting()
    $serial.Write([string][char]1)
    Start-Sleep -Milliseconds 150
    $null=$serial.ReadExisting()
    $serial.Write("import os; print(os.uname().machine)`n"+[char]4)
    Start-Sleep -Milliseconds 300
    $reply=$serial.ReadExisting()
    if($reply -notmatch 'RP2350'){throw 'Port did not identify as RP2350 MicroPython'}
    $serial.Write("import machine; machine.bootloader()`n"+[char]4)
    'Requested BOOTSEL from existing RP2350 MicroPython; no flash writes.'
}finally{
    # The requested reboot disconnects USB before Close may complete.
    try{if($serial.IsOpen){$serial.Close()}}catch{}
    try{$serial.Dispose()}catch{}
}
