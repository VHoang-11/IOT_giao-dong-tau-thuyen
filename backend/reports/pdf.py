"""Dung PDF bao cao chuyen di bang ReportLab, font DejaVu (co du dau tieng Viet).

- Moi chuoi dong deu duoc escape: Paragraph hieu cu phap giong XML nen '<' hoac '&' se lam hong ca tai lieu.
- Khong ve duong nguong nao len bieu do: nguong chi la tham so demo, khong de nguoi doc hieu thanh nguong an toan.
"""
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional
from xml.sax.saxutils import escape

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.schemas.voyage import Distribution, ReportSummary

FONT_DIR = Path(__file__).resolve().parent / "fonts"
FONT, FONT_BOLD = "DejaVu", "DejaVu-Bold"
_registered = False


def register_fonts() -> None:
    global _registered
    if _registered:
        return
    pdfmetrics.registerFont(TTFont(FONT, str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(FONT, normal=FONT, bold=FONT_BOLD, italic=FONT, boldItalic=FONT_BOLD)
    _registered = True


def _e(v) -> str:
    return escape("" if v is None else str(v))


def _fmt(v: Optional[float], digits: int = 2, unit: str = "") -> str:
    return "—" if v is None else f"{v:.{digits}f}{unit}"


def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{v * 100:.1f}%"


def _dt(v: Optional[datetime]) -> str:
    return "—" if v is None else v.strftime("%Y-%m-%d %H:%M:%S UTC")


def _dur(seconds: Optional[float]) -> str:
    if seconds is None:
        return "—"
    s = int(seconds)
    return f"{s // 3600} giờ {s % 3600 // 60} phút {s % 60} giây"


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle("base", fontName=FONT, fontSize=9.5, leading=13)
    return {
        "title": ParagraphStyle("title", parent=base, fontName=FONT_BOLD, fontSize=18, leading=22, spaceAfter=4),
        "h2": ParagraphStyle("h2", parent=base, fontName=FONT_BOLD, fontSize=12, leading=16, spaceBefore=10, spaceAfter=4),
        "body": base,
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=10.5, textColor=colors.HexColor("#444444")),
        "banner": ParagraphStyle("banner", parent=base, fontName=FONT_BOLD, fontSize=11, leading=15,
                                 textColor=colors.white),
        "cell": ParagraphStyle("cell", parent=base, fontSize=9, leading=12),
    }


def _table(rows: list[list[str]], st: dict[str, ParagraphStyle], widths: list[float], header: bool = False) -> Table:
    data = [[Paragraph(_e(c), st["cell"]) for c in r] for r in rows]
    t = Table(data, colWidths=widths, hAlign="LEFT")
    style = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BBBBBB")),
             ("VALIGN", (0, 0), (-1, -1), "TOP"),
             ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")))
    else:
        style.append(("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F6F6F6")))
    t.setStyle(TableStyle(style))
    return t


def _dist_rows(d: Distribution) -> list[list[str]]:
    rows = [["Lớp", "Số mẫu", "Tỉ lệ"]]
    rows += [[k, str(v), _pct(d.share.get(k))] for k, v in d.counts.items()]
    return rows if len(rows) > 1 else [["Lớp", "Số mẫu", "Tỉ lệ"], ["(không có dữ liệu)", "—", "—"]]


def _chart(series: list[tuple[float, float]]) -> Optional[Drawing]:
    if len(series) < 2:
        return None
    w, h = 170 * mm, 62 * mm
    d = Drawing(w, h)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 38, 28, w - 55, h - 42
    lp.data = [[(x / 60.0, y) for x, y in series]]  # truc x tinh bang phut
    lp.lines[0].strokeColor = colors.HexColor("#1F5FBF")
    lp.lines[0].strokeWidth = 0.8
    for axis in (lp.xValueAxis, lp.yValueAxis):
        axis.labels.fontName = FONT
        axis.labels.fontSize = 7
    lp.xValueAxis.labelTextFormat = "%.0f"
    lp.yValueAxis.labelTextFormat = "%.1f"
    d.add(lp)
    d.add(String(38, h - 10, "Góc roll theo thời gian (chỉ các mẫu sensor_ok = true)", fontName=FONT_BOLD, fontSize=8.5))
    d.add(String(w / 2 - 40, 6, "Thời gian từ mẫu đầu (phút)", fontName=FONT, fontSize=7.5))
    d.add(String(2, h / 2, "roll (°)", fontName=FONT, fontSize=7.5))
    return d


def build_pdf(s: ReportSummary, series: list[tuple[float, float]]) -> bytes:
    register_fonts()
    st = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=18 * mm, title=f"Báo cáo chuyến đi {s.voyage.voyage_id}",
                            author="Smart Vessel Motion Guard")
    full = A4[0] - 36 * mm
    story: list = [Paragraph("Báo cáo chuyến đi", st["title"]),
                   Paragraph(f"Chuyến <b>{_e(s.voyage.voyage_id)}</b> · Thiết bị <b>{_e(s.voyage.device_id)}</b>", st["body"]),
                   Spacer(1, 6)]

    colour = {"SIMULATION": "#B45F06", "SENSOR": "#1B6E3C", "MIXED": "#9C1C1C"}.get(s.source_label, "#555555")
    banner = {"SIMULATION": "DỮ LIỆU MÔ PHỎNG (SIMULATION)", "SENSOR": "DỮ LIỆU TỪ CẢM BIẾN (SENSOR)",
              "MIXED": "DỮ LIỆU TRỘN SENSOR + SIMULATION", "UNKNOWN": "CHƯA CÓ DỮ LIỆU"}[s.source_label]
    if s.provisional:
        banner += "  ·  SỐ LIỆU TẠM THỜI (chuyến đang chạy)"
    bt = Table([[Paragraph(_e(banner), st["banner"])]], colWidths=[full])
    bt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(colour)),
                            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    story += [bt, Spacer(1, 4), Paragraph(_e(s.disclaimer), st["small"])]

    w2 = [full * 0.42, full * 0.58]
    v = s.voyage
    story += [Paragraph("1. Thông tin chuyến đi", st["h2"]), _table([
        ["Trạng thái", "ĐANG CHẠY (tạm thời)" if s.provisional else "ĐÃ KẾT THÚC"],
        ["Bắt đầu", f"{_dt(v.started_at)} bởi {v.started_by}"],
        ["Kết thúc", f"{_dt(v.ended_at)}" + (f" bởi {v.ended_by}" if v.ended_by else "")],
        ["Mẫu đầu / mẫu cuối (giờ server)", f"{_dt(s.first_sample_at)}  →  {_dt(s.last_sample_at)}"],
        ["Thời lượng có dữ liệu", _dur(s.duration_s)],
        ["Nguồn dữ liệu", ", ".join(s.source_modes) or "—"],
    ], st, w2)]

    q = s.data_quality
    story += [Paragraph("2. Chất lượng dữ liệu", st["h2"]), _table([
        ["Số bản tin nhận được", str(q.samples)],
        ["Số bản tin kỳ vọng (theo dải seq từng lần khởi động)", str(q.expected_samples)],
        ["Thiếu", str(q.missing_samples)],
        ["Tỉ lệ nhận", _pct(q.received_rate)],
        ["Số lần khởi động thiết bị (boot_id)", str(q.boots)],
        ["Mẫu lỗi cảm biến (sensor_ok = false, đã loại khỏi mục 3)", str(q.sensor_fault_samples)],
    ], st, w2)]

    m = s.motion
    story += [Paragraph("3. Chuyển động (chỉ mẫu sensor_ok = true)", st["h2"]), _table([
        ["Số mẫu dùng để thống kê", str(m.samples_used)],
        ["|roll| lớn nhất", _fmt(m.max_abs_roll_deg, 2, "°")],
        ["|roll| phân vị 95 (nearest-rank)", _fmt(m.p95_abs_roll_deg, 2, "°")],
        ["RMS roll trung bình (do thiết bị tính)", _fmt(m.mean_rms_roll_deg, 2, "°")],
        ["|pitch| lớn nhất", _fmt(m.max_abs_pitch_deg, 2, "°")],
        ["|độ nghiêng lệch| lớn nhất", _fmt(m.max_abs_heel_offset_deg, 2, "°")],
    ], st, w2)]
    chart = _chart(series)
    story += [Spacer(1, 6), chart] if chart else [Spacer(1, 4), Paragraph("Không đủ dữ liệu để vẽ biểu đồ.", st["small"])]

    story += [Paragraph("4. Phân loại chuyển động (theo số mẫu)", st["h2"]), Paragraph("Random Forest trên thiết bị", st["body"]),
              _table(_dist_rows(s.class_rf), st, [full * 0.5, full * 0.25, full * 0.25], header=True),
              Spacer(1, 4), Paragraph("Baseline B", st["body"]),
              _table(_dist_rows(s.class_baseline_b), st, [full * 0.5, full * 0.25, full * 0.25], header=True),
              Spacer(1, 3), Paragraph(f"Tỉ lệ RF trùng Baseline B: <b>{_pct(s.rf_baseline_agreement_rate)}</b> "
                                      "(chỉ tính các mẫu có cả hai nhãn).", st["body"])]

    a = s.alarms
    story += [Paragraph("5. Cảnh báo", st["h2"]), _table([
        ["Tổng số cảnh báo", str(a.total)],
        ["Theo mức cao nhất", ", ".join(f"{k}: {n}" for k, n in sorted(a.by_max_level.items())) or "—"],
        ["Số cảnh báo bị leo thang", f"{a.escalated} ({_pct(a.escalation_rate)})"],
        ["MTTA (thời gian trung bình đến khi có người xác nhận)", _fmt(a.mtta_s, 1, " giây")],
        ["Đã đánh giá (đúng/sai/chưa rõ)", f"{a.labeled} ({_pct(a.label_coverage)} số cảnh báo)"],
        ["Chi tiết nhãn", ", ".join(f"{k}: {n}" for k, n in sorted(a.by_label.items())) or "—"],
        ["Tỉ lệ cảnh báo sai (SAI / (ĐÚNG + SAI))", _pct(a.false_alarm_rate)],
        ["Cảnh báo sai mỗi giờ", _fmt(s.false_alarms_per_hour, 2)],
    ], st, w2),
        Paragraph("Cảnh báo ‘chưa rõ’ và cảnh báo chưa đánh giá không tính vào tỉ lệ cảnh báo sai. "
                  "Dấu ‘—’ nghĩa là chưa đủ dữ liệu đánh giá để kết luận, không phải bằng 0.", st["small"])]

    story += [Paragraph("6. Mức cảnh báo ghi nhận trong telemetry (theo số mẫu)", st["h2"]),
              _table(_dist_rows(s.alarm_levels), st, [full * 0.5, full * 0.25, full * 0.25], header=True),
              Paragraph("7. Lệnh điều khiển trong khoảng thời gian có dữ liệu", st["h2"]),
              _table([["Tổng số lệnh", str(s.commands.total)],
                      ["Theo trạng thái", ", ".join(f"{k}: {n}" for k, n in sorted(s.commands.by_state.items())) or "—"]],
                     st, w2)]

    story += [Paragraph("8. Ghi chú về số liệu", st["h2"])]
    story += [Paragraph("• " + _e(n), st["body"]) for n in s.notes] or [Paragraph("Không có ghi chú.", st["body"])]
    story += [Spacer(1, 6), Paragraph(f"Báo cáo tạo lúc {_dt(s.generated_at)}. Dấu vân tay dữ liệu (SHA-256 của telemetry.csv, "
                                      f"{s.telemetry_rows} dòng):<br/>{_e(s.telemetry_csv_sha256)}", st["small"])]

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont(FONT, 7.5)
        canvas.setFillColor(colors.HexColor("#555555"))
        canvas.drawString(18 * mm, 10 * mm, "SVMG — nguyên mẫu nghiên cứu/đào tạo, không phải hệ thống an toàn hàng hải")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Trang {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
