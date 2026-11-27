/**
 * SMART VESSEL MOTION GUARD (SVMG) - BỘ TỪ ĐIỂN & VIỆT HÓA MOBILE (i18n)
 * Đồng bộ trực tiếp với frontend/src/i18n/vi.ts trên Web.
 */

export const i18n = {
  nav: {
    overview: 'Tổng quan',
    motion: 'Chuyển động',
    alarms: 'Cảnh báo',
    more: 'Thêm',
    control: 'Trung tâm điều khiển',
    reports: 'Báo cáo hành trình',
    replay: 'Phát lại và đánh giá',
    health: 'Tình trạng thiết bị',
    model: 'Giám sát mô hình',
    logout: 'Đăng xuất',
  },

  roles: {
    Operator: 'Sĩ quan trực ca',
    Supervisor: 'Giám sát viên',
    Admin: 'Quản trị viên',
  },

  maritime: {
    roll: 'Góc lắc ngang',
    pitch: 'Góc chúi dọc',
    port: 'Mạn trái',
    stbd: 'Mạn phải',
    bowUp: 'Ngóc mũi',
    bowDown: 'Chúi mũi',
    even: 'Cân bằng',
    level: 'Mức chuẩn',
    waterline: 'Đường mực nước tham chiếu',
    horizon: 'Đường chân trời',
    isoView: 'Phối cảnh',
    rollView: 'Mặt cắt ngang',
    pitchView: 'Mặt cắt dọc',
    mai: 'Chỉ số bất thường MAI',
  },

  rfClass: {
    NORMAL: 'Bình thường',
    HIGH_ROLL: 'Lắc ngang mạnh',
    PERSISTENT_OFFSET: 'Nghiêng lệch kéo dài',
    AMPLITUDE_GROWTH: 'Biên độ dao động tăng',
    UNKNOWN: 'Chưa xác định',
    FAULT: 'Lỗi cảm biến',
  },

  alarmLevel: {
    NORMAL: 'Bình thường',
    CAUTION: 'Cảnh giác',
    WARNING: 'Cảnh báo',
    CRITICAL: 'Nguy cấp',
    UNKNOWN: 'Không xác định',
    SAFE: 'An toàn',
  },

  alarmStatus: {
    RAISED: 'Đang phát',
    ACKED: 'Đã xác nhận',
    CLEARED: 'Đã kết thúc',
    SENT: 'Đã gửi',
    DELIVERED: 'Đã nhận',
    APPLIED: 'Đã áp dụng',
    REJECTED: 'Bị từ chối',
    TIMEOUT: 'Quá thời gian',
  },

  system: {
    ONLINE: 'Đang kết nối',
    OFFLINE: 'Mất kết nối',
    SENSOR_FAULT: 'Lỗi cảm biến',
    UNKNOWN: 'Chưa xác định',
    SIMULATION: 'Dữ liệu mô phỏng',
    SENSOR: 'Cảm biến phần cứng',
    VALID: 'Hợp lệ',
    WARNING: 'Cảnh giác',
    INVALID: 'Không hợp lệ',
    MISSING: 'Thiếu dữ liệu',
    NOT_APPLICABLE: 'Không khả dụng',
  },

  scenarios: {
    S0: 'Biển êm',
    S0b: 'Nghiêng rồi hồi phục',
    S1: 'Lắc ngang lớn',
    S2: 'Nghiêng lệch kéo dài',
    S3: 'Biên độ tăng dần',
    H1: 'Kết hợp nguy hiểm',
    OFFLINE: 'Mất kết nối thiết bị',
    UNKNOWN: 'Không xác định',
    SENSOR_FAULT: 'Lỗi cảm biến phần cứng',
  },
};

export const FEATURE_NAMES_VI: Record<string, { titleVi: string; descVi: string }> = {
  roll_rms_60: {
    titleVi: 'Giá trị hiệu dụng lắc ngang 60s (RMS)',
    descVi: 'Căn bậc hai trung bình bình phương (RMS) góc lắc ngang trong cửa sổ 60 giây.',
  },
  roll_std_60: {
    titleVi: 'Độ lệch chuẩn lắc ngang 60s (STD)',
    descVi: 'Độ lệch chuẩn góc lắc ngang biểu thị mức độ tán xạ dao động trong 60 giây.',
  },
  roll_mean_60: {
    titleVi: 'Góc lắc ngang trung bình 60s',
    descVi: 'Giá trị trung bình số học góc lắc ngang trong cửa sổ ngắn 60 giây.',
  },
  roll_peak_to_peak_60: {
    titleVi: 'Biên độ đỉnh-đáy lắc ngang 60s',
    descVi: 'Chênh lệch độ nghiêng cực đại giữa đỉnh và đáy sóng lắc ngang trong 60 giây.',
  },
  roll_abs_p95_60: {
    titleVi: 'Phân vị 95 độ lắc tuyệt đối 60s (P95)',
    descVi: 'Phân vị thứ 95 của góc lắc ngang tuyệt đối, loại trừ nhiễu đột biến trong 60 giây.',
  },
  roll_abs_max_60: {
    titleVi: 'Góc lắc ngang cực đại tuyệt đối 60s',
    descVi: 'Giá trị độ nghiêng tuyệt đối lớn nhất ghi nhận được trong 60 giây.',
  },
  roll_iqr_60: {
    titleVi: 'Khoảng tứ phân vị lắc ngang 60s (IQR)',
    descVi: 'Độ trải giữa phân vị 75% và 25% của góc lắc ngang trong 60 giây.',
  },
  roll_diff_rms_60: {
    titleVi: 'Tốc độ đổi góc lắc ngang 60s',
    descVi: 'Giá trị hiệu dụng vi phân bậc nhất biểu thị vận tốc góc lắc ngang trong 60 giây.',
  },
  roll_mean_180: {
    titleVi: 'Góc nghiêng tĩnh trung bình 180s',
    descVi: 'Góc nghiêng trung bình trong cửa sổ dài 180 giây, phát hiện tàu lệch mạn kéo dài.',
  },
  roll_median_180: {
    titleVi: 'Trung vị góc lắc ngang 180s',
    descVi: 'Điểm trung vị phân bố góc lắc ngang trong cửa sổ quan sát dài 180 giây.',
  },
  roll_mean_abs_180: {
    titleVi: 'Độ lệch tuyệt đối trung bình 180s',
    descVi: 'Trung bình số học các giá trị tuyệt đối góc lắc ngang trong 180 giây.',
  },
  roll_dominant_sign_ratio_180: {
    titleVi: 'Tỷ lệ nghiêng một mạn ưu thế 180s',
    descVi: 'Tỷ lệ thời gian thân tàu bị nghiêng hẳn về một mạn (trái hoặc phải) trong 180 giây.',
  },
  roll_segment_mean_std_180: {
    titleVi: 'Độ biến thiên giữa các phân đoạn 180s',
    descVi: 'Độ lệch chuẩn trung bình giữa các đoạn con 30s, đo mức ổn định xu hướng.',
  },
  roll_mean_shift_180: {
    titleVi: 'Độ dịch chuyển trung bình 180s',
    descVi: 'Mức chênh lệch trung bình góc nghiêng giữa nửa đầu và nửa sau cửa sổ 180 giây.',
  },
  roll_rms_early_60: {
    titleVi: 'Giá trị hiệu dụng lắc ngang giai đoạn đầu',
    descVi: 'RMS góc lắc ngang trong 60 giây đầu tiên của cửa sổ quan sát 180 giây.',
  },
  roll_rms_late_60: {
    titleVi: 'Giá trị hiệu dụng lắc ngang giai đoạn sau',
    descVi: 'RMS góc lắc ngang trong 60 giây gần nhất của cửa sổ quan sát 180 giây.',
  },
  roll_rms_ratio_180: {
    titleVi: 'Tỷ số tăng trưởng biên độ lắc ngang',
    descVi: 'Tỷ số RMS giai đoạn sau chia giai đoạn đầu, chỉ dấu cảnh báo hiện tượng cộng hưởng.',
  },
  roll_rms_slope_180: {
    titleVi: 'Hệ số góc xu hướng biên độ lắc ngang',
    descVi: 'Độ dốc đường hồi quy RMS góc lắc ngang theo thời gian trong 180 giây.',
  },
  roll_rms_trend_r2_180: {
    titleVi: 'Độ tin cậy xu hướng biên độ lắc ngang (R²)',
    descVi: 'Hệ số xác định R² của đường hồi quy xu hướng RMS trong 180 giây.',
  },
  roll_p95_trend_slope_180: {
    titleVi: 'Hệ số góc xu hướng phân vị 95 (P95)',
    descVi: 'Tốc độ tăng trưởng của phân vị 95 độ nghiêng trong cửa sổ dài 180 giây.',
  },
  pitch_rms_60: {
    titleVi: 'Giá trị hiệu dụng chúi dọc 60s (RMS)',
    descVi: 'Căn bậc hai trung bình bình phương (RMS) góc nhồi/chúi dọc trong 60 giây.',
  },
  pitch_std_60: {
    titleVi: 'Độ lệch chuẩn chúi dọc 60s (STD)',
    descVi: 'Độ lệch chuẩn góc chúi dọc biểu thị mức độ lắc dọc thân tàu trong 60 giây.',
  },
  pitch_peak_to_peak_60: {
    titleVi: 'Biên độ đỉnh-đáy chúi dọc 60s',
    descVi: 'Chênh lệch góc chúi lớn nhất giữa ngóc mũi và chúi mũi trong 60 giây.',
  },
};

export function getRoleNameVi(role: string | null | undefined): string {
  if (!role) return '—';
  return (i18n.roles as Record<string, string>)[role] || role;
}

export function getAlarmStatusNameVi(status: string | null | undefined): string {
  if (!status) return '—';
  return (i18n.alarmStatus as Record<string, string>)[status] || status;
}

export function getAlarmLevelNameVi(level: string | null | undefined): string {
  if (!level) return 'Bình thường';
  return (i18n.alarmLevel as Record<string, string>)[level] || level;
}

export function getRFClassNameVi(cls: string | null | undefined): string {
  if (!cls) return 'Bình thường';
  return (i18n.rfClass as Record<string, string>)[cls] || cls;
}

export function getCommandStatusNameVi(st: string | null | undefined): string {
  if (!st) return '—';
  return (i18n.alarmStatus as Record<string, string>)[st] || st;
}

export function getScenarioNameVi(sc: string | null | undefined): string {
  if (!sc) return '—';
  return (i18n.scenarios as Record<string, string>)[sc] || sc;
}
