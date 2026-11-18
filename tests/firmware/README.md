# Kiểm thử M1 — 23 đặc trưng

Chạy từ gốc repo, cần GCC/G++ và Unity/ArduinoJson (PlatformIO tải vào `.pio/libdeps/native`):

```bash
python tests/firmware/tools/run_native.py
python tests/firmware/tools/check_features23.py
python tests/firmware/tools/check_filter23.py
python tests/firmware/tools/check_model_adapter.py
python tests/firmware/tools/validate_messages.py
python tests/firmware/tools/crosscheck_crc.py
```

Parity cần numpy/pandas/scipy/PyYAML; kiểm schema cần jsonschema. Dùng cùng môi trường Python của ML.
Có thể chạy Unity bằng `cd tests/firmware` rồi `pio test -e native`.

208 ca Unity: filter 30, FRD 4, feature 13, decision 22, alarm 29, cmd/config 26, evbuf 8, message 31, engine 31,
T01/T05/T07 host 14. Test feature giải tích kiểm RMS/std/Type-7, đơn vị slope, ba đoạn, NaN/zero-denominator,
cadence/cold start, coverage, mất cặp sai phân, ring và workspace. Parity dùng **extractor Python M2 thực tế**
và cùng chuỗi float32, dung sai tuyệt đối/tương đối 2e-5. Bộ lọc đối chiếu SciPy độc lập.

`check_model_adapter.py` compile adapter firmware thật với artifact chỉ phục vụ test trong thư mục tạm;
không tạo model RF dùng cho demo và không thay model M2. Các script build vào thư mục tạm, không sửa source ML.

Các sóng trong engine là fixture M1, không phải bộ sinh M2 và không chứng minh độ chính xác RF.
Chưa chạy Wokwi/ESP32/broker/NVS: xem thủ tục và trạng thái **NOT RUN** trong [TEST_LOG.md](TEST_LOG.md).
T08 là stretch, vẫn chưa thực hiện. `gen_frd_golden.py` giữ bộ đối chứng hệ trục từ IMU simulator M2.
