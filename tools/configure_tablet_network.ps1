param([Parameter(Mandatory=$true)][int]$InterfaceIndex,[switch]$ReuseLocalPassword)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$root=Split-Path -Parent $PSScriptRoot
$private=Join-Path $root 'handoff\2026-10-22\work\private\tablet-network'
$address=Get-NetIPAddress -InterfaceIndex $InterfaceIndex -AddressFamily IPv4 | Where-Object { $_.AddressState -eq 'Preferred' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -First 1
if(-not $address){throw 'No preferred IPv4 address on selected interface'}
$profile=Get-NetConnectionProfile -InterfaceIndex $InterfaceIndex
$wlanLines=netsh wlan show interfaces
$bandLine=@($wlanLines | Where-Object { $_ -match '^\s*(Band|波段|频带)\s*:' }) -join ' '
$authLine=@($wlanLines | Where-Object { $_ -match '^\s*(Authentication|身份验证)\s*:' }) -join ' '
if($bandLine -notmatch '2\.4\s*GHz' -or $authLine -notmatch 'WPA2-Personal'){throw 'Selected Wi-Fi must be 2.4GHz WPA2-Personal; credentials were not changed'}
$ssidLines=@($wlanLines | Where-Object { $_ -match '^\s*SSID\s*:' })
if($ssidLines.Count -ne 1){throw 'Expected one actual connected Wi-Fi SSID'}
$actualSsid=($ssidLines[0] -replace '^\s*SSID\s*:\s*','').Trim()
$octets=[Net.IPAddress]::Parse($address.IPAddress).GetAddressBytes()
$number=([uint64]$octets[0] -shl 24) -bor ([uint64]$octets[1] -shl 16) -bor ([uint64]$octets[2] -shl 8) -bor [uint64]$octets[3]
$prefix=[int]$address.PrefixLength
if($prefix -lt 1 -or $prefix -gt 30){throw 'Unsupported LAN prefix'}
$mask=([uint64]4294967295 -shl (32-$prefix)) -band [uint64]4294967295
$netNumber=$number -band $mask
$subnet=(([string](($netNumber -shr 24) -band 255))+'.'+(($netNumber -shr 16) -band 255)+'.'+(($netNumber -shr 8) -band 255)+'.'+($netNumber -band 255)+'/'+$prefix)
$form=New-Object Windows.Forms.Form
$form.Text='Pico network test - local credentials'
$form.Size=New-Object Drawing.Size(520,255)
$form.StartPosition='CenterScreen';$form.TopMost=$true;$form.FormBorderStyle='FixedDialog';$form.MaximizeBox=$false;$form.MinimizeBox=$false
$notice=New-Object Windows.Forms.Label
$notice.Text='Local input only. Use the tablet 2.4GHz WPA2 hotspot.'+"`r`n"+'PC: '+$address.IPAddress+'   No motor output; RAM test only.'
$notice.Location=New-Object Drawing.Point(20,15);$notice.Size=New-Object Drawing.Size(470,40);$form.Controls.Add($notice)
$ssidLabel=New-Object Windows.Forms.Label;$ssidLabel.Text='Hotspot name (SSID)';$ssidLabel.Location=New-Object Drawing.Point(20,70);$ssidLabel.AutoSize=$true;$form.Controls.Add($ssidLabel)
$ssidBox=New-Object Windows.Forms.TextBox;$ssidBox.Location=New-Object Drawing.Point(180,66);$ssidBox.Size=New-Object Drawing.Size(290,25);$ssidBox.Text=$actualSsid;$form.Controls.Add($ssidBox)
$keyLabel=New-Object Windows.Forms.Label;$keyLabel.Text='Hotspot password';$keyLabel.Location=New-Object Drawing.Point(20,110);$keyLabel.AutoSize=$true;$form.Controls.Add($keyLabel)
$keyBox=New-Object Windows.Forms.TextBox;$keyBox.Location=New-Object Drawing.Point(180,106);$keyBox.Size=New-Object Drawing.Size(290,25);$keyBox.UseSystemPasswordChar=$true;$form.Controls.Add($keyBox)
if($ReuseLocalPassword){
    $oldHeader=[IO.File]::ReadAllText((Join-Path $private 'bridge_credentials.h'))
    $keyMatch=[regex]::Match($oldHeader,'bridge_key\[\]="((?:\\x[0-9a-fA-F]{2})+)";')
    if(-not $keyMatch.Success){throw 'Local password unavailable; use interactive input'}
    $keyOctets=[byte[]]@([regex]::Matches($keyMatch.Groups[1].Value,'\\x([0-9a-fA-F]{2})') | ForEach-Object {[Convert]::ToByte($_.Groups[1].Value,16)})
    $keyBox.Text=[Text.Encoding]::UTF8.GetString($keyOctets)
    $oldHeader=$null;$keyOctets=$null
}
$ok=New-Object Windows.Forms.Button;$ok.Text='Save locally';$ok.Location=New-Object Drawing.Point(270,160);$ok.Size=New-Object Drawing.Size(100,30)
$ok.Add_Click({
    $ssidBytes=[Text.Encoding]::UTF8.GetByteCount($ssidBox.Text);$keyBytes=[Text.Encoding]::UTF8.GetByteCount($keyBox.Text)
    if($ssidBytes -lt 1 -or $ssidBytes -gt 32 -or $keyBytes -lt 8 -or $keyBytes -gt 63){[Windows.Forms.MessageBox]::Show('SSID must be 1-32 UTF-8 bytes; password 8-63 bytes.') | Out-Null;return}
    $form.DialogResult=[Windows.Forms.DialogResult]::OK;$form.Close()
});$form.Controls.Add($ok);$form.AcceptButton=$ok
$cancel=New-Object Windows.Forms.Button;$cancel.Text='Cancel';$cancel.Location=New-Object Drawing.Point(380,160);$cancel.DialogResult=[Windows.Forms.DialogResult]::Cancel;$form.Controls.Add($cancel);$form.CancelButton=$cancel
if(-not $ReuseLocalPassword -and $form.ShowDialog() -ne [Windows.Forms.DialogResult]::OK){$form.Dispose();throw 'Local credential input cancelled; no device changed'}
try{
    New-Item -ItemType Directory -Force -Path $private | Out-Null
    function C-String([string]$value){return '"'+(([Text.Encoding]::UTF8.GetBytes($value) | ForEach-Object {'\x'+$_.ToString('x2')}) -join '')+'"'}
    $random=New-Object byte[] 8;$rng=[Security.Cryptography.RandomNumberGenerator]::Create();try{$rng.GetBytes($random)}finally{$rng.Dispose()}
    $session=([BitConverter]::ToString($random)).Replace('-','').ToLower()
    $hostHex=$number.ToString('x8')
    $header='static const char bridge_ssid[]='+ (C-String $ssidBox.Text)+';'+"`n"+'static const char bridge_key[]='+(C-String $keyBox.Text)+';'+"`n"+'#define BRIDGE_SESSION UINT64_C(0x'+$session+")`n"+'#define BRIDGE_HOST_IPV4 0x'+$hostHex+"u`n"
    [IO.File]::WriteAllText((Join-Path $private 'bridge_credentials.h'),$header,[Text.Encoding]::ASCII)
    [ordered]@{bind_host=$address.IPAddress;subnet=$subnet;port=49724} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $private 'network-config.json') -Encoding utf8
    'Local network parameters saved. Credentials and session were not printed. No device changed.'
}finally{$keyBox.Clear();$header=$null;$session=$null;$form.Dispose()}
