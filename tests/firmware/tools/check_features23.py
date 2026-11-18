"""Compare ESP32 C features against the actual M2 Python extractor and SciPy filter.
Run from any directory: python tests/firmware/tools/check_features23.py
Requirements: numpy pandas scipy PyYAML (ML environment), GCC, G++.
"""
import ctypes as ct
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import numpy as np
import pandas as pd
import yaml
from scipy.signal import butter,sosfilt,sosfilt_zi
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from ml.features.extractor import extract_segment
from ml.features.spec import PRACTICAL_SUBSETS
NAMES=PRACTICAL_SUBSETS['angle_only_23_without_gyro_or_period']
FP=ct.POINTER(ct.c_float)
def main():
    chosen=re.findall(r'^\|\s*\d+\s*\|\s*([a-z][a-z0-9_]+)\s*\|',(ROOT/'ml/docs/M2_23_Features_ESP32_Integration.md').read_text(encoding='utf-8'),re.M)
    assert tuple(chosen)==NAMES and len(NAMES)==23
    manifest=json.loads((ROOT/'contracts/features23.json').read_text(encoding='utf-8'))
    assert tuple(item['name'] for item in manifest['features'])==NAMES
    assert [item['index'] for item in manifest['features']]==list(range(23))
    settings=yaml.safe_load((ROOT/'ml/features/config.yaml').read_text(encoding='utf-8'))['features']
    assert settings['target_sampling_hz']==10 and settings['window_stride_seconds']==10
    assert settings['numeric_zero_epsilon_deg']==1e-9 and settings['r_squared_zero_tolerance']==1e-15
    checked=0
    with tempfile.TemporaryDirectory(prefix='svmg-parity-',ignore_cleanup_errors=True) as tmp:
        dll=Path(tmp)/'features.dll'
        subprocess.run([shutil.which('gcc'),'-std=c99','-O1','-shared','-I',str(ROOT/'core/include'),str(ROOT/'core/src/features.c'),'-lm','-o',str(dll)],check=True)
        lib=ct.CDLL(str(dll));fn=lib.svmg_features_from_series
        fn.argtypes=[FP,FP,ct.c_void_p,ct.c_int,FP];fn.restype=ct.c_int
        cnames=(ct.c_char_p*23).in_dll(lib,'SVMG_FEATURE_NAMES')
        assert tuple(n.decode() for n in cnames)==NAMES
        rng=np.random.default_rng(20261118)
        t=np.arange(1801,dtype=np.float64)/10
        waves=np.sin(2*np.pi*t/17)+.3*np.sin(2*np.pi*t/7)
        cases=[('normal',waves,.4*np.sin(t)),('offset',5+waves,np.cos(t)),('growth',(1+t/30)*waves,np.sin(t/3)),
               ('zero',np.zeros(1801),np.zeros(1801)),('constant',np.full(1801,5.),np.full(1801,-2.)),
               ('ramp',t/10,t/20),('sign_zeros',np.resize([-1.,0.,1.,0.],1801),np.zeros(1801)),
               ('steps',np.where(t<=60,1.,np.where(t<=120,2.,3.)),np.zeros(1801)),
               ('missing_roll',waves.copy(),np.cos(t)),('missing_pitch',waves.copy(),np.cos(t)),
               ('insufficient_block',waves.copy(),np.cos(t))]
        cases[8][1][1300:1308]=np.nan
        cases[9][2][100:108]=np.nan
        cases[10][1][1:33]=np.nan
        for j in range(12):cases.append(('random_%02d'%j,rng.normal(size=1801).cumsum()/10,rng.normal(size=1801)))
        for label,r,p in cases:
            # Both implementations receive exactly the same float32 values.
            r=np.asarray(r,dtype=np.float32);p=np.asarray(p,dtype=np.float32)
            frame=pd.DataFrame(dict(dataset_source='hohai',session_id=label,segment_id='s0',time_seconds=t,
                roll_deg=r.astype(float),pitch_deg=p.astype(float),gyro_x_rad_s=np.nan,gyro_y_rad_s=np.nan))
            values,metadata,_=extract_segment(frame,{'target_sampling_hz_effective':10.0},settings)
            expected=values.iloc[-1][list(NAMES)].to_numpy(dtype=float)
            actual=np.empty(23,dtype=np.float32)
            status=fn(r[1:].ctypes.data_as(FP),p[1:].ctypes.data_as(FP),None,1800,actual.ctypes.data_as(FP))
            for k,name in enumerate(NAMES):
                if np.isnan(expected[k]):assert np.isnan(actual[k]),(label,name,expected[k],actual[k])
                else:assert np.isfinite(actual[k]) and abs(actual[k]-expected[k])<=2e-5+2e-5*abs(expected[k]),(label,name,expected[k],actual[k])
                checked+=1
            if np.isfinite(expected).all():assert status==0,(label,status)
        # No future leakage: calculate prefix before and after changing only the suffix.
        r=np.asarray(waves,dtype=np.float32);p=np.zeros(1801,dtype=np.float32)
        prefix=np.empty(23,dtype=np.float32);fn(r[:1800].ctypes.data_as(FP),p[:1800].ctypes.data_as(FP),None,1800,prefix.ctypes.data_as(FP))
        r[1800]=9999
        repeated=np.empty(23,dtype=np.float32);fn(r[:1800].ctypes.data_as(FP),p[:1800].ctypes.data_as(FP),None,1800,repeated.ctypes.data_as(FP))
        np.testing.assert_equal(prefix,repeated)
        if sys.platform=='win32':
            import _ctypes
            _ctypes.FreeLibrary(lib._handle)
    print(json.dumps({'cases':len(cases),'feature_comparisons':checked,'failures':0,'schema_order':'PASS','future_leakage':'PASS'}))
if __name__=='__main__':main()
