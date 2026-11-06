"""Danh bạ đối tác theo mã số thuế — "AI đọc, dữ liệu chuẩn kiểm".

Eval cho thấy AI đọc MST đúng 100%, nhưng thỉnh thoảng sai dấu trong tên công ty
viết hoa ("THỰC PHẨM" -> "THỰC PHẦM"), và sai không ổn định: cùng một chữ lúc đúng lúc sai.
Sửa prompt không chữa dứt được loại lỗi này. Cách đúng: tên của một MST chỉ có một,
nên khi MST đã có trong danh bạ thì lấy TÊN CHUẨN từ danh bạ.

Danh bạ được nạp từ nguồn đáng tin:
  - hoá đơn XML (dữ liệu gốc từ hệ thống hoá đơn điện tử)
  - chứng từ đã được kế toán duyệt
"""
import re
import unicodedata
from collections.abc import Callable

from schema import HoaDon

VAI = (("người bán", "mst_nguoi_ban", "ten_nguoi_ban"), ("người mua", "mst_nguoi_mua", "ten_nguoi_mua"))


def chuan_mst(mst: str | None) -> str | None:
    if not mst:
        return None
    m = re.sub(r"[^\d-]", "", mst)
    return m if re.fullmatch(r"\d{10}(-\d{3})?", m) else None


def _de_so(ten: str | None) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", ten or "")).strip().casefold()


def cac_cap_mst_ten(hd: HoaDon) -> list[tuple[str, str]]:
    """Các cặp (MST, tên) hợp lệ trên một hoá đơn — để nạp vào danh bạ."""
    ket_qua = []
    for _, truong_mst, truong_ten in VAI:
        mst, ten = chuan_mst(getattr(hd, truong_mst)), getattr(hd, truong_ten)
        if mst and ten and ten.strip():
            ket_qua.append((mst, re.sub(r"\s+", " ", unicodedata.normalize("NFC", ten)).strip()))
    return ket_qua


def chuan_hoa_ten(hd: HoaDon, tra_cuu: Callable[[str], str | None]) -> list[str]:
    """Thay tên AI đọc bằng tên chuẩn theo MST (nếu có trong danh bạ). Sửa trực tiếp `hd`.
    Trả về ghi chú những gì đã sửa, để người duyệt biết."""
    ghi_chu = []
    for vai, truong_mst, truong_ten in VAI:
        mst = chuan_mst(getattr(hd, truong_mst))
        if not mst:
            continue
        ten_chuan = tra_cuu(mst)
        ten_ai = getattr(hd, truong_ten)
        if ten_chuan and _de_so(ten_chuan) != _de_so(ten_ai):
            setattr(hd, truong_ten, ten_chuan)
            ghi_chu.append(f"Tên {vai} lấy theo danh bạ MST {mst}: \"{ten_chuan}\" (AI đọc: \"{ten_ai or ''}\")")
    return ghi_chu
