"""Gợi ý tài khoản hạch toán cho từng dòng hàng của hoá đơn MUA VÀO.

Thiết kế "quy tắc trước, AI sau":
  1. Quy tắc cố định (miễn phí, giải thích được) xử lý các trường hợp phổ biến.
  2. Chỉ dòng nào quy tắc không nhận ra mới hỏi AI, và AI chỉ được CHỌN trong danh mục
     cho phép (enum) — không thể bịa ra số tài khoản lạ.
  3. Kết quả luôn là GỢI Ý; kế toán viên duyệt và sửa trên màn hình.

LƯU Ý NGHIỆP VỤ: danh mục và quy tắc dưới đây chỉ là mẫu để học.
Kế toán phải điều chỉnh theo chế độ kế toán doanh nghiệp đang áp dụng
và chính sách riêng (ví dụ ngưỡng ghi nhận tài sản cố định).
"""
from typing import Literal

from pydantic import BaseModel, Field

import llm
from schema import DongHang, HoaDon

DANH_MUC = {
    "152": "Nguyên liệu, vật liệu",
    "1531": "Công cụ, dụng cụ",
    "1561": "Giá mua hàng hoá",
    "211": "Tài sản cố định hữu hình",
    "242": "Chi phí trả trước",
    "6421": "Chi phí bán hàng",
    "6422": "Chi phí quản lý doanh nghiệp",
}
TK_THUE_DAU_VAO = "1331"
TK_DOI_UNG_MAC_DINH = "331"  # phải trả người bán (mua chưa thanh toán)
NGUONG_TSCD = 30_000_000  # ngưỡng mẫu; kiểm tra quy định hiện hành

QUY_TAC = [  # (từ khoá trong tên hàng, tài khoản, lý do)
    (("dịch vụ", "phí ", "bảo trì", "bảo dưỡng", "tư vấn", "sửa chữa", "thuê "), "6422", "Dịch vụ phục vụ quản lý"),
    (("vận chuyển", "giao hàng", "cước"), "6422", "Chi phí vận chuyển"),
    (("giấy in", "mực in", "văn phòng phẩm", "bút ", "sổ "), "6422", "Văn phòng phẩm dùng ngay"),
    (("bàn", "ghế", "tủ", "kệ", "máy "), "1531", "Đồ dùng/thiết bị — công cụ dụng cụ"),
]


def _theo_quy_tac(dong: DongHang) -> dict | None:
    ten = f" {dong.ten_hang.lower()} "
    for tu_khoa, tk, ly_do in QUY_TAC:
        if any(k in ten for k in tu_khoa):
            if tk == "1531" and (dong.don_gia or 0) >= NGUONG_TSCD:
                return {"tk_no": "211", "nguon": "quy tắc", "ly_do": f"Đơn giá ≥ {NGUONG_TSCD:,} — xem xét ghi TSCĐ"}
            return {"tk_no": tk, "nguon": "quy tắc", "ly_do": ly_do}
    return None


class ChonTaiKhoan(BaseModel):
    """Khuôn câu trả lời của AI: chỉ được chọn trong DANH_MUC (Literal = enum)."""
    tai_khoan: Literal[tuple(DANH_MUC)]  # type: ignore[valid-type]
    ly_do: str = Field(description="Lý do ngắn gọn, tiếng Việt")


def _hoi_ai(dong: DongHang, hd: HoaDon) -> tuple[dict, dict]:
    danh_muc = "\n".join(f"{k}: {v}" for k, v in DANH_MUC.items())
    ket_qua, token = llm.goi_co_cau_truc(
        "Bạn là kế toán viên Việt Nam. Chọn tài khoản Nợ phù hợp nhất trong danh mục cho phép.",
        f"Danh mục:\n{danh_muc}\n\nNgười bán: {hd.ten_nguoi_ban}\n"
        f"Dòng hàng: {dong.ten_hang} | ĐVT: {dong.don_vi_tinh} | SL: {dong.so_luong} | "
        f"Đơn giá: {dong.don_gia} | Thành tiền: {dong.thanh_tien}",
        ChonTaiKhoan,
    )
    return {"tk_no": ket_qua.tai_khoan, "nguon": f"AI ({llm.nha_cung_cap()})", "ly_do": ket_qua.ly_do}, token


def goi_y_hach_toan(hd: HoaDon, dem_token: dict | None = None) -> list[dict]:
    """dem_token: nếu truyền vào, token của các lần hỏi AI được CỘNG DỒN vào đó —
    để chi phí mỗi chứng từ tính đủ cả phần gợi ý tài khoản, không chỉ phần đọc."""
    co_api = llm.co_api()
    ket_qua = []
    for dong in hd.dong_hang:
        goi_y = _theo_quy_tac(dong)
        if goi_y is None and co_api:
            try:
                goi_y, token = _hoi_ai(dong, hd)
                if dem_token is not None:
                    for k in ("input_tokens", "output_tokens"):
                        dem_token[k] = dem_token.get(k, 0) + token.get(k, 0)
            except Exception as e:  # AI lỗi thì để kế toán tự chọn, không làm hỏng cả chứng từ
                goi_y = {"tk_no": None, "nguon": "chưa rõ", "ly_do": f"AI lỗi: {e}"}
        ket_qua.append(goi_y or {"tk_no": None, "nguon": "chưa rõ", "ly_do": "Không khớp quy tắc nào"})
    return ket_qua
