"""Thiết lập chung cho mọi test.

- Cho phép `import schema`, `import db`... như khi chạy trong src/.
- Mỗi test dùng một cơ sở dữ liệu TẠM (không đụng data/app.db thật).
- Tắt gọi AI: test phải chạy được không cần mạng, không cần API key, không tốn tiền.
"""
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

HOA_DON_MAU = {
    "loai_hoa_don": "GTGT",
    "ky_hieu": "C26TKK",
    "so_hoa_don": "3932",
    "ngay_lap": "2026-01-02",
    "ten_nguoi_ban": "CÔNG TY CỔ PHẦN DỊCH VỤ KỸ THUẬT AN KHANG",
    "mst_nguoi_ban": "0911417075",
    "ten_nguoi_mua": "CÔNG TY TNHH GIẢI PHÁP PHẦN MỀM SAO MAI",
    "mst_nguoi_mua": "0645568151",
    "tong_tien_chua_thue": 111472000,
    "tien_thue": 11147200,
    "tong_thanh_toan": 122619200,
    "dong_hang": [
        {"ten_hang": "Bàn làm việc gỗ 1m2", "don_vi_tinh": "cái", "so_luong": 8,
         "don_gia": 3030000, "thanh_tien": 24240000, "thue_suat": "10%"},
        {"ten_hang": "Dịch vụ tư vấn thuế tháng 10", "don_vi_tinh": "gói", "so_luong": 20,
         "don_gia": 4279000, "thanh_tien": 85580000, "thue_suat": "10%"},
        {"ten_hang": "Giấy in A4 70gsm", "don_vi_tinh": "ram", "so_luong": 14,
         "don_gia": 118000, "thanh_tien": 1652000, "thue_suat": "10%"},
    ],
}


@pytest.fixture
def hd_dict():
    """Một hoá đơn hợp lệ dạng dict — mỗi test nhận bản sao riêng để sửa thoải mái."""
    return copy.deepcopy(HOA_DON_MAU)


@pytest.fixture
def db_tam(tmp_path, monkeypatch):
    """Cơ sở dữ liệu SQLite tạm, tự xoá sau test."""
    import db
    import llm
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(llm, "co_api", lambda: False)  # không bao giờ gọi AI trong test
    db.khoi_tao()
    return db
