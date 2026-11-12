#!/usr/bin/env python3
"""Sinh include/baseline_params.h từ baseline_params.json do M2 xuất (M2-05) - M1-04.

Định dạng JSON (ĐỀ XUẤT, cần M2 xác nhận trong contracts):
{
  "baseline_b": {"hi_rms_deg": 6.0, "off_mean_deg": 2.5, "off_same_sign": 0.85,
                 "grow_trend": 1.0, "grow_ratio": 1.5, "grow_min_rms": 1.5},
  "mai":        {"a_ref_deg": 8.0, "b_ref_deg": 5.0, "g_ref_deg_per_min": 2.0},
  "generator_version": "...", "data_hash": "..."
}
Chạy: python tools/gen_baseline_header.py ../ml/baselines/baseline_params.json include/baseline_params.h
"""
import json
import sys

B_KEYS = ["hi_rms_deg", "off_mean_deg", "off_same_sign", "grow_trend", "grow_ratio", "grow_min_rms"]
M_KEYS = ["a_ref_deg", "b_ref_deg", "g_ref_deg_per_min"]


def main(src, dst):
    d = json.load(open(src, encoding="utf-8"))
    for grp, keys in (("baseline_b", B_KEYS), ("mai", M_KEYS)):
        if grp not in d:
            sys.exit("thieu nhom '%s' trong %s" % (grp, src))
        for k in keys:
            v = d[grp].get(k)
            if not isinstance(v, (int, float)) or v != v or v <= 0:
                sys.exit("gia tri '%s.%s' khong hop le: %r" % (grp, k, v))
    f = lambda v: repr(float(v)) + "f"
    out = ["// SINH TU DONG boi tools/gen_baseline_header.py - KHONG SUA TAY.",
           "// Nguon: %s | generator_version=%s | data_hash=%s" % (src, d.get("generator_version", "?"), d.get("data_hash", "?")),
           "#pragma once", "#include \"svmg_decision.h\"",
           "static const svmg_baseline_params_t SVMG_BASELINE_B_PARAMS = { " + ", ".join(f(d["baseline_b"][k]) for k in B_KEYS) + " };",
           "static const svmg_mai_params_t SVMG_MAI_PARAMS = { " + ", ".join(f(d["mai"][k]) for k in M_KEYS) + " };", ""]
    open(dst, "w", encoding="utf-8").write("\n".join(out))
    print("da ghi", dst)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
