# Rà soát kỹ thuật cuối — SVMG M2 Data Preprocessing

Ngày rà soát: 2026-11-16. Phạm vi gồm source code, cấu hình, unit tests, notebook, báo cáo và artifact được tạo từ dữ liệu thực. Không trích xuất feature, tạo nhãn hoặc huấn luyện mô hình.

## 1. Kết quả đã xác nhận

### Đối soát hàng Seafar

| Bước | Hàng | Diễn giải |
|---|---:|---|
| Đầu vào | 143.318 | JSON raw, một session |
| Loại nhóm timestamp xung đột | −28 | 14 nhóm; mỗi nhóm bị loại toàn bộ, không lấy trung bình |
| Duplicate đồng nhất | −0 | Không có hàng duplicate giống hệt |
| Thiếu/không hữu hạn ở trường bắt buộc | −0 | Timestamp, Roll, Pitch đều qua kiểm tra |
| Đoạn ngắn hơn 1 giây | −10 | 8 đoạn ngắn hình thành quanh các gap |
| Hàng nguồn thuộc segment được giữ | 143.280 | 24 segment liên tục riêng biệt |
| Điểm lưới resampling 10 Hz | 143.264 | Đầu ra cuối cùng |

Chênh lệch 54 hàng phân rã chính xác thành `28 + 10 + 16`. Phần 16 là chênh lệch số điểm giữa các hàng nguồn và lưới đầu ra: 16/24 segment có số điểm lưới ít hơn một so với số hàng nguồn; 8 segment có cùng số đếm. Không có target timestamp nào bị loại vì vượt tuổi mẫu cho phép. Seafar không bị lọc và không có warmup filter. Vì vậy 16 không phải hàng invalid bị loại do chất lượng; đây là khác biệt biểu diễn khi regularize về 10 Hz. Chi tiết này đã được bổ sung vào [báo cáo preprocessing](preprocessing_results.md).

### Filter anti-alias và hành vi causal

Cấu hình được kiểm tra vẫn giữ nguyên: Butterworth bậc 4, cutoff 4 Hz, đầu vào 50 Hz, đầu ra 10 Hz; dạng SOS và `sosfilt`. Bộ lọc causal không dùng mẫu tương lai. Trạng thái khởi tạo là `sosfilt_zi × mẫu đầu`, tương đương steady-state cho tín hiệu hằng bằng giá trị mẫu đầu. Resampling chọn mẫu trước gần nhất; timestamp đầu ra không được bù pha nên tín hiệu có độ trễ vật lý so với timestamp được gán.

Đáp ứng lý thuyết được tính từ đúng SOS của cấu hình tại 50 Hz:

| Tần số | Gain biên độ | Group delay xấp xỉ |
|---:|---:|---:|
| 0,5 Hz | −0,0000002 dB | 0,103 s |
| 1 Hz | −0,000056 dB | 0,105 s |
| 2 Hz | −0,0149 dB | 0,117 s |
| 3 Hz | −0,386 dB | 0,147 s |
| 4 Hz (cutoff) | −3,010 dB | 0,153 s |
| 5 Hz (Nyquist đầu ra) | −8,795 dB | — |

Pha trễ tăng theo tần số và không phải một dịch thời gian cố định cho mọi thành phần. Việc không hiệu chỉnh pha là phù hợp với xử lý causal, nhưng cần tính đến khi so sánh thời điểm/pha giữa tín hiệu hoặc giữa Python và firmware.

Cutoff 4 Hz giữ gần như nguyên dải 0,1–2 Hz trong dữ liệu thật: median tỷ lệ công suất sau/trước là 0,99991/0,99995 cho Roll/Pitch Hohai và 0,99764/0,99979 cho Southampton. Suy giảm công suất có trọng số Welch ở dải 5,25 Hz đến Nyquist nguồn có median −24,69/−23,75 dB với Hohai và −16,27/−24,55 dB với Southampton. Đây là kết quả theo phổ của các mẫu đã đo, không phải bảo đảm attenuation cho mọi tín hiệu. Tại 5 Hz, gain lý thuyết chỉ −8,80 dB; vì vậy vùng chuyển tiếp sát Nyquist 5 Hz vẫn có rủi ro alias và cấu hình không tạo stop-band sâu ngay tại Nyquist.

Rà soát phát hiện trước đó filter chỉ áp dụng Roll/Pitch/gyro, trong khi các kênh liên tục bổ sung cũng bị giảm mẫu. Đã sửa tối thiểu `signal_processing.py`: mọi kênh liên tục dạng số hữu hạn được lọc trước giảm mẫu; trường hậu tố `_raw` được giữ nguyên theo nguồn. Provenance ghi các kênh thực sự lọc và trường raw được bảo toàn. Test mới xác nhận accelerometer 8 Hz bị suy giảm sau filter và `Delta Angle *_raw` không bị thay đổi. Pipeline và cấu hình sản xuất không bị viết lại hoặc đổi thông số.

#### Phân tích độ nhạy cutoff bằng dữ liệu thật

So sánh cutoff hiện tại 4 Hz với phương án kỹ thuật 3 Hz trên segment dài nhất Hohai (`Berth_D_T1_Type_A`) và Southampton (`southampton_run_14`). Cùng filter order, khởi tạo, warmup và target rate; chỉ thay cutoff trong lần phân tích tạm, không ghi artifact và không đổi production config.

| Nguồn / tín hiệu | RMSE giữa đầu ra 3 Hz và 4 Hz | Tương quan | RMS 3 Hz / 4 Hz | Công suất thấp 4 Hz / 3 Hz | Attenuation ngoài dải 4 Hz / 3 Hz |
|---|---:|---:|---:|---:|---:|
| Hohai Roll | 0,03169° | 0,9921 | 0,99997 | 1,00027 / 1,00035 | −24,49 / −34,64 dB |
| Hohai Pitch | 0,00820° | 0,9920 | 0,99952 | 0,99996 / 0,99994 | −23,58 / −33,72 dB |
| Southampton Roll | 0,01658° | 0,9549 | 1,0000 | 0,99399 / 0,98912 | −17,49 / −27,60 dB |
| Southampton Pitch | 0,00934° | 0,9914 | 1,00001 | 1,00234 / 1,00280 | −21,24 / −31,37 dB |

Cutoff 3 Hz tăng suy giảm ngoài dải khoảng 10 dB trong hai segment đại diện; sai khác RMS thấp, nhưng tương quan Roll Southampton giảm do thay đổi đáp ứng pha/hình dạng theo thời gian. Chưa có band-limit vật lý được nhóm phê duyệt để chọn 3 hay 4 Hz. Giữ 4 Hz là quyết định cấu hình hiện hành, không phải kết luận tối ưu; cần đánh giá phổ chuyển động tàu và tiêu chí phát hiện trước khi chốt.

#### Warmup 2 giây

Pole có bán kính lớn nhất 0,82987, tương ứng hằng số thời gian xấp xỉ 0,107 s; 2 giây bằng khoảng 18,6 hằng số thời gian. Đây là khoảng bỏ đầu bảo thủ theo động học của filter, nhưng vẫn là engineering heuristic: không có ground truth để chứng minh mọi transient của cảm biến đã ổn định sau đúng 2 giây. Khởi tạo steady-state cũng làm tín hiệu hằng không có bước quá độ lý tưởng.

Sensitivity trên toàn bộ 21 sheet Hohai và 47 run Southampton:

| Nguồn | Warmup | Hàng đầu ra | Đủ 60 s | Đủ 180 s |
|---|---:|---:|---:|---:|
| Hohai | 1 s | 188.790 | 21 | 21 |
| Hohai | 2 s | 188.580 | 21 | 21 |
| Hohai | 4 s | 188.160 | 21 | 21 |
| Southampton | 1 s | 54.412 | 47 | 1 |
| Southampton | 2 s | 53.942 | 47 | 1 |
| Southampton | 4 s | 53.002 | 47 | 1 |

Không thay đổi số phiên đủ cửa sổ trong các phương án này. Thay warmup chỉ đổi số điểm đầu mỗi segment; không khắc phục được thiếu timestamp/dropout Hohai hoặc thiếu run 180 giây Southampton.

### Kênh liên tục bổ sung

Sau sửa anti-alias, trên Hohai `Berth_D_T1_Type_A`, attenuation ngoài dải đo được: Yaw −22,28 dB, Surge −22,42 dB, Sway −21,59 dB, Heave −20,91 dB. Trên Southampton Run 14: Accelerometer X/Y/Z lần lượt −27,71/−25,30/−21,55 dB; Heave −20,21 dB; Yaw −20,36 dB. Các `Delta Angle *_raw` không lọc theo chính sách giữ raw và có attenuation đo được 0 dB. Đơn vị ghi trong CSV là degree/s nhưng ngữ nghĩa chưa xác nhận; không dùng các trường này làm gyro canonical.

## 2. Tính tái lập và notebook

- Môi trường chạy: Python 3.14.6; NumPy 2.4.6; pandas 3.0.3; SciPy 1.18.0; openpyxl 3.1.5; PyArrow 23.0.1; PyYAML 6.0.3; Matplotlib 3.11.0. Các notebook dùng `nbconvert`/`ipykernel` trong requirements.
- `requirements.txt` dùng các dải phiên bản tương thích, không phải lockfile. Để tái lập số học chặt, dùng các phiên bản ghi trong `preprocessing_summary.json`.
- Đường dẫn cấu hình/input/output của CLI và lệnh trong README là repository-relative. Raw data phải được đặt riêng trong `ml/data/raw/`; cả `ml/data/raw/` và `ml/data/processed/` đều bị `.gitignore` loại trừ. Dataset không có trong Git nên thành viên mới phải nhận/cung cấp dataset trước khi chạy.
- Lệnh tái tạo dữ liệu Parquet, provenance, hình, báo cáo preprocessing và summary JSON là `python -m ml.preprocessing.run --config ml/preprocessing/config.yaml --dataset all`. Lệnh này xóa và sinh lại thư mục processed theo từng dataset; chạy từ repository root sau khi đã đặt đúng raw data.
- Chạy notebook sau pipeline bằng bốn lệnh `python -m jupyter nbconvert --to notebook --execute --inplace ml/notebooks/<tên notebook>`, như hướng dẫn trong README. Notebook không tự tái xử lý/ghi Parquet; chúng đọc summary, loader và artifact đã sinh.
- Cả bốn notebook đã chạy top-to-bottom sau lần chạy pipeline cuối: Seafar 8/8, Hohai 8/8, Southampton 8/8, Comparison 6/6 code cell; không cell nào có output lỗi. Mã nguồn notebook không có đường dẫn tuyệt đối theo máy; output chứa preview nhỏ, bảng và hình, không chứa toàn bộ raw data. Kích thước lần lượt xấp xỉ 0,31/0,38/0,29/1,63 MB. Notebook dùng helper phân giải path từ repository root; JSON metadata hiện được lưu bằng đường dẫn tương đối.
- Đã chuẩn hóa `repository_root`, `configuration_path`, inventory, figure references và `raw_reference` trong summary/provenance thành đường dẫn tương đối từ repository root. Summary/provenance được tái sinh sau thay đổi và không còn đường dẫn absolute theo máy.

## 3. Kiểm thử và vệ sinh Git

Sau thay đổi phạm vi filter, đã chạy:

```text
python -m pytest ml/preprocessing/tests -q
18 passed in 1.62s
```

Test mới kiểm tra filter trên kênh liên tục bổ sung và bảo toàn Delta Angle raw; các test trước tiếp tục bao phủ unit conversion, timestamp, duplicate, gap/session, causal prefix, 50→10 Hz và window eligibility. CLI `--dataset all` chạy thành công và ghi lại 18/18 vào summary.

Kiểm tra `.gitignore` xác nhận raw JSON và Parquet nằm dưới các quy tắc `/ml/data/raw/` và `/ml/data/processed/`. Không có notebook checkpoint. `__pycache__`/pytest cache bị ignore. Các file ở trạng thái untracked là deliverable mã nguồn, tests, README, notebook, Markdown/JSON report; không có raw dataset hoặc processed Parquet trong danh sách Git. Notebook tổng hợp lớn nhất khoảng 1,63 MB, chứa hình chẩn đoán chứ không chứa bảng dữ liệu đầy đủ. Không commit hoặc push.

## 4. Giả định, hạn chế và khuyến nghị

### Giả định/kỹ thuật hiện hành

- Cutoff 4 Hz, target 10 Hz, warmup 2 giây và gap threshold 1,5× median `dt` là quyết định kỹ thuật cấu hình được, chưa phải ngưỡng hàng hải được chứng nhận.
- Hohai time được suy từ index/50 Hz; không thể xác nhận sensor dropout từ workbook.
- Seafar rate được đổi từ rad/min theo tên trường; trục, dấu và lineage cảm biến còn cần xác nhận.
- Filter được reset ở mỗi segment/session; không có lọc xuyên gap. Nhãn thời gian output không hiệu chỉnh group delay.

### Hạn chế còn lại

- Butterworth bậc 4 chỉ suy giảm khoảng 8,8 dB tại Nyquist 5 Hz; attenuation thật phụ thuộc phổ tín hiệu. Chưa xác định dải tần nguy hiểm/quan trọng của vessel motion để chấp nhận 4 Hz.
- Warmup 2 giây chưa được xác nhận bằng đáp ứng transient của phần cứng hoặc tiêu chí sai số ứng dụng.
- Các trường hậu tố `_raw` cố ý không lọc; không được dùng như dữ liệu 10 Hz đã anti-alias.
- Các thư mục dữ liệu raw/processed bị loại khỏi Git; clone mới cần nhận raw datasets và chạy pipeline trước khi mở notebook.
- Southampton chỉ có một run đủ 180 giây; Hohai continuity là suy luận; gyro đo trực tiếp không sẵn ở Hohai/Southampton.

### Đề xuất trước Feature Extraction

1. Nhóm xác nhận tần số chuyển động cần giữ và chấp nhận attenuation/phase delay; benchmark 3 Hz, 4 Hz hoặc filter khác trên mục tiêu vật lý và dữ liệu gắn nhãn sau này.
2. Xác nhận warmup bằng tiêu chí sai số/settling thay vì chỉ số pole; cân nhắc metadata time alignment nếu feature phụ thuộc pha/độ trễ.
3. Chỉ đưa các kênh đã xác nhận đơn vị/trục vào Feature Extraction; không dùng `Delta Angle *_raw` như gyro và không suy gyro từ góc trong bước này.
4. Thiết kế validity mask và grouped split theo session/run; không chia các cửa sổ cùng session ngẫu nhiên sang Train/Test.
5. Trước khi đánh giá đủ 30 candidate features, giải quyết thiếu gyro và số lượng window 180 s hạn chế theo từng nguồn. Chưa nên tuyên bố sẵn sàng cho training hoặc ESP32 deployment.
