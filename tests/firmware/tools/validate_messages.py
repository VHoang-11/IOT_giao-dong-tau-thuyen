#!/usr/bin/env python3
"""Kiểm bản tin MQTT của thiết bị với contracts/schemas bằng jsonschema (Draft 7, giống backend/ingest/validator.py).

Biên dịch lõi C + thư viện bản tin + chương trình tools/emit_messages.cpp (chạy ENGINE THẬT qua các kịch bản: khởi động nguội với
ngưỡng cứng, vòng đời cảnh báo S1 có ACK, leo thang, lỗi cảm biến, nghiêng lệch kéo dài), chạy, rồi kiểm từng bản tin. Thêm:
  * vòng đời event: alarm_id nhất quán, prev_level liền mạch, seq tăng dần, có ACK mang acked_by, kết thúc bằng CLEARED;
  * topic thiết bị ghi/đọc nằm trong ACL infra/mosquitto/acl.
Chạy:  python tests/firmware/tools/validate_messages.py        (mã thoát 0 = đạt)
Yêu cầu: gcc/g++ trong PATH, pip install jsonschema, và đã chạy `pio test -e native` một lần (để có ArduinoJson trong .pio/libdeps).
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

from jsonschema import Draft7Validator

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCHEMAS = os.path.join(ROOT, "contracts", "schemas")


def find_arduinojson():
    hits = glob.glob(os.path.join(ROOT, "tests", "firmware", ".pio", "libdeps", "*", "ArduinoJson", "src"))
    if not hits:
        sys.exit("Không thấy ArduinoJson: chạy `cd tests/firmware && pio test -e native` một lần trước.")
    return hits[0]


def build(tmp):
    gcc, gpp = shutil.which("gcc"), shutil.which("g++")
    if not gcc or not gpp:
        sys.exit("Cần gcc/g++ trong PATH")
    inc = ["-I", os.path.join(ROOT, "core", "include"), "-I", find_arduinojson(),
           "-I", os.path.join(ROOT, "firmware", "lib", "svmg_msg", "src"),
           "-I", os.path.join(ROOT, "tests", "firmware", "lib", "svmg_testutil")]
    objs = []
    for src in sorted(glob.glob(os.path.join(ROOT, "core", "src", "*.c"))):
        o = os.path.join(tmp, os.path.basename(src) + ".o")
        subprocess.run([gcc, "-std=c99", "-O1", *inc, "-c", src, "-o", o], check=True)
        objs.append(o)
    mo = os.path.join(tmp, "msg.o")
    subprocess.run([gpp, "-std=c++17", "-O1", *inc, "-c", os.path.join(ROOT, "firmware", "lib", "svmg_msg", "src", "msg.cpp"), "-o", mo], check=True)
    exe = os.path.join(tmp, "emit.exe")
    subprocess.run([gpp, "-std=c++17", "-O1", *inc, os.path.join(ROOT, "tests", "firmware", "tools", "emit_messages.cpp"), mo, *objs, "-lm", "-o", exe], check=True)
    return exe


def acl_topics():
    allow = {"write": set(), "read": set()}
    user = None
    for line in open(os.path.join(ROOT, "infra", "mosquitto", "acl"), encoding="utf-8"):
        t = line.split()
        if len(t) >= 2 and t[0] == "user":
            user = t[1]
        elif user == "vessel-demo-01" and len(t) == 3 and t[0] == "topic":
            allow[t[1]].add(t[2].replace("svmg/vessel-demo-01/", ""))
    return allow


def main():
    with tempfile.TemporaryDirectory() as tmp:
        exe = build(tmp)
        out = subprocess.run([exe], capture_output=True, text=True, encoding="utf-8").stdout
    validators = {}
    ok = bad = 0
    events, pub, sub = [], [], []
    for line in out.splitlines():
        kind, name, js = (line.split("\t", 2) + ["", ""])[:3]
        if kind.startswith("INVALID_"):
            bad += 1
            print("FAIL  thiết bị không dựng được bản tin:", kind, name)
            continue
        if kind == "TOPIC_PUB":
            pub.append(name); continue
        if kind == "TOPIC_SUB":
            sub.append(name); continue
        if kind not in validators:
            sch = json.load(open(os.path.join(SCHEMAS, kind + ".json"), encoding="utf-8"))
            Draft7Validator.check_schema(sch)
            validators[kind] = Draft7Validator(sch)
        msg = json.loads(js)
        errs = sorted(validators[kind].iter_errors(msg), key=lambda e: list(e.path))
        if errs:
            bad += 1
            print("FAIL  %-11s %s" % (kind, name))
            for e in errs[:3]:
                print("        - %s: %s" % (".".join(map(str, e.path)) or "(gốc)", e.message[:120]))
        else:
            ok += 1
            if kind == "event":
                events.append(msg)

    # ---- vòng đời event
    problems = []
    per_boot = {}
    for e in events:
        per_boot.setdefault(e["boot_id"], []).append(e["seq"])        # seq chỉ có nghĩa trong một lần boot
    for boot, seqs in per_boot.items():
        if seqs != sorted(seqs) or len(set(seqs)) != len(seqs):
            problems.append("boot %s: seq của event không tăng nghiêm ngặt" % boot)
    by_alarm = {}
    for e in events:
        by_alarm.setdefault((e["boot_id"], e["alarm_id"]), []).append(e)
    for key, chain in by_alarm.items():
        lvl = "NORMAL"
        for e in chain:
            if e["prev_level"] != lvl:
                problems.append("alarm %s: prev_level=%s nhưng mức trước là %s" % (key[1], e["prev_level"], lvl)); break
            lvl = e["level"]
    cleared = [k for k, c in by_alarm.items() if c[-1]["level"] == "NORMAL"]
    acked = [k for k, c in by_alarm.items() if any(e.get("acked_by") for e in c)]
    if not cleared:
        problems.append("không có alarm nào kết thúc bằng CLEARED (level=NORMAL)")
    if not acked:
        problems.append("không có sự kiện ACK mang acked_by")
    if not any(e["level"] == "CRITICAL" for e in events):
        problems.append("không có sự kiện CRITICAL (kịch bản leo thang/ngưỡng cứng)")
    # ---- ACL
    allow = acl_topics()
    for t in pub:
        if t not in allow["write"]:
            problems.append("ACL không cho thiết bị ghi topic '%s'" % t)
    for t in sub:
        if t not in allow["read"]:
            problems.append("ACL không cho thiết bị đọc topic '%s'" % t)
    for p in problems:
        print("FAIL  ", p)
    print("\nBản tin hợp lệ: %d | vi phạm: %d | event: %d (alarm: %d, CLEARED: %d, có ACK: %d) | vấn đề vòng đời/ACL: %d" % (
        ok, bad, len(events), len(by_alarm), len(cleared), len(acked), len(problems)))
    sys.exit(1 if (bad or problems) else 0)


if __name__ == "__main__":
    main()
