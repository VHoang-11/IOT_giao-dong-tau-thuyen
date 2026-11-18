#!/usr/bin/env python3
"""Đối chiếu CRC cấu hình của THIẾT BỊ (C++) với bản của BACKEND (Python, backend/commands/config_service.compute_crc).

Backend: CRC-16/CCITT-FALSE trên json.dumps(payload bỏ crc, sort_keys=True, separators=(",", ":")).
Thiết bị phải tái dựng đúng chuỗi byte đó từ JSON nhận được. Script sinh vector cố định + hàng nghìn payload ngẫu nhiên
(số thực mọi cỡ, số nguyên, chuỗi Unicode/ký tự điều khiển, bool, null, khóa lộn xộn) và so từng CRC.
Chạy: python tests/firmware/tools/crosscheck_crc.py   (mã thoát 0 = khớp 100%)
"""
import binascii
import glob
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def backend_crc(payload):
    body = {k: v for k, v in payload.items() if k != "crc"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return "%04x" % binascii.crc_hqx(canon, 0xFFFF)


def build(tmp):
    gcc, gpp = shutil.which("gcc"), shutil.which("g++")
    aj = glob.glob(os.path.join(ROOT, "tests", "firmware", ".pio", "libdeps", "*", "ArduinoJson", "src"))
    if not (gcc and gpp and aj):
        sys.exit("Cần gcc/g++ và ArduinoJson (chạy `pio test -e native` một lần)")
    inc = ["-I", os.path.join(ROOT, "core", "include"), "-I", aj[0], "-I", os.path.join(ROOT, "firmware", "lib", "svmg_msg", "src")]
    objs = []
    for src in sorted(glob.glob(os.path.join(ROOT, "core", "src", "*.c"))):
        o = os.path.join(tmp, os.path.basename(src) + ".o")
        subprocess.run([gcc, "-std=c99", "-O1", *inc, "-c", src, "-o", o], check=True)
        objs.append(o)
    exe = os.path.join(tmp, "crc_tool.exe")
    subprocess.run([gpp, "-std=c++17", "-O1", *inc, os.path.join(ROOT, "tests", "firmware", "tools", "crc_tool.cpp"),
                    os.path.join(ROOT, "firmware", "lib", "svmg_msg", "src", "msg.cpp"), *objs, "-lm", "-o", exe], check=True)
    return exe


def rand_value(rng):
    k = rng.randrange(8)
    if k == 0:
        return rng.randrange(-10**9, 10**9)
    if k == 1:
        return rng.choice([20.0, 15.0, 25.0, 0.5, 18.5, 22.25, 100.0, 1e15, 1e16, 1.5e-5, 0.0001, 123456789.125, 2.5e20])
    if k == 2:
        return float("%.*g" % (rng.randrange(1, 16), rng.uniform(-1e6, 1e6)))            # <= 15 chữ số có nghĩa
    if k == 3:
        return float("%.*g" % (rng.randrange(1, 16), rng.uniform(0, 1) * 10 ** rng.randrange(-8, 18)))
    if k == 4:
        return "".join(rng.choice(['a', 'Z', '_', '"', '\\', '\n', '\t', '/', 'é', 'ệ', '€', '😀', '\x01', ' ']) for _ in range(rng.randrange(0, 12)))
    if k == 5:
        return rng.choice([True, False, None])
    if k == 6:
        return rng.choice(["RF", "BASELINE_B", "SENSITIVE", "STANDARD", "CONSERVATIVE"])
    return rng.randrange(0, 4000)


def main():
    fixed = [
        {"config_version": 8, "profile": "SENSITIVE", "debounce_n": 2, "phi_hard_deg": 20, "mai_caution": 70, "report_interval_s": 5, "primary_model": "RF"},
        {"config_version": 8, "profile": "SENSITIVE", "debounce_n": 2, "phi_hard_deg": 20.0, "mai_caution": 70, "report_interval_s": 5, "primary_model": "RF"},
        {"config_version": 9, "profile": "STANDARD"},
        {"profile": "SENSITIVE", "config_version": 3, "phi_hard_deg": 17.5},
    ]
    expected_known = {0: "4fa6", 1: "0902"}   # đã tính độc lập khi lập kế hoạch
    rng = random.Random(20261117)
    cases = list(fixed)
    for _ in range(4000):
        d = {"config_version": rng.randrange(1, 10**6), "profile": rng.choice(["SENSITIVE", "STANDARD", "CONSERVATIVE"])}
        for _k in range(rng.randrange(0, 8)):
            d["k%d_%s" % (rng.randrange(100), rng.choice("abzXY"))] = rand_value(rng)
        if rng.random() < 0.3:
            d["crc"] = "ffff"        # trường crc phải bị bỏ qua
        cases.append(d)
    with tempfile.TemporaryDirectory() as tmp:
        exe = build(tmp)
        stdin = "\n".join(json.dumps(c) for c in cases) + "\n"
        out = subprocess.run([exe], input=stdin, capture_output=True, text=True, encoding="utf-8").stdout.split()
    assert len(out) == len(cases), (len(out), len(cases))
    bad = 0
    for i, (c, got) in enumerate(zip(cases, out)):
        want = backend_crc(c)
        if got != want:
            bad += 1
            if bad <= 5:
                print("LỆCH #%d: thiết bị=%s backend=%s  %s" % (i, got, want, json.dumps(c, ensure_ascii=False)[:160]))
    # Số thực 16-17 chữ số có nghĩa: thiết bị dùng strtod trên token gốc nên phải khớp tuyệt đối (ArduinoJson thì KHÔNG: lệch 1 ulp).
    longs = [{"config_version": 5, "a": rng.uniform(0, 1e6), "b": 0.1 + 0.2, "c": 1 / 3.0} for _ in range(300)]
    with tempfile.TemporaryDirectory() as tmp2:
        exe2 = build(tmp2)
        payload2 = "\n".join(json.dumps(c) for c in longs) + "\n"
        out2 = subprocess.run([exe2], input=payload2, capture_output=True, text=True, encoding="utf-8").stdout.split()
    long_bad = sum(1 for c, g in zip(longs, out2) if g != backend_crc(c))
    print("số thực 16-17 chữ số: %d/%d khớp" % (len(longs) - long_bad, len(longs)))
    bad += long_bad
    for i, v in expected_known.items():
        assert backend_crc(fixed[i]) == v and out[i] == v, ("vector vàng", i, out[i], v)
    print("CRC thiết bị khớp backend: %d/%d payload (gồm vector vàng 4fa6/0902)" % (len(cases) - bad, len(cases)))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
