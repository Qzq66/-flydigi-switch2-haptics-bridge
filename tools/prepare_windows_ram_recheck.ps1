# Uses original local tools; credentials and board selection stay in ignored files.
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$localTools='C:\Users\quziqi\Documents\Codex\pico-work-20261022'
$env:PICO_SDK_PATH=Join-Path $localTools 'pico-tools\pico-sdk'
$env:PICO_TOOLCHAIN_PATH=Join-Path $localTools 'pico-tools'
$env:picotool_DIR=Join-Path $localTools 'picotool-2.3.1\picotool'
$env:pioasm_DIR=Join-Path $localTools 'pico-tools\sdk-tools-2.3.1\pioasm'
$cmakeBin='D:\GPT-SoVITS-v2-240821 AI语音\runtime\Lib\site-packages\cmake\data\bin'
$env:PATH=$cmakeBin+';'+(Join-Path $localTools 'pico-tools\ninja')+';'+(Join-Path $localTools 'pico-tools\bin')+';'+$env:PATH
$python='C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe'
$hotspot=Join-Path $root 'handoff\2026-10-22\work\pico-hotspot.ps1'
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $hotspot -BridgeNetwork
if($LASTEXITCODE -ne 0){throw 'Hotspot preparation failed'}
& $python (Join-Path $root 'tools\build_pico_snapshot.py') --variant v042 --profile ram
if($LASTEXITCODE -ne 0){throw 'RAM compilation or image checks failed'}
'RAM build verified. No device loaded by this preparation script.'
