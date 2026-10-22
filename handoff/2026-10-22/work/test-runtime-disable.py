import importlib.util
import pathlib

spec=importlib.util.spec_from_file_location('safe',pathlib.Path(__file__).with_name('flydigi-safe-waveform.py'))
safe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(safe)
class Reader:
    def __init__(self,failures):self.failures=list(failures);self.calls=[]
    def mode(self,payload):
        self.calls.append(payload)
        if self.failures:
            error=self.failures.pop(0)
            if error:raise error

def run():
    no_sleep=lambda _:None
    r=Reader([])
    assert safe.disable_runtime(r,sleep=no_sleep)==[dict(attempt=1,status='ACK_OK')]
    r=Reader([TimeoutError('lost ACK'),None])
    assert safe.disable_runtime(r,sleep=no_sleep)[-1]==dict(attempt=2,status='ACK_OK')
    assert r.calls==[b'\x01\x12\x00']*2
    r=Reader([TimeoutError('1'),TimeoutError('2'),TimeoutError('3')])
    try:safe.disable_runtime(r,sleep=no_sleep)
    except RuntimeError:pass
    else:raise AssertionError('Unbounded/hidden shutdown failure')
    assert len(r.calls)==3
    r=Reader([ValueError('explicit device rejection')])
    try:safe.disable_runtime(r,sleep=no_sleep)
    except ValueError:pass
    else:raise AssertionError('Explicit rejection ignored')
    assert len(r.calls)==1
    print('4 shutdown policy checks passed; no devices opened')
if __name__=='__main__':run()
