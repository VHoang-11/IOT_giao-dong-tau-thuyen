"""Compare production CF + causal Butterworth4 4 Hz / 20->10 Hz to SciPy."""
import ctypes as ct
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import numpy as np
from scipy.signal import butter, sosfilt, sosfilt_zi

ROOT=Path(__file__).resolve().parents[3]
FP=ct.POINTER(ct.c_float)
def main():
    with tempfile.TemporaryDirectory(prefix='svmg-filter-',ignore_cleanup_errors=True) as tmp:
        dll=Path(tmp)/'filter.dll'
        subprocess.run([shutil.which('gcc'),'-std=c99','-O1','-shared','-I',str(ROOT/'core/include'),
            str(ROOT/'core/src/filter.c'),str(ROOT/'tests/firmware/tools/filter_parity.c'),'-lm','-o',str(dll)],check=True)
        lib=ct.CDLL(str(dll));fn=lib.check_pipeline
        fn.argtypes=[FP,FP,FP,FP,ct.c_int,FP,FP];fn.restype=ct.c_int
        t=np.arange(8000)/20
        r=np.asarray(.1+.15*np.sin(.3*t)+.02*np.sin(2*np.pi*3*t),dtype=np.float32)
        p=np.asarray(-.03+.08*np.cos(.5*t),dtype=np.float32)
        gx=np.asarray(.045*np.cos(.3*t)+.12*np.pi*np.cos(2*np.pi*3*t),dtype=np.float32)
        gy=np.asarray(-.04*np.sin(.5*t),dtype=np.float32)
        ro=np.empty(4000,dtype=np.float32);po=np.empty_like(ro)
        n=fn(*(a.ctypes.data_as(FP) for a in (r,p,gx,gy)),len(t),ro.ctypes.data_as(FP),po.ctypes.data_as(FP))
        assert n==4000
        # Reproduce physical sample times passed through float32 (as on ESP32).
        ts=np.asarray(t,dtype=np.float32).astype(float)
        expected=[]
        for angles,rates in ((r,gx),(p,gy)):
            cf=np.empty(len(t));cf[0]=angles[0]
            for i in range(1,len(t)):
                dt=ts[i]-ts[i-1];alpha=7.5/(7.5+dt)
                cf[i]=alpha*(cf[i-1]+float(rates[i])*dt)+(1-alpha)*float(angles[i])
            sos=butter(4,4,fs=20,output='sos')
            filtered,_=sosfilt(sos,cf,zi=sosfilt_zi(sos)*cf[0])
            expected.append(filtered[1::2])
        for actual,reference in zip((ro,po),expected):np.testing.assert_allclose(actual,reference,atol=1e-5,rtol=2e-5)
        error=max(float(np.max(np.abs(a-b))) for a,b in zip((ro,po),expected))
        if sys.platform=='win32':
            import _ctypes
            _ctypes.FreeLibrary(lib._handle)
    print(json.dumps({'samples_compared':8000,'maximum_error_rad':error,'result':'PASS'}))
if __name__=='__main__':main()
