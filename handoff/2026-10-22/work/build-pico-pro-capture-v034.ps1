param([ValidateSet('ram','flash')][string]$Profile='ram')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$tools='C:\Users\WINDOWS_USER\Documents\Codex\pico-work-20261022'
$source='C:\Users\WINDOWS_USER\Documents\Codex\pico-pro-capture-v034-20261022'
if(-not(Test-Path -LiteralPath $source)){New-Item -ItemType Junction -Path $source -Target (Join-Path $root 'outputs\pico-pro-capture-v034') | Out-Null}
$env:PICO_SDK_PATH=Join-Path $tools 'pico-tools\pico-sdk'
$env:PICO_TOOLCHAIN_PATH=Join-Path $tools 'pico-tools'
$cmake='D:\GPT-SoVITS-v2-240821 AI语音\runtime\Lib\site-packages\cmake\data\bin\cmake.exe'
$build=Join-Path $tools ('pico-pro-capture-v034-'+$Profile+'-build')
$noFlash=if($Profile -eq 'ram'){1}else{0}
& $cmake -S $source -B $build -G Ninja "-DCMAKE_MAKE_PROGRAM=$tools\pico-tools\ninja\ninja.exe" "-Dpicotool_DIR=$tools\picotool-2.3.1\picotool" '-DPython3_EXECUTABLE=C:/Program Files (x86)/Microsoft Visual Studio/Shared/Python39_64/python.exe' "-DPICO_NO_FLASH=$noFlash" -DCMAKE_BUILD_TYPE=Release
if($LASTEXITCODE -ne 0){throw 'Configure failed'}
& $cmake --build $build --parallel 6
if($LASTEXITCODE -ne 0){throw 'Build failed'}
$out=Join-Path $source $Profile
New-Item -ItemType Directory -Force -Path $out | Out-Null
$imageExt=if($Profile -eq 'ram'){'uf2'}else{'bin'}
foreach($ext in @($imageExt,'elf')){Copy-Item -LiteralPath (Join-Path $build ('pico_pro_capture.'+$ext)) -Destination $out}
& 'C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe' (Join-Path $PSScriptRoot 'verify-capture-image.py') $Profile (Join-Path $out ('pico_pro_capture.'+$imageExt))
if($LASTEXITCODE -ne 0){throw 'Image bounds failed'}
$symbols=& "$tools\pico-tools\bin\arm-none-eabi-nm.exe" (Join-Path $out 'pico_pro_capture.elf')
if($Profile -eq 'ram' -and $symbols -match '\b(flash_range_program|flash_range_erase)\b'){throw 'RAM build must not contain Flash mutation routines'}
Get-FileHash -LiteralPath (Join-Path $out ('pico_pro_capture.'+$imageExt)) -Algorithm SHA256
