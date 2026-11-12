**KẾ HOẠCH CHIA VIỆC CHO 4 THÀNH VIÊN**

Đồ án IoT – Smart Vessel Motion Guard (đề cương v2.0)

*Mỗi người 40 điểm công việc · làm độc lập qua hợp đồng giao diện · quản
lý bằng GitHub*

# 1. Nguyên tắc chia việc

1.  **Chia theo module, mỗi người sở hữu trọn một mảng:** mã nguồn, kiểm
    thử, README và phần báo cáo của mảng đó.

2.  **Chia đều:** mỗi người đúng **40 điểm công việc (SP)**. 1 SP ≈ 1
    ngày công tập trung (khoảng 4 giờ). Mỗi người có thêm 1 hạng mục phụ
    (stretch) 3 SP, không tính vào chỉ tiêu.

3.  **Làm độc lập nhờ hợp đồng + mock:** trong tuần 1 cả nhóm cùng chốt
    thư mục contracts/ (định dạng bản tin MQTT, OpenAPI, header C, thứ
    tự đặc trưng) rồi gắn thẻ contracts-v1. Từ đó mỗi người dùng mock
    cho phần mình phụ thuộc, không phải chờ nhau.

4.  **Không sửa trực tiếp mã của người khác:** cần thay đổi thì mở issue
    hoặc PR vào module đó. PR được **review chéo theo vòng**: M1 → M2 →
    M3 → M4 → M1 (người kế tiếp review PR của người trước).

5.  Mỗi người đều có đủ phần khó (lõi, mô hình, dịch vụ, giao diện) và
    phần nhẹ (kiểm thử, tài liệu).

# 2. Tổng quan 4 vai trò

|  | **Vai trò** | **Thư mục sở hữu** | **SP** | **Trách nhiệm chính** |
|:---|:---|:---|:---|:---|
| M1 | Embedded / Lõi C | core/ (trừ core/src/sim/), firmware/ | 40 | Mạch Wokwi, lọc và đặc trưng, ngưỡng cứng, MAI, máy trạng thái cảnh báo, MQTT, xử lý lệnh/cấu hình, bộ đệm offline. |
| M2 | Mô phỏng / ML | simulation/, ml/, core/src/sim/ | 40 | Bộ sinh tín hiệu (Python và C), dữ liệu 605 phiên, Random Forest, baseline, đánh giá, giám sát mô hình, mock_device và fleet_sim. |
| M3 | Backend / Dữ liệu | backend/ | 40 | Nhận MQTT, CSDL, vòng đời cảnh báo, kênh lệnh, phân quyền, chuyến đi và báo cáo PDF/CSV, replay, thông báo. |
| M4 | Frontend / Hạ tầng / QA / Tài liệu | frontend/, infra/, tests/e2e/, docs/report/ | 40 | Dashboard 9 trang, docker-compose và CI, kiểm thử đầu cuối, chủ trì tuần tích hợp, demo, ghép báo cáo. |

# 3. Gói công việc của từng người

Cột "Phụ thuộc" là gói công việc phải xong (hoặc dùng mock) trước khi
bắt đầu. Tuần tính từ tuần 1 của dự án.

## Thành viên 1 – Embedded / Lõi C (40 SP)

| **WP** | **Công việc** | **SP** | **Tuần** | **Phụ thuộc** | **Sản phẩm bàn giao** |
|:---|:---|:---|:---|:---|:---|
| M1-01 | Mạch Wokwi: ESP32, MPU6050, LCD I2C, 3 nút (MODE/SCENARIO/ACK), chiết áp, LED, buzzer | 3 | 1 | – | firmware/wokwi/diagram.json, bảng chân trong README |
| M1-02 | acquireMotionSample (SENSOR), bộ lọc bù, lọc thông thấp và giảm mẫu 20→2 Hz | 5 | 1–2 | M1-01 | core/src/filter.c + test đơn vị trên máy chủ |
| M1-03 | Đặc trưng cửa sổ 60 s/180 s, cờ chất lượng, quy tắc UNKNOWN/FAULT | 6 | 2–3 | M1-02 | core/src/features.c khớp contracts/features.md |
| M1-04 | Lớp ngưỡng cứng (safety envelope), chỉ số MAI, Baseline B bằng C (tham số lấy từ M2) | 4 | 3–4 | M1-03 | core/src/baseline.c, safety.c, mai.c |
| M1-05 | Máy trạng thái cảnh báo (NORMAL/CAUTION/WARNING/CRITICAL/ACKED) + LED/buzzer/LCD/nút ACK | 6 | 3–4 | M1-04 | core/src/alarm_fsm.c + bộ kiểm thử chuỗi sự kiện |
| M1-06 | Kết nối WiFi/MQTT; telemetry, event, status (LWT), health; bộ đệm offline boot_id+seq | 6 | 4–5 | M1-05 | firmware/src/net.c, buffer.c |
| M1-07 | Xử lý lệnh/cấu hình: cmd_id idempotent, TTL, CRC, NVS, ràng buộc an toàn, mã từ chối | 5 | 4–6 | M1-06 | firmware/src/cmd.c, config.c |
| M1-08 | Tích hợp RF (model.h của M2) + shadow Baseline B + đo thời gian suy luận, RAM, flash | 2 | 5–6 | M2-06 | firmware/src/infer.c, bảng đo tài nguyên |
| M1-09 | Kiểm thử T01, T05, T07 (lỗi cảm biến), README firmware, nhật ký kiểm thử | 3 | 5–8 | M1-07 | tests/firmware/, firmware/README.md |
|  | Tổng | 40 |  |  |  |

*Stretch (S1-01, 3 SP): T08: chạy kiểm chứng chéo A/B bằng Wokwi
Automation Scenarios (cần CLI + token).*

## Thành viên 2 – Mô phỏng / ML (40 SP)

| **WP** | **Công việc** | **SP** | **Tuần** | **Phụ thuộc** | **Sản phẩm bàn giao** |
|:---|:---|:---|:---|:---|:---|
| M2-01 | Bộ sinh Python (dao động tử roll): S0, S0b, S1, S2, S3, H1 và bộ sinh G2 (tổng sin, nhiễu khác) | 6 | 1–2 | – | simulation/generator/ + cấu hình kịch bản |
| M2-02 | Cổng C của bộ sinh (core/sim, xorshift32) dùng chung cho ESP32 và máy chủ; kiểm tra tương đương với Python | 5 | 2–3 | M2-01 | core/src/sim/ + test sai số Python so với C |
| M2-03 | Dựng dữ liệu: 605 phiên, quy tắc nhãn ưu tiên, vùng chuyển tiếp, CSV + metadata (Phụ lục B) | 4 | 2–3 | M2-01 | ml/data/ + sinh bằng một lệnh |
| M2-04 | Bao Python quanh lõi C (ctypes) để trích đặc trưng giống hệt firmware | 3 | 3–4 | M1-03 | ml/features_c.py |
| M2-05 | Chỉnh Baseline A/B trên validation; xuất tham số cho M1 | 3 | 3–4 | M2-04 | ml/baselines/ + baseline_params.json |
| M2-06 | Huấn luyện Random Forest (GroupKFold theo phiên), xuất mã C bằng emlearn: model.h | 4 | 4–5 | M2-04 | ml/train/ + ml/export/model.h |
| M2-07 | Bộ đánh giá: macro-F1, cảnh báo giả/giờ trên ≥100 giờ NORMAL, độ trễ cold/warm, bootstrap theo phiên, so sánh ML/Baseline | 6 | 5–7 | M2-05,M2-06 | ml/eval/ + báo cáo kết quả |
| M2-08 | Registry mô hình (JSON), thư viện Model Monitor: PSI, Isolation Forest, tỉ lệ đồng thuận RF/Baseline B | 4 | 5–6 | M2-06 | ml/registry/, ml/monitor/ |
| M2-09 | mock_device và fleet_sim (3–5 tàu ảo) phát MQTT đúng schema; chèn mất gói và lỗi để thử T10/T14 | 5 | 2–4 | M2-01 | simulation/mock_device.py, fleet_sim.py |
|  | Tổng | 40 |  |  |  |

*Stretch (S2-01, 3 SP): Bối cảnh biển: lấy dự báo sóng Open-Meteo, quy
đổi sang sea state; T16.*

## Thành viên 3 – Backend / Dữ liệu (40 SP)

| **WP** | **Công việc** | **SP** | **Tuần** | **Phụ thuộc** | **Sản phẩm bàn giao** |
|:---|:---|:---|:---|:---|:---|
| M3-01 | Khung FastAPI, cấu hình, lược đồ CSDL (SQLAlchemy, SQLite→PostgreSQL), migration; viết contracts/openapi.yaml | 4 | 1–2 | – | backend/ khởi chạy được + openapi.yaml v1 |
| M3-02 | MQTT ingest: kiểm tra JSON Schema, chống trùng (device_id,boot_id,seq), xử lý LWT/offline | 5 | 2–3 | M3-01 | backend/ingest/ + kiểm thử bản tin sai |
| M3-03 | Alarm service: máy trạng thái (theo đặc tả), MTTA, leo thang, WebSocket đẩy dữ liệu trực tiếp | 6 | 3–4 | M3-02 | backend/alarms/ + test chuỗi sự kiện |
| M3-04 | Command service: SENT→DELIVERED→APPLIED/REJECTED/TIMEOUT, thử lại cùng cmd_id, TTL, nhật ký kiểm toán; cấu hình có phiên bản + rollback | 6 | 3–5 | M3-02 | backend/commands/ |
| M3-05 | Xác thực JWT, phân quyền Operator/Supervisor/Admin (Bảng 3.1), nhật ký kiểm toán | 3 | 4–5 | M3-01 | backend/auth/ |
| M3-06 | Chuyến đi (voyage) và báo cáo: thống kê, bảng cảnh báo, PDF/CSV | 6 | 5–6 | M3-03 | backend/reports/ |
| M3-07 | API replay, nhãn đánh giá cảnh báo, sức khỏe thiết bị, tích hợp thư viện Model Monitor của M2 | 4 | 5–7 | M3-06,M2-08 | backend/replay/, health/, monitor/ |
| M3-08 | Thông báo Telegram/email webhook, giới hạn tần suất, gộp theo alarm_id | 2 | 6 | M3-03 | backend/notify/ |
| M3-09 | Kiểm thử T06 (phía backend), T09, T10, T14 (chịu tải bằng fleet_sim); README backend | 4 | 6–8 | M3-04,M2-09 | tests/backend/ |
|  | Tổng | 40 |  |  |  |

*Stretch (S3-01, 3 SP): Gộp nhiều thiết bị: lọc, so sánh, API cho trang
Fleet; phân trang dữ liệu lớn.*

## Thành viên 4 – Frontend / Hạ tầng / QA / Tài liệu (40 SP)

| **WP** | **Công việc** | **SP** | **Tuần** | **Phụ thuộc** | **Sản phẩm bàn giao** |
|:---|:---|:---|:---|:---|:---|
| M4-01 | Khung React/Vite, client sinh từ openapi.yaml, đăng nhập, bố cục, trạng thái kết nối | 4 | 1–3 | M3-01 | frontend/ chạy với mock API |
| M4-02 | Trang Overview và Live Motion (đồ thị roll/pitch, nhãn RF so với Baseline B, MAI) | 5 | 3–4 | M4-01 | frontend/src/pages/ |
| M4-03 | Trang Alarms: vòng đời, nút ACK/mute, MTTA, bộ lọc | 4 | 4–5 | M4-02,M3-03 | frontend/src/pages/Alarms |
| M4-04 | Trang Control Center: form lệnh, theo dõi trạng thái lệnh, lịch sử và rollback cấu hình | 5 | 5–6 | M4-02,M3-04 | frontend/src/pages/Control |
| M4-05 | Trang Voyage Reports và Replay & Review (thanh thời gian, gắn nhãn đúng/sai) | 6 | 5–7 | M3-06,M3-07 | frontend/src/pages/Reports, Replay |
| M4-06 | Trang Device Health, Model Monitor, Fleet (bản đồ Leaflet) | 5 | 6–7 | M3-07,M2-09 | frontend/src/pages/Health, Monitor, Fleet |
| M4-07 | docker-compose (Mosquitto có xác thực/ACL, backend, CSDL, frontend), .env.example, GitHub Actions CI cho cả 4 module | 4 | 1–2 | – | infra/ + .github/workflows/ci.yml chạy xanh |
| M4-08 | Kế hoạch kiểm thử đầu cuối; script tính lại độc lập số liệu báo cáo (T11) và T15; chủ trì tuần tích hợp; kịch bản và video demo | 4 | 5–8 | M3-06 | tests/e2e/, docs/report/demo.md |
| M4-09 | README gốc, ghép báo cáo cuối kỳ (nhận phần từ cả nhóm), hướng dẫn chạy, kiểm tra tài liệu tham khảo | 3 | 6–8 | – | docs/report/ |
|  | Tổng | 40 |  |  |  |

*Stretch (S4-01, 3 SP): Hoàn thiện giao diện Fleet và cờ bối cảnh biển;
giao diện tối/sáng; xuất ảnh đồ thị.*

# 4. Phụ thuộc chéo và mock

| **Người cần** | **Cần từ** | **Qua hợp đồng** | **Mock dùng trong lúc chờ** |
|:---|:---|:---|:---|
| M1 | M2: model.h, tham số baseline, core/src/sim/ | svmg_core.h, svmg_sim.h, features.md | model_stub.h (luôn trả NORMAL); bộ sinh sin đơn giản; tham số baseline mặc định |
| M2 | M1: core/src/features.c | svmg_core.h, features.md | Bản Python tham chiếu ml/features_ref.py cho đến khi M1-03 merge |
| M3 | M1/M2: bản tin MQTT | schemas/\*.json, examples/\*.json | simulation/mock_device.py (M2-09) hoặc ví dụ trong contracts/examples |
| M4 | M3: REST và WebSocket | openapi.yaml | Mock API sinh từ openapi.yaml (Prism hoặc MSW) + dữ liệu mẫu trong frontend/fixtures/ |
| M4 | M2: fleet_sim cho trang Fleet | schemas/\*.json | Dữ liệu mẫu nhiều tàu |
| M3 | M2: thư viện Model Monitor | ml/monitor/ | Hàm giả trả PSI = 0 |

> **Tuần 1 – việc chung của cả nhóm (ngày 1–3)**
>
> Cả 4 người cùng đọc, sửa và chốt contracts/, sau đó gắn thẻ
contracts-v1. Sau ngày 3, đổi hợp đồng chỉ qua PR có chấp thuận của
người phát và ít nhất một người nhận.

# 5. Lịch 8 tuần

| **Tuần** | **Cả nhóm** | **M1** | **M2** | **M3** | **M4** |
|:---|:---|:---|:---|:---|:---|
| 1 | Chốt contracts-v1 | M1-01, 02 | M2-01 | M3-01 | M4-01, 07 |
| 2 |  | M1-02, 03 | M2-01..03, 09 | M3-01, 02 | M4-01 |
| 3 |  | M1-03..05 | M2-02..05 | M3-02..04 | M4-01, 02 |
| 4 |  | M1-04..07 | M2-04..06, 09 | M3-03..05 | M4-02, 03 |
| 5 | Tích hợp MVP (M4 chủ trì): toàn bộ chức năng bắt buộc chạy đầu cuối | M1-06..09 | M2-06..08 | M3-04..07 | M4-03..05, 08 |
| 6 | Sửa lỗi tích hợp | M1-07..09 | M2-07, 08 | M3-06..09 | M4-04..06, 09 |
| 7 | Stretch và kiểm thử | stretch | M2-07, stretch | M3-07, 09, stretch | M4-05, 06, stretch |
| 8 | Đánh giá độc lập, báo cáo, video demo | M1-09 | Báo cáo kết quả | M3-09 | M4-08, 09 |

Nếu thời hạn học phần ngắn hơn 8 tuần: cắt stretch trước, rồi các chức
năng mở rộng (trang Fleet, Open-Meteo, phát hiện drift). Không cắt các
chức năng bắt buộc.

# 6. Ai chạy thí nghiệm nào

| **Mã** | **Thí nghiệm** | **Chủ trì** | **Hỗ trợ** |
|:---|:---|:---|:---|
| T01 | MPU6050 ở SENSOR MODE | M1 |  |
| T02 | Chạy S0, S0b, S1, S2, S3, H1 | M2 | M1 |
| T03 | Python so với lõi C so với ESP32 | M2 | M1 |
| T04 | ML so với Baseline A/B trên Test-G1/G2 và bộ NORMAL dài | M2 |  |
| T05 | Ngắt MQTT lúc có bất thường | M1 | M4 (demo) |
| T06 | Phục hồi mạng, đồng bộ, khởi động lại | M3 | M1 |
| T07 | Lỗi cảm biến / thiếu mẫu | M1 |  |
| T08 | Kiểm chứng chéo A/B bằng Wokwi Automation (stretch) | M1 |  |
| T09 | Vòng đời cảnh báo | M3 | M1 (thiết bị), M4 (giao diện) |
| T10 | Kênh lệnh: RTT, mất gói, lệnh vi phạm an toàn | M3 | M2, M1 |
| T11 | Độ chính xác báo cáo (tính lại độc lập) | M4 viết script | M3 |
| T12 | Shadow mode và phát hiện drift | M2 |  |
| T13 | Lỗi sức khỏe chèn vào | M1 | M4 |
| T14 | Đội tàu, chịu tải | M3 | M2 |
| T15 | Replay khớp dữ liệu gốc | M4 | M3 |
| T16 | Bối cảnh biển (stretch) | M2 |  |

*T11 cố ý giao cho người không viết phần sinh báo cáo, để số liệu được
tính lại độc lập.*

# 7. Phần báo cáo cuối kỳ mỗi người viết

| **Người** | **Các mục của đề cương v2.0** |
|:---|:---|
| M1 | 5 (Wokwi), 7.1–7.2 (xử lý tín hiệu, cửa sổ), 8.5 (sức khỏe), 9.1; kết quả T01, T05, T07 |
| M2 | 6 (mô hình tín hiệu), 7.3–7.5 (ML), 8.6–8.7 (giám sát mô hình, bối cảnh biển), 10.1–10.5; kết quả T02–T04, T12, T14, T16 |
| M3 | 3 (yêu cầu), 4 (kiến trúc), 8.1–8.4 (cảnh báo, lệnh, báo cáo, replay), 9.2–9.3 (MQTT, bảo mật); kết quả T06, T09–T11 |
| M4 | 1, 2, 9.4 (dashboard), 11–13 (kế hoạch, rủi ro, demo, bảo vệ), 14 (tài liệu tham khảo), phụ lục; ghép toàn bộ |

# 8. Quy ước làm việc trên GitHub

- main được bảo vệ: không đẩy trực tiếp; cần PR, 1 review và CI xanh.

- Tên nhánh theo mã gói công việc: feat/M3-04-command-retry,
  fix/M1-06-lwt-topic.

- Commit theo Conventional Commits: feat(core): thêm bộ lọc bù,
  fix(backend): chống trùng bản tin.

- PR nhỏ (khoảng dưới 400 dòng), ghi rõ gói công việc và bài kiểm thử đã
  chạy.

- Chỉ sửa trong thư mục mình sở hữu (xem CODEOWNERS); sửa contracts/ cần
  người phát và ít nhất một người nhận chấp thuận.

- Không commit khóa, mật khẩu, token; dùng biến môi trường và cập nhật
  .env.example.

- Một gói công việc được coi là xong khi: đạt sản phẩm bàn giao, có kiểm
  thử hoặc nhật ký kiểm thử, README module cập nhật, PR đã merge và CI
  xanh.

## Khi lệch tiến độ

- Cuối mỗi tuần cập nhật bảng GitHub Projects theo từng gói công việc
  (Todo, Doing, Review, Done).

- Nếu ai trễ hơn 3 SP: chuyển gói công việc **chưa bắt đầu** có SP thấp
  nhất sang người còn dư, ghi lại trong docs/work_packages.csv và cập
  nhật CODEOWNERS.

- Không chuyển gói đang làm dở giữa tuần; chỉ chuyển ở ranh giới tuần.

# 9. Việc cần làm ngay

1.  Chọn ai là M1, M2, M3, M4 (có thể bốc thăm hoặc theo sở trường).

2.  Mỗi người tạo tài khoản GitHub, gửi username cho người lập repo;
    thay @member1..4 trong CODEOWNERS.

3.  Người lập repo up khung repo, bật bảo vệ nhánh main, chạy
    tools/create_issues.py để tạo issue từ danh sách gói công việc.

4.  Họp 1 buổi (khoảng 1–2 giờ) trong tuần 1 để chốt contracts-v1.

5.  Mỗi người đọc README của module mình và bắt đầu gói công việc tuần
    1.
