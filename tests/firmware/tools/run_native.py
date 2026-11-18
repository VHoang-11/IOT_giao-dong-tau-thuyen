"""Build and run native Unity suites with GCC; no PlatformIO installation required.
Uses the same Unity/ArduinoJson dependencies as tests/firmware/platformio.ini.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[3]
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--suite',action='append')
    args=parser.parse_args()
    inc=[]
    for p in ('core/include','tests/firmware/.pio/libdeps/native/Unity/src','tests/firmware/lib/svmg_testutil','firmware/lib/svmg_msg/src','tests/firmware/.pio/libdeps/native/ArduinoJson/src'):
        inc+=['-I',str(ROOT/p)]
    cc=shutil.which('gcc');cpp=shutil.which('g++')
    if not cc or not cpp: raise SystemExit('GCC and G++ required in PATH')
    failed=[];totals=[]
    with tempfile.TemporaryDirectory(prefix='svmg-native-') as tmp:
        objects=[]
        for source in [*sorted((ROOT/'core/src').glob('*.c')),ROOT/'tests/firmware/.pio/libdeps/native/Unity/src/unity.c']:
            obj=str(Path(tmp)/(source.name+'.o'))
            subprocess.run([cc,'-std=c99','-O1','-Wall','-Wextra','-fstack-usage',*inc,'-c',str(source),'-o',obj],check=True)
            objects.append(obj)
        for suite in sorted((ROOT/'tests/firmware/test').iterdir()):
            if not suite.is_dir() or (args.suite and suite.name not in args.suite):continue
            sources=[*suite.glob('*.c'),*suite.glob('*.cpp')]
            exe=str(Path(tmp)/(suite.name+'.exe'))
            is_cpp=any(s.suffix=='.cpp' for s in sources)
            cmd=[cpp if is_cpp else cc,'-std=c++17' if is_cpp else '-std=c99','-O1','-Wall','-Wextra',*inc,*map(str,sources)]
            if is_cpp:cmd+=[str(ROOT/'firmware/lib/svmg_msg/src/msg.cpp')]
            subprocess.run([*cmd,*objects,'-lm','-o',exe],check=True)
            result=subprocess.run([exe],cwd=ROOT/'tests/firmware',capture_output=True,text=True,encoding='utf-8',errors='replace')
            print(suite.name,flush=True)
            for line in result.stdout.splitlines():
                if ':FAIL' in line or 'Tests ' in line or ':INFO:' in line:print(line,flush=True)
                if 'Tests ' in line:totals.append(int(line.split()[0]))
            if result.returncode:failed.append(suite.name)
        stack=[]
        for p in Path(tmp).glob('*.su'):
            for line in p.read_text().splitlines():
                parts=line.split('\t')
                if len(parts)>1:stack.append((int(parts[1]),parts[0]))
        if stack:
            print('Host convenience stack frame:',max(stack),flush=True)
            runtime=[item for item in stack if 'svmg_features_from_series' not in item[1] and 'Unity' not in item[1]]
            print('Largest runtime core frame:',max(runtime),flush=True)
    print('TOTAL',sum(totals),'tests; failed suites:',failed,flush=True)
    raise SystemExit(bool(failed))
if __name__=='__main__':main()
