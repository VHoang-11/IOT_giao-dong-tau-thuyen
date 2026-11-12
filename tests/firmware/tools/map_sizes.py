#!/usr/bin/env python3
"""Tổng hợp dung lượng flash/RAM theo thành phần từ file .map sau khi link (đã loại bỏ code thừa).

Chạy:  python tests/firmware/tools/map_sizes.py firmware/.pio/build/esp32dev/firmware.map
Dùng cho bảng tài nguyên M1-08 và quyết định thư viện M1-06.
"""
import collections
import re
import sys

SEC_OK = ('.text', '.rodata', '.data', '.bss', '.literal', '.iram', '.flash', '.dram', '.noinit')


def classify(obj):
    o = obj.replace(chr(92), '/')
    if 'libsvmg_msg.a' in o:
        return 'msg.cpp (tao JSON + ArduinoJson parse)'
    if 'libcore.a' in o:
        return 'core/ (loi C cua M1)'
    if 'stubs' in o:
        return 'stubs (mock sim)'
    if re.search(r'(^|/)src/[^/]+\.cpp\.o$', o):
        return 'firmware/src (app, net, io, lcd, ...)'
    if 'mqtt' in o.lower():
        return 'esp-mqtt (IDF)'
    if re.search(r'WiFi|Network|libnet80211|libwpa|liblwip|libphy|libesp_wifi|libpp\.a|libmbedtls|libmbedcrypto|libesp_netif|libesp-tls', o):
        return 'WiFi / TCP-IP / TLS (IDF)'
    return 'framework + khac'


def main(path):
    txt = open(path, encoding='utf-8', errors='ignore').read()
    lines = txt[txt.index('Linker script and memory map'):].splitlines()
    full = re.compile(r'^\s+(\.\S+)\s+0x[0-9a-f]+\s+0x([0-9a-f]+)\s+(.+)$')
    name = re.compile(r'^\s+(\.\S+)$')
    cont = re.compile(r'^\s+0x[0-9a-f]+\s+0x([0-9a-f]+)\s+(.+)$')
    tot = collections.Counter()
    i = 0
    while i < len(lines):
        m = full.match(lines[i])
        if m:
            sec, sz, obj = m.group(1), int(m.group(2), 16), m.group(3)
        else:
            m2 = name.match(lines[i])
            c = cont.match(lines[i + 1]) if (m2 and i + 1 < len(lines)) else None
            if not c:
                i += 1
                continue
            sec, sz, obj = m2.group(1), int(c.group(1), 16), c.group(2)
            i += 1
        i += 1
        if sz and sec.startswith(SEC_OK):
            kind = 'ram' if sec.startswith(('.bss', '.data', '.dram', '.noinit')) else 'flash'
            tot[(classify(obj), kind)] += sz
    for (k, kind), v in sorted(tot.items(), key=lambda kv: -kv[1]):
        print('%-42s %-5s %9d B' % (k, kind, v))


if __name__ == '__main__':
    main(sys.argv[1])
