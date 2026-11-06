"""Bước 2: Đọc hoá đơn điện tử dạng XML — KHÔNG dùng AI.

Bài học quan trọng nhất của thiết kế hệ thống LLM: dữ liệu đã có cấu trúc
(XML) thì đọc bằng code thường — nhanh, miễn phí, đúng 100%. Chỉ dùng LLM
cho chứng từ không có cấu trúc (PDF scan, ảnh chụp).

Cấu trúc thẻ theo mẫu XML hoá đơn điện tử phổ biến (TTChung, NBan, NMua,
DSHHDVu, TToan...). Mỗi nhà cung cấp hoá đơn có thể khác đôi chút, nên code
tìm thẻ theo tên ở bất kỳ độ sâu nào thay vì đường dẫn cố định.
"""
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

from schema import DongHang, HoaDon


def _bo_namespace(root: ET.Element) -> ET.Element:
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _chu(node: ET.Element | None, duong_dan: str) -> str | None:
    if node is None:
        return None
    el = node.find(duong_dan)
    return el.text.strip() if el is not None and el.text else None


def _so(text: str | None) -> float | None:
    return float(text) if text not in (None, "") else None


def _tien(text: str | None) -> int:
    return round(float(text)) if text else 0


def doc_xml(path: str | Path) -> HoaDon:
    root = _bo_namespace(ET.parse(path).getroot())
    tt = root.find(".//TTChung")
    ban = root.find(".//NBan")
    mua = root.find(".//NMua")
    ttoan = root.find(".//TToan")

    dong_hang = [
        DongHang(
            ten_hang=_chu(h, "THHDVu") or "",
            don_vi_tinh=_chu(h, "DVTinh"),
            so_luong=_so(_chu(h, "SLuong")),
            don_gia=_tien(_chu(h, "DGia")) if _chu(h, "DGia") else None,
            thanh_tien=_tien(_chu(h, "ThTien")),
            thue_suat=_chu(h, "TSuat"),
        )
        for h in root.iter("HHDVu")
    ]

    tieu_de = (_chu(tt, "THDon") or "").lower()
    loai = "GTGT" if "giá trị gia tăng" in tieu_de else ("BAN_HANG" if "bán hàng" in tieu_de else None)

    return HoaDon(
        loai_hoa_don=loai,
        ky_hieu=_chu(tt, "KHHDon"),
        so_hoa_don=_chu(tt, "SHDon") or "",
        ngay_lap=date.fromisoformat(_chu(tt, "NLap")),
        ten_nguoi_ban=_chu(ban, "Ten") or "",
        mst_nguoi_ban=_chu(ban, "MST") or "",
        ten_nguoi_mua=_chu(mua, "Ten"),
        mst_nguoi_mua=_chu(mua, "MST"),
        tong_tien_chua_thue=_tien(_chu(ttoan, "TgTCThue")),
        tien_thue=_tien(_chu(ttoan, "TgTThue")),
        tong_thanh_toan=_tien(_chu(ttoan, "TgTTTBSo")),
        dong_hang=dong_hang,
    )


if __name__ == "__main__":
    hd = doc_xml(sys.argv[1])
    print(hd.model_dump_json(indent=2))
    print("Kiểm tra nghiệp vụ:", hd.kiem_tra() or "OK")
