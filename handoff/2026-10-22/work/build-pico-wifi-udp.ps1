$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$tools='C:\Users\WINDOWS_USER\Documents\Codex\pico-work-20261022'
$source='C:\Users\WINDOWS_USER\Documents\Codex\pico-wifi-udp-20261022'
if(-not(Test-Path $source)){New-Item -ItemType Junction -Path $source -Target (Join-Path $root 'outputs\pico-wifi-udp-ram') | Out-Null}
$env:PICO_SDK_PATH=Join-Path $tools 'pico-tools\pico-sdk'
$env:PICO_TOOLCHAIN_PATH=Join-Path $tools 'pico-tools'
$cmake='D:\GPT-SoVITS-v2-240821 AI语音\runtime\Lib\site-packages\cmake\data\bin\cmake.exe'
$build=Join-Path $tools 'pico-wifi-udp-build'
& $cmake -S $source -B $build -G Ninja "-DCMAKE_MAKE_PROGRAM=$tools\pico-tools\ninja\ninja.exe" "-Dpicotool_DIR=$tools\picotool-2.3.1\picotool" "-Dpioasm_DIR=$tools\pico-tools\sdk-tools-2.3.1\pioasm" '-DPython3_EXECUTABLE=C:/Program Files (x86)/Microsoft Visual Studio/Shared/Python39_64/python.exe' -DCMAKE_BUILD_TYPE=Release
if($LASTEXITCODE -ne 0){throw 'Probe configure failed'}
& $cmake --build $build --parallel 6
if($LASTEXITCODE -ne 0){throw 'Probe build failed'}
Copy-Item (Join-Path $build 'pico_wifi_udp.uf2') (Join-Path $root 'outputs\pico-wifi-udp-ram')
& 'C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe' (Join-Path $PSScriptRoot 'verify-capture-image.py') ram (Join-Path $root 'outputs\pico-wifi-udp-ram\pico_wifi_udp.uf2')
if($LASTEXITCODE -ne 0){throw 'RAM bounds failed'}
$symbols=& "$tools\pico-tools\bin\arm-none-eabi-nm.exe" (Join-Path $build 'pico_wifi_udp.elf')
if($symbols -match '\b(flash_range_program|flash_range_erase)\b'){throw 'No Flash mutation routines permitted'}

