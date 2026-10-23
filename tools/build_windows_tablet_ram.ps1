param([string]$CredentialsDir,[string]$BuildDir,[ValidateSet('ram','flash')][string]$Profile='ram')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$localTools='C:\Users\quziqi\Documents\Codex\pico-work-20261022'
$env:PICO_SDK_PATH=Join-Path $localTools 'pico-tools\pico-sdk'
$env:PICO_TOOLCHAIN_PATH=Join-Path $localTools 'pico-tools'
$env:picotool_DIR=Join-Path $localTools 'picotool-2.3.1\picotool'
$env:pioasm_DIR=Join-Path $localTools 'pico-tools\sdk-tools-2.3.1\pioasm'
$cmakeRoots=@(Get-ChildItem -LiteralPath 'D:\' -Directory -Filter 'GPT-SoVITS-v2-240821*')
if($cmakeRoots.Count -ne 1){throw 'Expected exactly one retained CMake runtime folder'}
$cmakeBin=Join-Path $cmakeRoots[0].FullName 'runtime\Lib\site-packages\cmake\data\bin'
$env:PATH=$cmakeBin+';'+(Join-Path $localTools 'pico-tools\ninja')+';'+(Join-Path $localTools 'pico-tools\bin')+';'+$env:PATH
$private=if($CredentialsDir){$CredentialsDir}else{Join-Path $root 'handoff\2026-10-22\work\private\tablet-network'}
$build=if($BuildDir){$BuildDir}else{Join-Path $root 'build\pico-v042-tablet-ram'}
$python='C:\Program Files (x86)\Microsoft Visual Studio\Shared\Python39_64\python.exe'
$buildArgs=@((Join-Path $root 'tools\build_pico_snapshot.py'),'--variant','v042','--profile',$Profile,'--private-dir',$private,'--build-dir',$build)
if($Profile -eq 'ram'){$buildArgs+='--ram-end-bootsel'}
& $python @buildArgs
if($LASTEXITCODE -ne 0){throw 'RAM compilation or image checks failed'}
'Network build verified. No device loaded, no hotspot changed.'
