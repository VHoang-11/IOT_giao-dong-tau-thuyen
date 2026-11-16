from __future__ import annotations

from pathlib import Path
import os
import tempfile

_cache_root = Path(tempfile.gettempdir()) / "svmg-preprocessing-cache"
_cache_root.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(_cache_root / "matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", str(_cache_root))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import welch

from .common import finite_stats


def _vi_style():
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.unicode_minus": False,
                         "figure.autolayout": True, "font.size": 9})


def create_figures(representatives: dict, dataset_summary: dict, output_dir: Path, dpi: int = 140) -> list[dict]:
    """Tạo bộ hình chẩn đoán tiếng Việt từ các mẫu thật đã được xử lý."""
    _vi_style()
    output_dir.mkdir(parents=True, exist_ok=True)
    datasets = [name for name in ("seafar", "hohai", "southampton") if name in representatives]
    paths = []

    for signal, label, unit, fname in (("roll_deg", "Roll", "độ", "roll_raw_processed.png"),
                                       ("pitch_deg", "Pitch", "độ", "pitch_raw_processed.png")):
        fig, axes = plt.subplots(len(datasets), 1, figsize=(10, 2.7 * len(datasets)), squeeze=False)
        for ax, dataset in zip(axes[:, 0], datasets):
            rep = representatives[dataset]
            raw_t = rep["raw_time"]
            raw = rep["raw_signals"].get(signal, np.array([]))
            segment = rep.get("processed")
            if len(raw_t) and len(raw):
                limit = raw_t[0] + 180
                mask = (raw_t >= raw_t[0]) & (raw_t <= limit) & np.isfinite(raw) & np.isfinite(raw_t)
                ax.plot(raw_t[mask] - raw_t[0], raw[mask], label="Trước xử lý", alpha=.58, linewidth=.8)
            if segment is not None and signal in segment.frame:
                out = segment.frame
                out_mask = out["time_seconds"] <= 180.0
                ax.plot(out.loc[out_mask, "time_seconds"], out.loc[out_mask, signal], label="Sau xử lý", linewidth=1.0)
            ax.set_title(f"{dataset.capitalize()} — tín hiệu {label}")
            ax.set_xlabel("Thời gian tương đối trong phiên (s)")
            ax.set_ylabel(f"{label} ({unit})")
            ax.legend(loc="upper right")
            ax.grid(True, alpha=.25)
        fig.suptitle(f"So sánh tín hiệu {label} trước và sau tiền xử lý", fontsize=13)
        path = output_dir / fname
        fig.savefig(path, dpi=dpi)
        plt.close(fig)
        paths.append({"path": str(path), "caption_vi": f"So sánh tín hiệu {label} trước và sau tiền xử lý; dữ liệu đại diện theo từng nguồn."})

    fig, axes = plt.subplots(len(datasets), 1, figsize=(10, 2.7 * len(datasets)), squeeze=False)
    for ax, dataset in zip(axes[:, 0], datasets):
        rep = representatives[dataset]
        times = rep["raw_time"]
        times = times[np.isfinite(times)]
        if len(times) > 1:
            delta = np.diff(times)
            ax.plot(times[1:] - times[0], delta, linewidth=.7, label="Khoảng thời gian giữa mẫu")
            session = rep["raw_session"]
            rate = rep.get("input_rate_hz") or 10.0
            threshold = 1.5 / rate
            ax.axhline(threshold, color="tab:red", linestyle="--", label="Ngưỡng phân đoạn 1,5× chu kỳ")
        ax.set_title(f"{dataset.capitalize()} — khoảng thời gian và phân đoạn")
        ax.set_xlabel("Thời gian tương đối trong phiên (s)")
        ax.set_ylabel("Δt (s)")
        ax.legend(loc="upper right")
        ax.grid(True, alpha=.25)
    fig.suptitle("Phân đoạn dữ liệu theo khoảng gián đoạn thời gian", fontsize=13)
    path = output_dir / "timestamp_gaps_segments.png"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    paths.append({"path": str(path), "caption_vi": "Khoảng cách timestamp trên dữ liệu đầu vào; đường ngang biểu thị ngưỡng gap của cấu hình."})

    fig, axes = plt.subplots(len(datasets), 2, figsize=(11, 3.2 * len(datasets)), squeeze=False)
    for row, dataset in enumerate(datasets):
        summary = dataset_summary[dataset]
        rep = representatives[dataset]
        for col, (signal, label) in enumerate((("roll_deg", "Roll"), ("pitch_deg", "Pitch"))):
            before = rep["raw_pooled"].get(signal, np.array([]))
            after = np.concatenate([s.frame[signal].to_numpy(dtype=float) for s in rep["all_processed"]
                                    if signal in s.frame]) if rep["all_processed"] else np.array([])
            before = before[np.isfinite(before)]
            after = after[np.isfinite(after)]
            ax = axes[row, col]
            if len(before): ax.hist(before, bins=50, density=True, alpha=.45, label="Trước xử lý")
            if len(after): ax.hist(after, bins=50, density=True, alpha=.45, label="Sau xử lý")
            ax.set_title(f"{dataset.capitalize()} — phân bố {label}")
            ax.set_xlabel(f"{label} (độ)")
            ax.set_ylabel("Mật độ")
            ax.legend()
            ax.grid(True, alpha=.2)
    fig.suptitle("Phân bố góc Roll/Pitch trước và sau xử lý", fontsize=13)
    path = output_dir / "signal_distributions.png"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    paths.append({"path": str(path), "caption_vi": "Phân bố Roll/Pitch trước xử lý và sau xử lý; histogram mô tả biến đổi do lọc/lấy mẫu."})

    fig, axes = plt.subplots(len(datasets), 2, figsize=(11, 3.2 * len(datasets)), squeeze=False)
    for row, dataset in enumerate(datasets):
        rep = representatives[dataset]
        for col, (signal, label) in enumerate((("roll_deg", "Roll"), ("pitch_deg", "Pitch"))):
            ax = axes[row, col]
            segment = rep.get("processed")
            pair = segment.aligned.get(signal) if segment is not None else None
            raw = pair["raw_full"] if pair else np.array([])
            filtered = pair["filtered_full"] if pair else np.array([])
            processed = segment.frame[signal].to_numpy(dtype=float) if segment is not None and signal in segment.frame else np.array([])
            fs_in = rep.get("input_rate_hz") or 10.0
            if len(raw) >= 32:
                f0, p0 = welch(raw, fs=fs_in, nperseg=min(4096, len(raw)))
                ax.semilogy(f0, p0, label="Phổ tín hiệu nguồn", alpha=.7)
            if len(filtered) >= 32 and rep.get("filter_applied"):
                ff, pf = welch(filtered, fs=fs_in, nperseg=min(4096, len(filtered)))
                ax.semilogy(ff, pf, label="Sau lọc tại Sampling Rate nguồn", alpha=.7)
            if len(processed) >= 32:
                fs = dataset_summary[dataset]["sampling_rate_after_hz_median"] or 10.0
                f1, p1 = welch(processed, fs=fs, nperseg=min(4096, len(processed)))
                ax.semilogy(f1, p1, label="Phổ sau xử lý", alpha=.75)
                ax.axvline(fs / 2, color="tab:red", linestyle="--", label="Nyquist đích")
            ax.set_xlim(left=0)
            ax.set_title(f"{dataset.capitalize()} — phổ {label}")
            ax.set_xlabel("Tần số (Hz)")
            ax.set_ylabel("Mật độ phổ công suất (độ²/Hz)")
            ax.legend(fontsize=8)
            ax.grid(True, alpha=.2)
    fig.suptitle("Đánh giá lọc Anti-aliasing và giảm Sampling Rate", fontsize=13)
    path = output_dir / "resampling_frequency_diagnostics.png"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    paths.append({"path": str(path), "caption_vi": "Mật độ phổ công suất trước/sau; đường Nyquist cho lưới đầu ra."})
    return paths
