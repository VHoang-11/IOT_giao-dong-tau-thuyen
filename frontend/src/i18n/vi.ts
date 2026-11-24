/**
 * SMART VESSEL MOTION GUARD (SVMG) - BỘ TỪ ĐIỂN & VIỆT HÓA TOÀN DIỆN (i18n)
 * Áp dụng chuẩn thuật ngữ Hàng hải, An toàn cầu tàu và Bảng 3.1 đề cương v2.0
 */

export const i18n = {
  // 1. Sidebar & Điều hướng chính
  nav: {
    operationsGroup: 'Vận hành',
    overview: 'Tổng quan',
    motion: 'Giám sát chuyển động',
    alarms: 'Cảnh báo',
    control: 'Trung tâm điều khiển',
    reports: 'Báo cáo hành trình',
    replay: 'Phát lại và đánh giá',
    health: 'Tình trạng thiết bị',
    model: 'Giám sát mô hình',
    settings: 'Cài đặt',
    profile: 'Tài khoản',
    logout: 'Đăng xuất',
    more: 'Chức năng khác',
  },

  // 2. Vai trò người dùng (Bảng 3.1)
  roles: {
    Operator: 'Người trực ca',
    Supervisor: 'Giám sát viên',
    Admin: 'Quản trị viên',
  },

  // 3. Thuật ngữ Hàng hải
  maritime: {
    roll: 'Góc lắc ngang',
    pitch: 'Góc chúi dọc',
    port: 'Mạn trái',
    stbd: 'Mạn phải',
    starboard: 'Mạn phải',
    bowUp: 'Ngóc mũi',
    bowDown: 'Chúi mũi',
    even: 'Cân bằng',
    level: 'Mức chuẩn',
    waterline: 'Đường mực nước tham chiếu',
    horizon: 'Đường chân trời',
    peak: 'Giá trị đỉnh',
    digitalTwin: 'Mô hình số hóa',
    digitalTwinIso: 'Mô hình số hóa thân tàu (Phối cảnh Isometric)',
    isoView: 'Góc phối cảnh',
    rollView: 'Mặt cắt ngang',
    pitchView: 'Mặt cắt dọc',
    liveMotionChart: 'Biểu đồ dao động trực tiếp',
    mai: 'Chỉ số bất thường chuyển động (MAI)',
    maiFull: 'Chỉ số bất thường động học thân tàu (MAI)',
  },

  // 4. Trạng thái phân loại động học (TinyML / RFClass)
  rfClass: {
    NORMAL: 'Bình thường',
    HIGH_ROLL: 'Lắc ngang mạnh',
    PERSISTENT_OFFSET: 'Nghiêng lệch kéo dài',
    AMPLITUDE_GROWTH: 'Biên độ dao động tăng',
    UNKNOWN: 'Chưa xác định',
    FAULT: 'Lỗi cảm biến',
  },

  // 5. Mức độ cảnh báo (AlarmLevel)
  alarmLevel: {
    NORMAL: 'Bình thường',
    CAUTION: 'Cảnh giác',
    WARNING: 'Cảnh báo',
    CRITICAL: 'Nguy cấp',
    SAFE: 'An toàn',
  },

  // 6. Vòng đời cảnh báo (AlarmStatus)
  alarmStatus: {
    RAISED: 'Đã phát cảnh báo',
    ACKED: 'Đã xác nhận',
    CLEARED: 'Đã kết thúc',
    active: 'Đang hoạt động',
    ackBtn: 'Tiếp nhận (ACK)',
    muteBtn: 'Tạm tắt âm',
    details: 'Chi tiết cảnh báo',
    history: 'Lịch sử cảnh báo',
    filterStatus: 'Lọc trạng thái',
    all: 'Tất cả',
    mtta: 'Thời gian xác nhận trung bình',
    ackClarification: 'Xác nhận (ACK) chỉ ghi nhận sĩ quan trực ca đã tiếp nhận thông tin cảnh báo, không đồng nghĩa sự cố hoặc dao động nguy hiểm đã được xử lý xong.',
    criticalMuteNotice: 'Quy tắc an toàn: Cảnh báo mức NGUY CẤP (CRITICAL) không cho phép tạm tắt âm cảnh báo tại chỗ.',
  },

  // 7. Kết nối & Nguồn dữ liệu (SourceMode & Connectivity)
  system: {
    ONLINE: 'Đang kết nối',
    OFFLINE: 'Mất kết nối',
    SENSOR_FAULT: 'Lỗi cảm biến',
    MOCK_DATA: 'Dữ liệu mô phỏng',
    SIMULATION: 'Đang mô phỏng',
    SENSOR: 'Cảm biến phần cứng',
    LIVE: 'Dữ liệu trực tiếp',
    SAFE: 'An toàn',
    VALID: 'Hợp lệ',
    INVALID: 'Không hợp lệ',
    MISSING: 'Thiếu dữ liệu',
    NOT_APPLICABLE: 'Không áp dụng',
    STALE: 'Dữ liệu đã cũ',
    sensorOk: 'Bình thường (MPU6050 400kHz)',
    sensorError: 'Mất liên lạc / Lỗi I2C NACK',
    offlineNote: 'Mất kết nối MQTT (>30s). Dữ liệu đóng băng, hệ thống không tự tạo số đo giả mạo.',
  },

  // 8. Trung tâm điều khiển (Control Center)
  control: {
    currentConfig: 'Cấu hình hiện tại',
    deviceCommands: 'Lệnh thiết bị',
    sendCommand: 'Gửi lệnh',
    calibration: 'Hiệu chuẩn điểm 0',
    snapshot: 'Chụp trạng thái (Snapshot 180s)',
    timewarp: 'Tốc độ mô phỏng',
    scenario: 'Kịch bản thử nghiệm',
    rollback: 'Khôi phục cấu hình',
    commandHistory: 'Lịch sử thực thi lệnh',
    SENT: 'Đã gửi',
    DELIVERED: 'Đã chuyển đến thiết bị',
    APPLIED: 'Đã áp dụng',
    REJECTED: 'Bị từ chối',
    TIMEOUT: 'Quá thời gian chờ',
  },

  // 9. Biểu đồ & Phát lại (Charts & Replay)
  chart: {
    freezeFrame: 'Đóng băng khung hình',
    freezeActive: '❚❚ Đang đóng băng khung hình',
    resume: 'Tiếp tục',
    pause: 'Tạm dừng',
    play: 'Phát lại',
    playbackSpeed: 'Tốc độ phát',
    timeline: 'Dòng thời gian',
    scrub: 'Mốc đang chọn',
    currentSample: 'Mẫu hiện tại',
    selectedSample: 'Mẫu được chọn',
    timeRange: 'Khoảng thời gian (Buffer)',
    exportCsv: 'Xuất file CSV',
    exportReport: 'Xuất báo cáo',
    reset: 'Đặt lại',
    zoom: 'Phóng to / thu nhỏ',
    buffer10s: '10 giây',
    buffer30s: '30 giây',
    buffer1m: '1 phút',
    buffer5m: '5 phút',
    emptyData: 'Không có dữ liệu dao động',
    sensorErrorStream: 'Mất tín hiệu viễn trắc (Không hiển thị dữ liệu giả định)',
  },

  // 10. Giám sát Mô hình & 23 Đặc trưng (Model Monitor)
  model: {
    title: 'Giám sát mô hình học máy',
    activeModel: 'Mô hình chính',
    shadowModel: 'Mô hình đối chiếu (Shadow)',
    currentPrediction: 'Kết quả phân loại hiện tại',
    modelConcordance: 'Độ đồng thuận giữa các mô hình',
    concordanceTimeline: 'Diễn biến đồng thuận theo thời gian',
    agreementByClass: 'Độ đồng thuận theo lớp động học',
    dataDrift: 'Dịch chuyển phân phối dữ liệu (Data Drift)',
    psi: 'Chỉ số ổn định phân phối (PSI)',
    featureRegistry: 'Danh mục 23 đặc trưng động học',
    featureDetails: 'Chi tiết đặc trưng',
    featureId: 'Mã đặc trưng',
    value: 'Giá trị',
    unit: 'Đơn vị',
    status: 'Trạng thái',
    description: 'Mô tả',
    contractVersion: 'Phiên bản hợp đồng dữ liệu',
    groups: {
      all: 'Tất cả 23 đặc trưng',
      roll_60s: 'Góc lắc ngang - Động học ngắn hạn (60 giây)',
      roll_180s: 'Góc lắc ngang - Xu hướng dài hạn & Nghiêng lệch (180 giây)',
      pitch_60s: 'Góc chúi dọc - Động học ngắn hạn (60 giây)',
    },
  },

  // 11. Xác thực & Đăng nhập (Auth)
  auth: {
    loginTitle: 'Đăng nhập Buồng lái',
    loginSub: 'Nhập thông tin định danh sĩ quan trực ca hoặc giám sát viên:',
    registerTitle: 'Đăng ký Tài khoản Trực ca',
    registerSub: 'Tạo tài khoản mới cho sĩ quan buồng lái (Quyền mặc định: Người trực ca - Bảng 3.1):',
    forgotTitle: 'Khôi phục Mật mã Truy cập',
    forgotSub: 'Yêu cầu cấp lại mật mã hoặc xác nhận khóa phần cứng:',
    usernameLabel: 'Tên đăng nhập / Mã sĩ quan (Officer ID)',
    passwordLabel: 'Mật khẩu buồng lái',
    displayNameLabel: 'Họ và tên sĩ quan hiển thị',
    showPass: 'Hiện mật khẩu',
    hidePass: 'Ẩn mật khẩu',
    loginBtn: 'Đăng nhập vào hệ thống',
    registerBtn: 'Đăng ký tài khoản mới',
    forgotBtn: 'Gửi yêu cầu khôi phục',
    backToLogin: '← Quay lại Đăng nhập',
    keyRecovery: 'Khôi phục mật mã',
    needAccount: 'Chưa có tài khoản sĩ quan?',
    haveAccount: 'Đã có tài khoản buồng lái?',
    accessDenied: 'Quyền truy cập bị từ chối',
    accessDeniedDesc: 'Theo quy định phân quyền tại Bảng 3.1 đề cương dự án Smart Vessel Motion Guard v2.0, vai trò Người trực ca (Operator) không có quyền truy cập màn hình này. Chức năng chỉ dành cho Giám sát viên (Supervisor) và Quản trị viên (Admin).',
  },

  // 12. Kịch bản mô phỏng
  scenarios: {
    S0: 'Biển êm (Trạng thái tĩnh)',
    S0b: 'Nghiêng lệch tạm thời (Gió giật)',
    S1: 'Lắc ngang lớn (Sóng dâng)',
    S2: 'Nghiêng lệch kéo dài (Mất cân bằng hàng hóa)',
    S3: 'Biên độ dao động tăng (Hiện tượng cộng hưởng)',
    H1: 'Tình huống kết hợp (Thời tiết nguy hiểm)',
    OFFLINE: 'Mất kết nối thiết bị (>30s)',
    SENSOR_FAULT: 'Lỗi cảm biến phần cứng (I2C NACK)',
  },
};

// Từ điển hiển thị tên tiếng Việt thân thiện cho 23 đặc trưng
export const FEATURE_NAMES_VI: Record<string, { titleVi: string; descVi: string }> = {
  roll_rms_60: {
    titleVi: 'Giá trị hiệu dụng lắc ngang 60s (RMS)',
    descVi: 'Căn bậc hai trung bình bình phương (RMS) góc lắc ngang trong cửa sổ 60 giây',
  },
  roll_std_60: {
    titleVi: 'Độ lệch chuẩn lắc ngang 60s (STD)',
    descVi: 'Độ lệch chuẩn góc lắc ngang biểu thị mức độ tán xạ dao động trong 60 giây',
  },
  roll_mean_60: {
    titleVi: 'Góc lắc ngang trung bình 60s',
    descVi: 'Giá trị trung bình số học góc lắc ngang trong cửa sổ ngắn 60 giây',
  },
  roll_peak_to_peak_60: {
    titleVi: 'Biên độ đỉnh-đáy lắc ngang 60s',
    descVi: 'Chênh lệch độ nghiêng cực đại giữa đỉnh và đáy sóng lắc ngang trong 60 giây',
  },
  roll_abs_p95_60: {
    titleVi: 'Phân vị 95 độ lắc tuyệt đối 60s (P95)',
    descVi: 'Phân vị thứ 95 của góc lắc ngang tuyệt đối, loại trừ nhiễu đột biến trong 60 giây',
  },
  roll_abs_max_60: {
    titleVi: 'Góc lắc ngang cực đại tuyệt đối 60s',
    descVi: 'Giá trị độ nghiêng tuyệt đối lớn nhất ghi nhận được trong 60 giây',
  },
  roll_iqr_60: {
    titleVi: 'Khoảng tứ phân vị lắc ngang 60s (IQR)',
    descVi: 'Độ trải giữa phân vị 75% và 25% của góc lắc ngang trong 60 giây',
  },
  roll_diff_rms_60: {
    titleVi: 'Tốc độ đổi góc lắc ngang 60s (dRoll/dt)',
    descVi: 'Giá trị hiệu dụng vi phân bậc nhất biểu thị vận tốc góc lắc ngang trong 60 giây',
  },
  roll_mean_180: {
    titleVi: 'Góc nghiêng tĩnh trung bình 180s (Heel Offset)',
    descVi: 'Góc nghiêng trung bình trong cửa sổ dài 180 giây, phát hiện tàu lệch mạn kéo dài',
  },
  roll_median_180: {
    titleVi: 'Trung vị góc lắc ngang 180s',
    descVi: 'Điểm trung vị phân bố góc lắc ngang trong cửa sổ quan sát dài 180 giây',
  },
  roll_mean_abs_180: {
    titleVi: 'Độ lệch tuyệt đối trung bình 180s',
    descVi: 'Trung bình số học các giá trị tuyệt đối góc lắc ngang trong 180 giây',
  },
  roll_dominant_sign_ratio_180: {
    titleVi: 'Tỷ lệ nghiêng một mạn ưu thế 180s',
    descVi: 'Tỷ lệ thời gian thân tàu bị nghiêng hẳn về một mạn (trái hoặc phải) trong 180 giây',
  },
  roll_segment_mean_std_180: {
    titleVi: 'Độ biến thiên giữa các phân đoạn 180s',
    descVi: 'Độ lệch chuẩn trung bình giữa các đoạn con 30s, đo mức ổn định xu hướng',
  },
  roll_mean_shift_180: {
    titleVi: 'Độ dịch chuyển trung bình 180s',
    descVi: 'Mức chênh lệch trung bình góc nghiêng giữa nửa đầu và nửa sau cửa sổ 180 giây',
  },
  roll_rms_early_60: {
    titleVi: 'Giá trị hiệu dụng lắc ngang giai đoạn đầu (RMS)',
    descVi: 'RMS góc lắc ngang trong 60 giây đầu tiên của cửa sổ quan sát 180 giây',
  },
  roll_rms_late_60: {
    titleVi: 'Giá trị hiệu dụng lắc ngang giai đoạn sau (RMS)',
    descVi: 'RMS góc lắc ngang trong 60 giây gần nhất của cửa sổ quan sát 180 giây',
  },
  roll_rms_ratio_180: {
    titleVi: 'Tỷ số tăng trưởng biên độ lắc ngang',
    descVi: 'Tỷ số RMS giai đoạn sau chia giai đoạn đầu, chỉ dấu cảnh báo hiện tượng cộng hưởng',
  },
  roll_rms_slope_180: {
    titleVi: 'Hệ số góc xu hướng biên độ lắc ngang',
    descVi: 'Độ dốc đường hồi quy RMS góc lắc ngang theo thời gian trong 180 giây',
  },
  roll_rms_trend_r2_180: {
    titleVi: 'Độ tin cậy xu hướng biên độ lắc ngang (R²)',
    descVi: 'Hệ số xác định R² của đường hồi quy xu hướng RMS trong 180 giây',
  },
  roll_p95_trend_slope_180: {
    titleVi: 'Hệ số góc xu hướng phân vị 95 (P95)',
    descVi: 'Tốc độ tăng trưởng của phân vị 95 độ nghiêng trong cửa sổ dài 180 giây',
  },
  pitch_rms_60: {
    titleVi: 'Giá trị hiệu dụng chúi dọc 60s (RMS)',
    descVi: 'Căn bậc hai trung bình bình phương (RMS) góc nhồi/chúi dọc trong 60 giây',
  },
  pitch_std_60: {
    titleVi: 'Độ lệch chuẩn chúi dọc 60s (STD)',
    descVi: 'Độ lệch chuẩn góc chúi dọc biểu thị mức độ lắc dọc thân tàu trong 60 giây',
  },
  pitch_peak_to_peak_60: {
    titleVi: 'Biên độ đỉnh-đáy chúi dọc 60s',
    descVi: 'Chênh lệch góc chúi lớn nhất giữa ngóc mũi và chúi mũi trong 60 giây',
  },
};

// Định dạng số chuẩn Việt Nam
export function formatNumVi(val: number | null | undefined, decimals = 1): string {
  if (val === null || val === undefined || isNaN(val)) return '—';
  return new Intl.NumberFormat('vi-VN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(val);
}

// Định dạng ngày giờ chuẩn Việt Nam
export function formatDateTimeVi(isoString: string | null | undefined): string {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return new Intl.DateTimeFormat('vi-VN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      timeZone: 'UTC',
    }).format(d) + ' UTC';
  } catch {
    return isoString;
  }
}

// Chuyển đổi nhãn vai trò
export function getRoleNameVi(role: string | null | undefined): string {
  if (!role) return '—';
  return (i18n.roles as Record<string, string>)[role] || role;
}

// Chuyển đổi nhãn trạng thái cảnh báo
export function getAlarmStatusNameVi(status: string | null | undefined): string {
  if (!status) return '—';
  return (i18n.alarmStatus as Record<string, string>)[status] || status;
}

// Chuyển đổi mức cảnh báo
export function getAlarmLevelNameVi(level: string | null | undefined): string {
  if (!level) return 'BÌNH THƯỜNG';
  return (i18n.alarmLevel as Record<string, string>)[level] || level;
}

// Chuyển đổi lớp động học TinyML
export function getRFClassNameVi(cls: string | null | undefined): string {
  if (!cls) return 'BÌNH THƯỜNG';
  return (i18n.rfClass as Record<string, string>)[cls] || cls;
}

// Chuyển đổi trạng thái lệnh
export function getCommandStatusNameVi(st: string | null | undefined): string {
  if (!st) return '—';
  return (i18n.control as Record<string, string>)[st] || st;
}

// Chuyển đổi tên kịch bản
export function getScenarioNameVi(sc: string | null | undefined): string {
  if (!sc) return '—';
  return (i18n.scenarios as Record<string, string>)[sc] || sc;
}
