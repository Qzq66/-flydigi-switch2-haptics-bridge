# Native output is copied as bytes. All callers use fixed experiment commands.
function Test-PktmonIdle([string]$Text){
    $expected=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('5pWw5o2u5YyF55uR6KeG5Zmo5rKh5pyJ6L+Q6KGM44CC'))
    return $Text.Trim() -eq $expected
}
function Test-PktmonEmptyFilters([string]$Text){
    $expected=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('5pWw5o2u5YyF562b6YCJ5ZmoOuaXoA=='))
    return ($Text -replace '\s','') -eq $expected
}
function Test-PktmonOwnFilter([string]$Text,[string]$Name){
    $rows=@($Text -split '\r?\n' | Where-Object {$_ -match '^\s*\d+\s+'})
    return $rows.Count -eq 1 -and $rows[0] -match ('(^|\s)'+[regex]::Escape($Name)+'(\s|$)')
}
function Test-PktmonOwnCapture([string]$Text,[string]$LogName){
    return $Text.IndexOf($LogName,[StringComparison]::OrdinalIgnoreCase) -ge 0
}
function Quote-PktmonArgument([string]$Text){
    if($Text -match '["\r\n]'){throw 'Unsafe native argument'}
    return '"'+$Text+'"'
}
function Invoke-PktmonCaptureCommand([string[]]$QueryArguments,[string]$Tag){
    $script:NativeIndex++
    $prefix=('{0:d2}-{1}' -f $script:NativeIndex,$Tag)
    $process=New-Object Diagnostics.Process
    $process.StartInfo.FileName=Join-Path $env:SystemRoot 'System32/PktMon.exe'
    $process.StartInfo.Arguments=($QueryArguments | ForEach-Object {Quote-PktmonArgument $_}) -join ' '
    $process.StartInfo.UseShellExecute=$false;$process.StartInfo.CreateNoWindow=$true
    $process.StartInfo.RedirectStandardOutput=$true;$process.StartInfo.RedirectStandardError=$true
    $stdout=New-Object IO.MemoryStream;$stderr=New-Object IO.MemoryStream
    try{
        if(-not $process.Start()){throw 'PktMon command could not start'}
        $copyOut=$process.StandardOutput.BaseStream.CopyToAsync($stdout)
        $copyErr=$process.StandardError.BaseStream.CopyToAsync($stderr)
        if(-not $process.WaitForExit(5000)){
            $process.Kill();$null=$process.WaitForExit(3000)
            throw ('Own PktMon command timed out: '+$Tag)
        }
        $null=$copyOut.GetAwaiter().GetResult();$null=$copyErr.GetAwaiter().GetResult()
        $outPath=Join-Path $RawRoot ($prefix+'.stdout')
        $errPath=Join-Path $RawRoot ($prefix+'.stderr')
        [IO.File]::WriteAllBytes($outPath,$stdout.ToArray());[IO.File]::WriteAllBytes($errPath,$stderr.ToArray())
        $Report.commands += [ordered]@{tag=$Tag;exit_code=$process.ExitCode;stdout_file=($prefix+'.stdout');stdout_sha256=(Get-FileHash -LiteralPath $outPath -Algorithm SHA256).Hash.ToLowerInvariant();stderr_sha256=(Get-FileHash -LiteralPath $errPath -Algorithm SHA256).Hash.ToLowerInvariant()}
        return [pscustomobject]@{Code=$process.ExitCode;Text=(New-Object Text.UTF8Encoding($false,$true)).GetString($stdout.ToArray())}
    }finally{$process.Dispose();$stdout.Dispose();$stderr.Dispose()}
}
