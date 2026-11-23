# Kiểm toán dataset mô phỏng G1 cho coursework RF

> Nhãn là `SIMULATION_SCENARIO_PROXY`, không phải ground truth/hazard. Chưa huấn luyện RF; không đánh giá Test-G2.

- Phiên: 36 (mỗi scenario: 9); tổng cửa sổ: 4284; đủ điều kiện: 482.
- Feature: svmg-angle-23-v1, đúng 23 tên/thứ tự; preprocessing: `imu-cf-bw4-20to10-v1`.
- CSV SHA-256: `ca3d28cca2fae32e8cbf5933b47957afa82430a48346d9e913a599c201508c85`. Pitch chỉ từ IMU/filter thực tế của simulator roll-only, không sinh thêm pitch motion.

| Split | Scenario | Session groups có mẫu đủ điều kiện | Cửa sổ đủ điều kiện | Cửa sổ loại |
|---|---|---:|---:|---:|
| Train | S0 | 4/4 | 40 | 436 |
| Train | S1 | 2/4 | 66 | 410 |
| Train | S2 | 3/4 | 51 | 425 |
| Train | S3 | 0/4 | 0 | 476 |
| Validation | S0 | 2/2 | 10 | 228 |
| Validation | S1 | 1/2 | 3 | 235 |
| Validation | S2 | 1/2 | 43 | 195 |
| Validation | S3 | 0/2 | 0 | 238 |
| Test-G1 | S0 | 3/3 | 168 | 189 |
| Test-G1 | S1 | 3/3 | 37 | 320 |
| Test-G1 | S2 | 1/3 | 37 | 320 |
| Test-G1 | S3 | 1/3 | 27 | 330 |

### Eligible windows per independent session

| Session ID | Split | Scenario proxy | Eligible | Excluded |
|---|---|---|---:|---:|
| `S0-seed-2026112301` | Train | NORMAL | 15 | 104 |
| `S0-seed-2026112302` | Train | NORMAL | 8 | 111 |
| `S0-seed-2026112303` | Train | NORMAL | 1 | 118 |
| `S0-seed-2026112304` | Train | NORMAL | 16 | 103 |
| `S0-seed-2026112305` | Validation | NORMAL | 8 | 111 |
| `S0-seed-2026112306` | Validation | NORMAL | 2 | 117 |
| `S0-seed-2026112307` | Test-G1 | NORMAL | 62 | 57 |
| `S0-seed-2026112308` | Test-G1 | NORMAL | 10 | 109 |
| `S0-seed-2026112309` | Test-G1 | NORMAL | 96 | 23 |
| `S1-seed-2026112310` | Train | HIGH_ROLL | 0 | 119 |
| `S1-seed-2026112311` | Train | HIGH_ROLL | 34 | 85 |
| `S1-seed-2026112312` | Train | HIGH_ROLL | 32 | 87 |
| `S1-seed-2026112313` | Train | HIGH_ROLL | 0 | 119 |
| `S1-seed-2026112314` | Validation | HIGH_ROLL | 0 | 119 |
| `S1-seed-2026112315` | Validation | HIGH_ROLL | 3 | 116 |
| `S1-seed-2026112316` | Test-G1 | HIGH_ROLL | 9 | 110 |
| `S1-seed-2026112317` | Test-G1 | HIGH_ROLL | 14 | 105 |
| `S1-seed-2026112318` | Test-G1 | HIGH_ROLL | 14 | 105 |
| `S2-seed-2026112319` | Train | PERSISTENT_OFFSET | 9 | 110 |
| `S2-seed-2026112320` | Train | PERSISTENT_OFFSET | 7 | 112 |
| `S2-seed-2026112321` | Train | PERSISTENT_OFFSET | 0 | 119 |
| `S2-seed-2026112322` | Train | PERSISTENT_OFFSET | 35 | 84 |
| `S2-seed-2026112323` | Validation | PERSISTENT_OFFSET | 0 | 119 |
| `S2-seed-2026112324` | Validation | PERSISTENT_OFFSET | 43 | 76 |
| `S2-seed-2026112325` | Test-G1 | PERSISTENT_OFFSET | 0 | 119 |
| `S2-seed-2026112326` | Test-G1 | PERSISTENT_OFFSET | 37 | 82 |
| `S2-seed-2026112327` | Test-G1 | PERSISTENT_OFFSET | 0 | 119 |
| `S3-seed-2026112328` | Train | AMPLITUDE_GROWTH | 0 | 119 |
| `S3-seed-2026112329` | Train | AMPLITUDE_GROWTH | 0 | 119 |
| `S3-seed-2026112330` | Train | AMPLITUDE_GROWTH | 0 | 119 |
| `S3-seed-2026112331` | Train | AMPLITUDE_GROWTH | 0 | 119 |
| `S3-seed-2026112332` | Validation | AMPLITUDE_GROWTH | 0 | 119 |
| `S3-seed-2026112333` | Validation | AMPLITUDE_GROWTH | 0 | 119 |
| `S3-seed-2026112334` | Test-G1 | AMPLITUDE_GROWTH | 0 | 119 |
| `S3-seed-2026112335` | Test-G1 | AMPLITUDE_GROWTH | 27 | 92 |
| `S3-seed-2026112336` | Test-G1 | AMPLITUDE_GROWTH | 0 | 119 |

## Kết luận

Training readiness: **BLOCKED_MISSING_CLASS_GROUP_COVERAGE**. Dataset phù hợp để kiểm tra plumbing/proxy theo G1, nhưng lớp thiếu coverage ở Train/Validation thì chưa train được. Chưa đủ cơ sở gọi là mô hình phenotype/hazard đã xác minh. Session/seed là group split; không chia cửa sổ ngẫu nhiên. Nhãn v1 đồng nhất, transition và overlap đã biết chỉ là bộ lọc proxy coursework, không phê duyệt ontology B2a.
