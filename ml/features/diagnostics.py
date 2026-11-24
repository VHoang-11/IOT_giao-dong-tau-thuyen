from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .spec import FEATURE_NAMES, VALIDITY_STATUSES


def create_feature_figures(dataset_values: dict[str, pd.DataFrame], dataset_validity: dict[str, list[dict]],
                           output_dir: Path, dpi: int = 120) -> list[dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "axes.unicode_minus": False,
                         "figure.autolayout": True, "font.size": 9})
    colors = {"seafar": "#2563eb", "hohai": "#ea580c", "southampton": "#059669"}
    features = ["roll_rms_60", "pitch_rms_60", "roll_mean_180", "roll_rms_ratio_180",
                "roll_period_est_180", "roll_zero_crossings_180"]
    figure_paths = []
    fig, axes = plt.subplots(2, 3, figsize=(12, 7))
    for ax, feature in zip(axes.flat, features):
        for dataset, frame in dataset_values.items():
            values = pd.to_numeric(frame.get(feature, pd.Series(dtype=float)), errors="coerce").to_numpy(float)
            values = values[np.isfinite(values)]
            if len(values):
                ax.hist(values, bins=32, density=True, alpha=.38,
                        color=colors.get(dataset), label=dataset.capitalize())
        ax.set_title(feature)
        ax.set_xlabel("Giá trị feature theo đơn vị đặc tả")
        ax.set_ylabel("Mật độ chuẩn hóa")
        ax.grid(True, alpha=.2)
    axes.flat[0].legend()
    fig.suptitle("Phân bố feature hợp lệ theo nguồn dữ liệu")
    path = output_dir / "feature_distribution_overview.png"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    figure_paths.append({"path": path, "caption_vi": "Phân bố của sáu feature đại diện; chỉ dùng giá trị có validity VALID."})

    counts = {dataset: {status: 0 for status in VALIDITY_STATUSES} for dataset in dataset_validity}
    for dataset, records in dataset_validity.items():
        for validity in records:
            for feature in FEATURE_NAMES:
                counts[dataset][validity[feature]["status"]] += 1
    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(counts))
    width = .12
    for idx, status in enumerate(VALIDITY_STATUSES):
        values = [counts[dataset][status] for dataset in counts]
        ax.bar(x + (idx - (len(VALIDITY_STATUSES)-1)/2) * width, values, width, label=status)
    ax.set_xticks(x, [name.capitalize() for name in counts])
    ax.set_ylabel("Số trạng thái feature (đếm theo feature-row)")
    ax.set_title("Trạng thái validity trên ba nguồn")
    ax.legend(fontsize=7, ncol=2)
    ax.grid(True, axis="y", alpha=.2)
    path = output_dir / "feature_validity_by_dataset.png"
    fig.savefig(path, dpi=dpi)
    plt.close(fig)
    figure_paths.append({"path": path, "caption_vi": "Số trạng thái validity của các feature; MISSING và UNVERIFIED được tách riêng."})
    return figure_paths
