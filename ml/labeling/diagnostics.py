from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def create_diagnostics(windows: dict[str, pd.DataFrame], processed_root: Path, output_root: Path) -> list[str]:
    output_root.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.unicode_minus": False, "font.size": 9})
    paths = []
    for dataset, frame in windows.items():
        if frame.empty:
            continue
        row = frame.sort_values(["session_id", "window_end_seconds"], kind="stable").iloc[-1]
        candidates = sorted(processed_root.joinpath(dataset).glob("**/timeseries.parquet"))
        match = None
        for path in candidates:
            head = pd.read_parquet(path, columns=["session_id", "segment_id"]).iloc[0]
            if str(head.session_id) == str(row.session_id) and str(head.segment_id) == str(row.segment_id):
                match = path
                break
        if match is None:
            continue
        signal = pd.read_parquet(match, columns=["time_seconds", "roll_deg", "pitch_deg"])
        end = float(row.window_end_seconds)
        signal = signal[(signal.time_seconds > end - 180.0) & (signal.time_seconds <= end)]
        if signal.empty:
            continue
        fig, axes = plt.subplots(2, 1, figsize=(10, 5), sharex=True)
        axes[0].plot(signal.time_seconds, signal.roll_deg, linewidth=.8, color="#2563eb")
        axes[0].set_title(f"{dataset.capitalize()} — tín hiệu Roll trong cửa sổ trailing 180 giây")
        axes[0].set_ylabel("Roll (độ)")
        axes[1].plot(signal.time_seconds, signal.pitch_deg, linewidth=.8, color="#ea580c")
        axes[1].set_title("Tín hiệu Pitch trong cùng cửa sổ")
        axes[1].set_ylabel("Pitch (độ)")
        axes[1].set_xlabel("Thời gian tương đối của segment (giây)")
        for axis in axes:
            axis.axvline(end - 180, color="black", linestyle="--", linewidth=.8, label="Bắt đầu cửa sổ")
            axis.axvline(end, color="green", linestyle=":", linewidth=.8, label="Endpoint causal")
            axis.grid(alpha=.2)
            axis.legend(loc="best")
        fig.suptitle(f"Minh họa thực tế: {row.session_id} / {row.segment_id}; nhãn: chưa xác định")
        fig.tight_layout()
        target = output_root / f"{dataset}_representative_window.png"
        fig.savefig(target, dpi=120)
        plt.close(fig)
        paths.append(target.as_posix())

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.scatter(frame.roll_mean_180, frame.roll_std_60, s=9, alpha=.45, color="#2563eb")
        ax.set_title(f"{dataset.capitalize()} — offset và dao động mô tả, chưa gán ngưỡng")
        ax.set_xlabel("Trung bình Roll 180 giây (độ)")
        ax.set_ylabel("Độ lệch chuẩn Roll 60 giây (độ)")
        ax.grid(alpha=.2)
        fig.tight_layout()
        target = output_root / f"{dataset}_offset_vs_oscillation.png"
        fig.savefig(target, dpi=120)
        plt.close(fig)
        paths.append(target.as_posix())
    if windows:
        fig, ax = plt.subplots(figsize=(9, 5))
        data, labels = [], []
        for dataset, frame in windows.items():
            values = pd.to_numeric(frame["roll_std_60"], errors="coerce").dropna().to_numpy()
            data.append(values)
            labels.append(dataset.capitalize())
        ax.boxplot(data, tick_labels=labels, showfliers=False)
        ax.set_title("Phân bố mô tả độ lệch chuẩn Roll theo nguồn")
        ax.set_ylabel("Độ lệch chuẩn Roll 60 giây (độ)")
        ax.grid(axis="y", alpha=.2)
        fig.tight_layout()
        target = output_root / "comparison_roll_std.png"
        fig.savefig(target, dpi=120)
        plt.close(fig)
        paths.append(target.as_posix())
    return paths
