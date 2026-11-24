"""M2-R7: biên dịch firmware/src/infer.cpp THẬT với model.h đóng băng trên máy host; so infer_predict với sklearn + tau trên
Validation/S0b (không dùng Test-G1); UNKNOWN khi conf < tau hoặc đầu vào lỗi, không bao giờ thành NORMAL."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from ml.export import prepare_firmware_model_m2r7 as P
from ml.export import rf4_freeze_m2r6b as F
from ml.train import rf_four_class_m2r6 as R
from ml.train.g1_simulation_dataset import ROOT

UNKNOWN = 4
PROBE = r"""#include "infer.h"
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
extern "C" void svmg_engine_set_rf(svmg_engine_t *e, svmg_rf_fn f, void *c) { e->rf = f; e->rf_ctx = c; }
int main() {
  svmg_engine_t e = {}; infer_begin(&e);
  printf("%s %s %d\n", infer_model_status(), infer_model_version(), e.rf != nullptr);
  char line[8192];
  while (fgets(line, sizeof line, stdin)) {
    float x[64]; int n = 0; char *c = line, *end;
    while (*c && *c != '\n' && n < 64) { x[n++] = strtof(c, &end); c = (*end == ',') ? end + 1 : end; }
    printf("%d\n", (int)infer_predict(nullptr, x, n));
  }
  return 0;
}
"""


@pytest.mark.skipif(shutil.which("g++") is None or not (F.MODEL_DIR / "model.joblib").exists(), reason="cần g++ và mô hình M2-R6a cục bộ")
def test_real_infer_cpp_with_frozen_header_matches_python(tmp_path):
    header = P.prepare(tmp_path / "model")
    (tmp_path / "Arduino.h").write_text("#pragma once\n#include <stdint.h>\ninline uint32_t micros(){static uint32_t t=0;return ++t;}\n")
    (tmp_path / "probe.cpp").write_text(PROBE)
    exe = tmp_path / "probe"
    subprocess.run([shutil.which("g++"), "-std=gnu++17", "-O2", "-Wall", "-Werror", "-I", str(tmp_path), "-I", str(header.parent),
                    "-I", str(ROOT / "core/include"), "-I", str(ROOT / "firmware/src"), str(ROOT / "firmware/src/infer.cpp"),
                    str(tmp_path / "probe.cpp"), "-o", str(exe)], check=True)
    frame = R.load(R.DATASETS["v0.3"][0])                     # chỉ Train/Validation; Test-G1 bị loại khi đọc
    data = frame.loc[frame.split.eq(R.VAL) | frame.subset.eq("CHALLENGE_S0B")]
    X = R.matrix(data)
    model, _ = F.load_frozen()
    proba = model.predict_proba(X)
    expected = np.where(proba.max(1).astype(np.float32) < np.float32(0.5), UNKNOWN, proba.argmax(1))
    bad = [X[0, :22], np.where(np.arange(23) == 3, np.nan, X[0]), np.where(np.arange(23) == 20, np.inf, X[0])]
    rows = [",".join(float(np.float32(v)).hex() for v in row) for row in [*X, *bad]]
    out = subprocess.run([str(exe)], input="\n".join(rows) + "\n", capture_output=True, text=True, check=True).stdout.split("\n")
    assert out[0] == f"AVAILABLE {R.MODEL_VERSION} 1"
    got = np.array([int(v) for v in out[1:1 + len(rows)]])
    assert np.array_equal(got[:len(X)], expected) and set(expected) == {0, 1, 2, 3, UNKNOWN}
    assert got[len(X):].tolist() == [UNKNOWN] * len(bad)
