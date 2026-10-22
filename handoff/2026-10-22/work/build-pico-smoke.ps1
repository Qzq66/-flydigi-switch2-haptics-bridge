$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$aliasRoot='C:\Users\WINDOWS_USER\Documents\Codex\pico-work-20261022'
$sourceAlias='C:\Users\WINDOWS_USER\Documents\Codex\pico-source-20261022'
# ASCII aliases avoid toolchain path encoding issues; targets remain in this project.
if(-not (Test-Path -LiteralPath $aliasRoot)){New-Item -ItemType Junction -Path $aliasRoot -Target $PSScriptRoot | Out-Null}
$sourceRoot=Join-Path $taskRoot 'outputs\pico-minimal-firmware'
if(-not (Test-Path -LiteralPath $sourceAlias)){New-Item -ItemType Junction -Path $sourceAlias -Target $sourceRoot | Out-Null}
$armZip=Join-Path $aliasRoot 'pico-tools\arm-gnu-toolchain-14.2.rel1.zip'
if((Get-FileHash -LiteralPath $armZip -Algorithm SHA256).Hash -ne 'F074615953F76036E9A51B87F6577FDB4ED8E77D3322A6F68214E92E7859888F'){throw 'Arm official hash mismatch'}
$env:PICO_SDK_PATH=Join-Path $aliasRoot 'pico-tools\pico-sdk'
$env:PICO_TOOLCHAIN_PATH=Join-Path $aliasRoot 'pico-tools'
$cmake='D:\GPT-SoVITS-v2-240821 AI语音\runtime\Lib\site-packages\cmake\data\bin\cmake.exe'
$ninja=Join-Path $aliasRoot 'pico-tools\ninja\ninja.exe'
$buildDir=Join-Path $aliasRoot 'pico-smoke-build'
$picotoolDir=Join-Path $aliasRoot 'picotool-2.3.1\picotool'
& $cmake -S $sourceAlias -B $buildDir -G Ninja "-DCMAKE_MAKE_PROGRAM=$ninja" "-DPICO_TOOLCHAIN_PATH=$env:PICO_TOOLCHAIN_PATH" "-Dpicotool_DIR=$picotoolDir" '-DPython3_EXECUTABLE=C:/Program Files (x86)/Microsoft Visual Studio/Shared/Python39_64/python.exe' -DPICO_NO_FLASH=1 -DCMAKE_BUILD_TYPE=Release
if($LASTEXITCODE -ne 0){throw 'Configure failed'}
& $cmake --build $buildDir --parallel 6
if($LASTEXITCODE -ne 0){throw 'Build failed'}
& (Join-Path $env:PICO_TOOLCHAIN_PATH 'bin\arm-none-eabi-size.exe') (Join-Path $buildDir 'pico_usb_smoke.elf')
& (Join-Path $picotoolDir 'picotool.exe') info -a (Join-Path $buildDir 'pico_usb_smoke.uf2')
if($LASTEXITCODE -ne 0){throw 'UF2 inspection failed'}
Copy-Item -LiteralPath (Join-Path $buildDir 'pico_usb_smoke.elf') -Destination $sourceRoot
Copy-Item -LiteralPath (Join-Path $buildDir 'pico_usb_smoke.uf2') -Destination $sourceRoot
Get-FileHash -LiteralPath (Join-Path $sourceRoot 'pico_usb_smoke.uf2') -Algorithm SHA256
