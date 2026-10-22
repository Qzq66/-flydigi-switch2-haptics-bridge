$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$toolsRoot=Join-Path $PSScriptRoot 'pico-tools'
New-Item -ItemType Directory -Path $toolsRoot -Force | Out-Null
$armZip=Join-Path $toolsRoot 'arm-gnu-toolchain-14.2.rel1.zip'
$armUrl='https://armkeil.blob.core.windows.net/developer/Files/downloads/gnu/14.2.rel1/binrel/arm-gnu-toolchain-14.2.rel1-mingw-w64-x86_64-arm-none-eabi.zip'
if(-not (Test-Path -LiteralPath $armZip)) {
    'Downloading official Arm GNU toolchain 14.2.Rel1...'
    Invoke-WebRequest -Uri $armUrl -OutFile $armZip
}
Get-FileHash -LiteralPath $armZip -Algorithm SHA256 | Format-List
$armDir=$toolsRoot
if(-not (Test-Path -LiteralPath (Join-Path $armDir 'bin\arm-none-eabi-gcc.exe'))) {
    'Extracting Arm toolchain...'
    tar -xf $armZip -C $toolsRoot
    if($LASTEXITCODE -ne 0){throw 'Arm extraction failed'}
}
$ninjaZip=Join-Path $toolsRoot 'ninja-1.13.2-win.zip'
if(-not (Test-Path -LiteralPath $ninjaZip)) {
    Invoke-WebRequest -Uri 'https://github.com/ninja-build/ninja/releases/download/v1.13.2/ninja-win.zip' -OutFile $ninjaZip
}
if((Get-FileHash -LiteralPath $ninjaZip -Algorithm SHA256).Hash -ne '07FC8261B42B20E71D1720B39068C2E14FFCEE6396B76FB7A795FB460B78DC65'){throw 'Ninja hash mismatch'}
Expand-Archive -LiteralPath $ninjaZip -DestinationPath (Join-Path $toolsRoot 'ninja') -Force
$sdkDir=Join-Path $toolsRoot 'pico-sdk'
if(-not (Test-Path -LiteralPath (Join-Path $sdkDir '.git'))) {
    git clone --depth 1 --branch 2.3.1 https://github.com/raspberrypi/pico-sdk.git $sdkDir
    if($LASTEXITCODE -ne 0){throw 'Pico SDK clone failed'}
}
$sdkCommit=git -C $sdkDir rev-parse HEAD
if($sdkCommit -ne '079c6f39023649b154152db30f1d781e884879bc'){throw 'SDK commit mismatch'}
git -C $sdkDir submodule update --init --depth 1 lib/tinyusb
if($LASTEXITCODE -ne 0){throw 'TinyUSB checkout failed'}
& (Join-Path $armDir 'bin\arm-none-eabi-gcc.exe') --version
& (Join-Path $toolsRoot 'ninja\ninja.exe') --version
git -C $sdkDir submodule status lib/tinyusb
'Portable toolchain ready; system PATH unchanged.'
