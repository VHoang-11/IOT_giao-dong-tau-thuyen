"""Compile the real RF adapter against controlled artifacts; no real model is fabricated."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[3]

def main():
    cases={
        'valid':(23,'svmg-angle-23-v1','imu-cf-bw4-20to10-v1',True,'AVAILABLE',False,True,True),
        'old_14':(14,'svmg-angle-23-v1','imu-cf-bw4-20to10-v1',False,'FEATURE_COUNT_MISMATCH',False,True,True),
        'wrong_schema':(23,'old-schema','imu-cf-bw4-20to10-v1',False,'FEATURE_SCHEMA_MISMATCH',False,False,True),
        'wrong_preprocessing':(23,'svmg-angle-23-v1','old-filter',False,'PREPROCESSING_MISMATCH',False,True,False),
        'missing_metadata':(0,'','',False,'FEATURE_COUNT_MISMATCH',False,False,False),
        'no_model':(0,'','',False,'STUB',True,False,False),
    }
    with tempfile.TemporaryDirectory(prefix='svmg-model-') as tmp:
        tmp=Path(tmp)
        (tmp/'Arduino.h').write_text('#pragma once\n#include <stdint.h>\ninline uint32_t micros(){static uint32_t t=0;return ++t;}\n')
        (tmp/'probe.cpp').write_text('''#include "infer.h"
#include <math.h>
#include <string.h>
extern "C" void svmg_engine_set_rf(svmg_engine_t *e,svmg_rf_fn f,void *c){e->rf=f;e->rf_ctx=c;}
int main(){
  svmg_engine_t e={};infer_begin(&e);
  if(infer_available()!=bool(EXPECT_AVAILABLE)||bool(e.rf)!=bool(EXPECT_AVAILABLE))return 1;
  if(strcmp(infer_model_status(),EXPECT_STATUS))return 5;
  if(infer_model_is_stub()!=bool(EXPECT_STUB)||infer_model_feature_count()!=EXPECT_FEATURE_COUNT)return 6;
  if(infer_model_schema_compatible()!=bool(EXPECT_SCHEMA_OK)||infer_model_preprocessing_compatible()!=bool(EXPECT_PREPROCESSING_OK))return 7;
  float x[23]={};
  if(infer_predict(nullptr,x,14)!=SVMG_UNKNOWN)return 2;
  x[3]=NAN;if(infer_predict(nullptr,x,23)!=SVMG_UNKNOWN)return 3;
  x[3]=0;if(infer_predict(nullptr,x,23)!=(EXPECT_AVAILABLE?SVMG_HIGH_ROLL:SVMG_UNKNOWN))return 4;
  return 0;
}
''')
        for name,(n,schema,pre,available,status,is_stub,schema_ok,preprocessing_ok) in cases.items():
            model=tmp/'model.h'
            if name=='no_model':
                model.unlink()
            else:
                model.write_text(f'''#define SVMG_MODEL_N_FEATURES {n}
#define SVMG_MODEL_FEATURE_SCHEMA_VERSION "{schema}"
#define SVMG_MODEL_PREPROCESSING_VERSION "{pre}"
#define SVMG_MODEL_VERSION "test_fixture"
inline int model_predict(const float*,int){{return 1;}}
''')
            exe=tmp/'probe.exe'
            subprocess.run([shutil.which('g++'),'-std=c++17','-O1',f'-DEXPECT_AVAILABLE={int(available)}',f'-DEXPECT_STATUS="{status}"',
                f'-DEXPECT_STUB={int(is_stub)}',f'-DEXPECT_FEATURE_COUNT={n}',f'-DEXPECT_SCHEMA_OK={int(schema_ok)}',
                f'-DEXPECT_PREPROCESSING_OK={int(preprocessing_ok)}',
                '-I',str(tmp),'-I',str(ROOT/'core/include'),'-I',str(ROOT/'firmware/src'),'-I',str(ROOT/'firmware/stubs'),
                str(ROOT/'firmware/src/infer.cpp'),str(tmp/'probe.cpp'),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)
    print(json.dumps({'artifact_cases':len(cases),'result':'PASS'}))
if __name__=='__main__':main()
