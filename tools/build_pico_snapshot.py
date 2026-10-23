#!/usr/bin/env python3
"""Portable snapshot build only. Never load a device or invoke output tests."""
import os,pathlib,argparse,subprocess,sys
p=argparse.ArgumentParser();p.add_argument('--variant',choices=('v040','v042','v043'),default='v042');p.add_argument('--profile',choices=('ram','flash'),default='ram');p.add_argument('--compile-only',action='store_true',help='Use public dummy credentials in ignored build directory; never flash this image');p.add_argument('--private-dir',type=pathlib.Path,help='Explicit local credentials directory');p.add_argument('--build-dir',type=pathlib.Path,help='Keep alternate network builds separate');p.add_argument('--ram-end-bootsel',action='store_true',help='Diagnostic RAM session exits to BOOTSEL, without starting retained Flash firmware');p.add_argument('--ram-diagnostic-recovery',action='store_true');a=p.parse_args()
if a.ram_diagnostic_recovery and (a.variant!='v043' or a.profile!='ram' or not a.ram_end_bootsel):p.error('Snapshot recovery requires v043 RAM with BOOTSEL return')
if a.ram_end_bootsel and (a.variant not in ('v042','v043') or a.profile!='ram'):p.error('--ram-end-bootsel requires v042/v043 RAM')
root=pathlib.Path(__file__).absolute().parents[1];snap=root/'handoff/2026-10-22'
sdk=os.environ.get('PICO_SDK_PATH');private=a.private_dir or snap/'work/private'
if a.compile_only and a.private_dir:p.error('--compile-only cannot use actual private credentials')
if not sdk or not (pathlib.Path(sdk)/'external/pico_sdk_import.cmake').is_file():p.error('Set PICO_SDK_PATH to a complete local Pico SDK checkout')
if a.compile_only:
    private=root/'build'/'compile-only-private'
    private.mkdir(parents=True,exist_ok=True)
    (private/'bridge_credentials.h').write_text((snap/'work/bridge_credentials.example.h').read_text(),encoding='utf-8')
if not (private/'bridge_credentials.h').is_file():p.error('Create the local ignored work/private/bridge_credentials.h; never commit real credentials')
build=a.build_dir or root/'build'/('pico-'+a.variant+'-'+a.profile+('-compile-only' if a.compile_only else ''))
subprocess.run(['cmake','-S',str(snap/'outputs'/('pico-haptics-bridge-'+a.variant)),'-B',str(build),'-G','Ninja','-DPICO_BOARD=pico2_w','-DPICO_PLATFORM=rp2350-arm-s','-DPICO_FLASH_SIZE_BYTES=4194304','-DPICO_NO_FLASH='+('1' if a.profile=='ram' else '0'),'-DBRIDGE_PRIVATE_DIR='+str(private),'-DCMAKE_BUILD_TYPE=Release','-DBRIDGE_RAM_END_BOOTSEL='+('ON' if a.ram_end_bootsel else 'OFF'),'-DBRIDGE_RAM_DIAGNOSTIC_RECOVERY='+('ON' if a.ram_diagnostic_recovery else 'OFF')]+(['-Dpicotool_DIR='+os.environ['picotool_DIR']] if os.environ.get('picotool_DIR') else []),check=True)
subprocess.run(['cmake','--build',str(build),'--parallel','4'],check=True)
image=build/('pico_pro_capture.'+('uf2' if a.profile=='ram' else 'bin'))
subprocess.run([sys.executable,str(snap/'work/verify-capture-v035-image.py'),a.profile,str(image)],check=True)
symbols=subprocess.check_output(['arm-none-eabi-nm',str(build/'pico_pro_capture.elf')],text=True)
if a.profile=='ram' and any(line.split()[-1] in ('flash_range_program','flash_range_erase') for line in symbols.splitlines() if line.split()):
    raise RuntimeError('RAM build contains Flash mutation routines')
print('Built and bounds-checked. Nothing was flashed. Source/session binaries remain private build products.')
