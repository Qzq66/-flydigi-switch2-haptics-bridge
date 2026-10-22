$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$tools='C:\Users\WINDOWS_USER\Documents\Codex\pico-work-20261022'
$source='C:\Users\WINDOWS_USER\Documents\Codex\pico-protocol-lab-20261022'
if(-not(Test-Path -LiteralPath $source)){New-Item -ItemType Junction -Path $source -Target (Join-Path $root 'outputs\pico-protocol-lab') | Out-Null}
$env:PICO_SDK_PATH=Join-Path $tools 'pico-tools\pico-sdk'
$env:PICO_TOOLCHAIN_PATH=Join-Path $tools 'pico-tools'
$cmake='D:\GPT-SoVITS-v2-240821 AI语音\runtime\Lib\site-packages\cmake\data\bin\cmake.exe'
$build=Join-Path $tools 'pico-protocol-build'
& $cmake -S $source -B $build -G Ninja "-DCMAKE_MAKE_PROGRAM=$tools\pico-tools\ninja\ninja.exe" "-Dpicotool_DIR=$tools\picotool-2.3.1\picotool" '-DPython3_EXECUTABLE=C:/Program Files (x86)/Microsoft Visual Studio/Shared/Python39_64/python.exe' -DPICO_NO_FLASH=1 -DCMAKE_BUILD_TYPE=Release
if($LASTEXITCODE -ne 0){throw 'Configure failed'}
& $cmake --build $build --parallel 6
if($LASTEXITCODE -ne 0){throw 'Build failed'}
Copy-Item -LiteralPath (Join-Path $build 'pico_protocol_lab.uf2') -Destination (Join-Path $source 'pico_protocol_lab.uf2')
Copy-Item -LiteralPath (Join-Path $build 'pico_protocol_lab.elf') -Destination (Join-Path $source 'pico_protocol_lab.elf')
& 'C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe' (Join-Path $PSScriptRoot 'verify-ram-uf2.py') (Join-Path $source 'pico_protocol_lab.uf2')
if($LASTEXITCODE -ne 0){throw 'UF2 is not SRAM-only'}
Get-FileHash -LiteralPath (Join-Path $source 'pico_protocol_lab.uf2') -Algorithm SHA256
