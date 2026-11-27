# Smart Vessel Motion Guard Mobile – TV4 demo

Ứng dụng **React Native/Expo** với hai chế độ chọn ở màn hình đăng nhập: **LIVE** (Backend FastAPI thật, đăng nhập JWT) và **MOCK** (demo offline).
Xem `docs/backend-integration.md` để biết cách kết nối Backend và các giới hạn.
Mã này là khung ứng dụng có tương tác và thiết kế theo phong cách Stitch,
chưa chuyển đổi chính xác từng pixel của 15 màn hình HTML tham chiếu.

## Khởi chạy (Windows PowerShell)

```powershell
cd mobile
npm.cmd install
npx.cmd expo install --fix
npx.cmd expo install react-native-svg react-native-safe-area-context
npx.cmd tsc --noEmit
npx.cmd expo start --clear
```

Quét mã QR bằng Expo Go tương thích với Expo SDK 57. Nếu SDK Expo Go khác,
ưu tiên `npx expo install --fix` và kiểm tra phiên bản SDK đang dùng, không trộn nhiều project.

## Tài khoản DEMO (chỉ chế độ MOCK)

- `operator` / `demo123` — xem giám sát, ACK, Review.
- `supervisor` / `demo123` — thêm cấu hình thường, báo cáo/Model Monitor.
- `admin` / `demo123` — thêm chọn kịch bản mô phỏng.

### Luồng màn hình
Login → Overview → tab Home/Motion/Alarms/Reports/More.
More → Control Center, Replay, Device Health, Model Monitor; có Logout.

**Giới hạn MOCK:** dữ liệu nằm trong bộ nhớ và reset khi reload; các nút mô phỏng chỉ phản hồi trong App.
**LIVE:** lệnh/ACK/nhãn gửi tới Backend thật; tải CSV/PDF chưa hỗ trợ trên mobile (dùng dashboard web).

## Thiết kế

Nguồn: `../designs/stitch-mobile/`; native component trong `src/screens/`.
Không nên thay nguyên màn hình bằng WebView; dùng HTML làm reference thiết kế.
