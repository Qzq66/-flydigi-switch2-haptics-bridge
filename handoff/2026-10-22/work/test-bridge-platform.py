"""Offline import/CLI and fake-child supervision checks; no real children."""
import contextlib
import importlib.util
import io
import json
import pathlib
import runpy
import subprocess
import sys
from unittest.mock import patch
from bridge_process import communicate_bounded, child_succeeded

checks=[]
def check(name, condition):
    assert condition, name
    checks.append(dict(name=name,passed=True))

class Process:
    def __init__(self, responses):
        self.responses=list(responses);self.returncode=None;self.kills=0;self.waits=0
    def communicate(self, timeout):
        result=self.responses.pop(0)
        if isinstance(result,BaseException):raise result
        self.returncode=0
        return result
    def kill(self):self.kills+=1
    def poll(self):return self.returncode
    def wait(self,timeout):self.waits+=1;self.returncode=-9

p=Process([('out','err')])
check('normal child output preserved',communicate_bounded(p,5)==('out','err',False))
check('exited child is not killed',p.kills==0 and p.waits==0)
p=Process([subprocess.TimeoutExpired('fake',5),('tail','')])
check('timeout kills child and captures tail',communicate_bounded(p,5)==('tail','',True) and p.kills==1)
for name,error in [('second timeout',subprocess.TimeoutExpired('fake',2)),('communication error',OSError('fake'))]:
    responses=[subprocess.TimeoutExpired('fake',5),error] if name=='second timeout' else [error]
    p=Process(responses)
    try:communicate_bounded(p,5)
    except type(error):pass
    else:raise AssertionError(name)
    check(name+' reaps live child',p.kills>=1 and p.waits==1)
p=Process([])
try:communicate_bounded(p,0)
except ValueError:pass
else:raise AssertionError('zero timeout')
check('invalid timeout does not touch child',p.kills==0 and p.waits==0)
for live,status in [(False,'PASSED_PICO_WIFI_FLYDIGI_BENCH'),(True,'PASSED_SWITCH_WIFI_FLYDIGI_LIMITED_LIVE')]:
    report=dict(status=status)
    check(f'clean child accepted live={live}',child_succeeded(report,0,live))
    check(f'nonzero exit rejected live={live}',not child_succeeded(report,1,live))
    check(f'wrong mode rejected live={live}',not child_succeeded(report,0,not live))
    for field in ('error','cleanup_error','pico_reset_error'):
        check(f'{field} rejected live={live}',not child_succeeded(dict(report,**{field:'fake'}),0,live))
for bad in (None,[],{},dict(status='INCOMPLETE')):
    check('missing/incomplete child rejected '+repr(bad),not child_succeeded(bad,0))

here=pathlib.Path(__file__).resolve().parent
for filename in ('bridge-switch-live.py','flydigi-live-bridge-bench.py'):
    path=here/filename
    spec=importlib.util.spec_from_file_location('offline_entry',path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    check(filename+' import leaves backend unloaded',mod.owner is None and mod.safe is None)
    with patch.object(sys,'platform','darwin'):
        try:mod.load_hardware()
        except RuntimeError as exc:check(filename+' direct backend fails clearly','Windows' in str(exc))
        else:raise AssertionError('backend accepted Mac')
    for platform in ('darwin','win32'):
        with patch.object(sys,'platform',platform),patch.object(sys,'argv',[str(path),'--help']),contextlib.redirect_stdout(io.StringIO()) as output:
            try:runpy.run_path(str(path),run_name='__main__')
            except SystemExit as exc:check(filename+' help '+platform,exc.code==0 and '--child' in output.getvalue())
            else:raise AssertionError('help did not exit')
    for args in ([],['--child','missing-backup','missing-report']):
        with patch.object(sys,'platform','darwin'),patch.object(sys,'argv',[str(path)]+args),contextlib.redirect_stderr(io.StringIO()) as output:
            try:runpy.run_path(str(path),run_name='__main__')
            except SystemExit as exc:check(filename+' Mac gate '+repr(args),exc.code==2 and 'Windows hardware backend' in output.getvalue())
            else:raise AssertionError('Mac entry accepted')
print(json.dumps(checks))
