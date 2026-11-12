$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$out = Join-Path $PSScriptRoot 'build'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$gcc = 'C:/Strawberry/c/bin/gcc.exe'
$gpp = 'C:/Strawberry/c/bin/g++.exe'
$unity = Join-Path $repo 'tests/firmware/.pio/libdeps/native/Unity/src'
$json = Join-Path $repo 'tests/firmware/.pio/libdeps/native/ArduinoJson/src'
$inc = @('-I', (Join-Path $repo 'core/include'), '-I', $unity, '-I', $json,
         '-I', (Join-Path $repo 'firmware/lib/svmg_msg/src'),
         '-I', (Join-Path $repo 'tests/firmware/lib/svmg_testutil'))
$objects = @()
foreach ($src in Get-ChildItem (Join-Path $repo 'core/src') -Filter '*.c') {
    $obj = Join-Path $out ($src.BaseName + '.o')
    & $gcc -std=c99 -Wall -Wextra -O1 @inc -c $src.FullName -o $obj
    if ($LASTEXITCODE -ne 0) { throw "Compile failed: $($src.Name)" }
    $objects += $obj
}
$unityObj = Join-Path $out 'unity.o'
& $gcc -O1 @inc -c (Join-Path $unity 'unity.c') -o $unityObj
if ($LASTEXITCODE -ne 0) { throw 'Unity compile failed' }
$msgObj = Join-Path $out 'msg.o'
& $gpp -std=c++17 -Wall -Wextra -O1 @inc -c (Join-Path $repo 'firmware/lib/svmg_msg/src/msg.cpp') -o $msgObj
if ($LASTEXITCODE -ne 0) { throw 'Message compile failed' }
$summary = @()
foreach ($suite in Get-ChildItem (Join-Path $repo 'tests/firmware/test') -Directory) {
    $src = @(Get-ChildItem $suite.FullName -File | Where-Object { $_.Extension -in '.c', '.cpp' })
    $testObj = Join-Path $out ($suite.Name + '.o')
    $compiler = if ($src[0].Extension -eq '.cpp') { $gpp } else { $gcc }
    & $compiler -Wall -Wextra -O1 @inc -c $src[0].FullName -o $testObj
    if ($LASTEXITCODE -ne 0) { throw "Test compile failed: $($suite.Name)" }
    $exe = Join-Path $out ($suite.Name + '.exe')
    & $gpp $testObj @objects $unityObj $msgObj -lm -o $exe
    if ($LASTEXITCODE -ne 0) { throw "Link failed: $($suite.Name)" }
    $lines = @(& $exe)
    $code = $LASTEXITCODE
    $lines | Set-Content -Encoding UTF8 (Join-Path $out ($suite.Name + '.log'))
    $result = $lines | Where-Object { $_ -match '\d+ Tests \d+ Failures' }
    $summary += "$($suite.Name): $result; exit=$code"
    if ($code -ne 0) { throw "Suite failed: $($suite.Name)" }
}
$probe = Join-Path $out 'review_probe.exe'
& $gpp -std=c++17 -O1 @inc (Join-Path $PSScriptRoot 'review_probe.cpp') @objects $msgObj -lm -o $probe
if ($LASTEXITCODE -ne 0) { throw 'Probe compile failed' }
$probeLines = @(& $probe)
$probeLines | Set-Content -Encoding UTF8 (Join-Path $out 'review_probe.log')
$summary | Set-Content -Encoding UTF8 (Join-Path $out 'summary.log')
$summary
$probeLines
