from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PILOT = Path(__file__).resolve().parents[3] / "ml/data/labels/annotation_pilot/batches/pilot_29.csv"


@pytest.mark.skipif(not PILOT.is_file(), reason="Pilot artifacts (gitignored, từ dữ liệu thật) không có trong môi trường này.")
def test_review_app_renders_selected_hohai_plot_from_validated_image_bytes():
    repo_root = Path(__file__).resolve().parents[3]
    app_path = repo_root / "ml/labeling/review_app.py"
    app = AppTest.from_file(str(app_path), default_timeout=30).run()

    assert not app.exception
    assert app.sidebar.metric[0].value == "29"
    assert app.get("subheader")[0].value == "Tín hiệu Roll/Pitch và lịch sử"
    images = app.get("imgs")
    assert len(images) == 1
    rendered_image = images[0].proto.imgs[0]
    assert rendered_image.url.startswith("data:image/png;base64,")
    assert rendered_image.caption.startswith("Tín hiệu đã preprocessing")
    assert "Không thể hiển thị signal plot" not in [error.value for error in app.error]
