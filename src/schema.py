"""Bước 1: Định nghĩa "khuôn" dữ liệu hoá đơn.

Đây là trái tim của structured output: thay vì để AI viết văn tự do,
ta mô tả chính xác các trường cần lấy. Cùng một khuôn này được dùng để:
  - đọc XML hoá đơn điện tử (parse_xml.py)
  - ép LLM trả đúng định dạng (extract_llm.py)
  - chấm điểm kết quả (evaluate.py)
"""
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class DongHang(BaseModel):
    ten_hang: str = Field(description="Tên hàng hoá, dịch vụ đúng như trên hoá đơn")
    don_vi_tinh: str | None = Field(default=None, description="Đơn vị tính, ví dụ: cái, kg, giờ")
    so_luong: float | None = None
    don_gia: int | None = Field(default=None, description="Đơn giá, VND, số nguyên")
    thanh_tien: int = Field(description="Thành tiền CHƯA thuế của dòng, VND, số nguyên")
    thue_suat: str | None = Field(default=None, description="Thuế suất GTGT: '10%', '8%', '5%', '0%' hoặc 'KCT'")


class HoaDon(BaseModel):
    loai_hoa_don: Literal["GTGT", "BAN_HANG", "KHAC"] | None = Field(
        default=None,
        description="GTGT nếu tiêu đề là 'Hoá đơn giá trị gia tăng'; BAN_HANG nếu là 'Hoá đơn bán hàng'; "
                    "KHAC nếu không phải hoá đơn (phiếu thu, báo giá, biên nhận...)",
    )
    ky_hieu: str | None = Field(default=None, description="Ký hiệu hoá đơn, ví dụ C26TAA")
    so_hoa_don: str | None = Field(default=None, description="Số hoá đơn. Để trống (null) nếu chứng từ không ghi")
    ngay_lap: date | None = Field(default=None, description="Ngày lập hoá đơn, định dạng YYYY-MM-DD")
    ten_nguoi_ban: str
    mst_nguoi_ban: str | None = Field(
        default=None,
        description="Mã số thuế người bán: 10 chữ số, hoặc 10 chữ số-3 chữ số. Để trống (null) nếu chứng từ không ghi — KHÔNG được tự nghĩ ra",
    )
    ten_nguoi_mua: str | None = Field(
        default=None,
        description="Tên ĐƠN VỊ mua hàng (công ty) nếu có; chỉ khi không có tên đơn vị mới ghi họ tên người mua",
    )
    mst_nguoi_mua: str | None = None
    tong_tien_chua_thue: int = Field(description="Cộng tiền hàng chưa thuế, VND")
    tien_thue: int = Field(description="Tổng tiền thuế GTGT, VND")
    tong_thanh_toan: int = Field(description="Tổng tiền thanh toán, VND")
    dong_hang: list[DongHang] = Field(default_factory=list)
    do_tin_cay_thap: list[str] = Field(
        default_factory=list,
        description="Tên các trường bạn KHÔNG chắc chắn (chữ mờ, bị che, khó đọc). Để rỗng nếu chắc chắn hết.",
    )

    def ly_do_khong_du_dieu_kien(self) -> list[str]:
        """Lý do khiến chứng từ KHÔNG được duyệt để hạch toán (khác với cảnh báo chỉ để lưu ý).

        Danh sách rỗng = đủ điều kiện. Đây là câu trả lời cho bài tập:
            khong_du_dieu_kien = (self.loai_hoa_don == "KHAC" or not self.ky_hieu or not self.so_hoa_don
                                  or not self.ngay_lap or not self.mst_nguoi_ban)
        nhưng trả về DANH SÁCH LÝ DO thay vì True/False, để màn hình nói được vì sao bị chặn.
        """
        ly_do = []
        if self.loai_hoa_don == "KHAC":
            ly_do.append("không phải hoá đơn")
        thieu = [ten for ten, gia_tri in (("ký hiệu", self.ky_hieu), ("số hoá đơn", self.so_hoa_don),
                                          ("ngày lập", self.ngay_lap), ("MST người bán", self.mst_nguoi_ban))
                 if not gia_tri]
        if thieu:
            ly_do.append("thiếu " + ", ".join(thieu))
        if self.mst_nguoi_ban and not re.fullmatch(r"\d{10}(-\d{3})?", self.mst_nguoi_ban.strip()):
            ly_do.append(f"MST người bán sai định dạng ({self.mst_nguoi_ban})")
        if self.ngay_lap and self.ngay_lap > date.today():
            ly_do.append(f"ngày lập {self.ngay_lap:%d/%m/%Y} ở tương lai")
        return ly_do

    def kiem_tra(self) -> list[str]:
        """Kiểm tra nghiệp vụ. AI có thể đọc 'đúng chữ' nhưng sai logic kế toán,
        nên luôn có một lớp kiểm tra bằng code thường (không dùng AI)."""
        loi = []
        if self.loai_hoa_don == "BAN_HANG":
            loi.append("Hoá đơn BÁN HÀNG (không phải GTGT): không có thuế GTGT đầu vào để khấu trừ — "
                       "ghi toàn bộ số tiền vào giá mua/chi phí")
        elif self.loai_hoa_don == "KHAC":
            loi.append("Chứng từ này có vẻ KHÔNG phải hoá đơn (phiếu thu, báo giá...) — kiểm tra trước khi hạch toán")
        thieu = [ten for ten, gt in (("ký hiệu", self.ky_hieu), ("số hoá đơn", self.so_hoa_don),
                                     ("ngày lập", self.ngay_lap), ("MST người bán", self.mst_nguoi_ban)) if not gt]
        if thieu and self.loai_hoa_don != "KHAC":
            loi.append(f"Thiếu {', '.join(thieu)} — có thể không phải hoá đơn GTGT hợp lệ, cần kiểm tra trước khi hạch toán")
        if self.ngay_lap and self.ngay_lap > date.today():
            loi.append(f"Ngày lập {self.ngay_lap:%d/%m/%Y} ở tương lai")
        if abs(self.tong_tien_chua_thue + self.tien_thue - self.tong_thanh_toan) > 1:
            loi.append("Tiền chưa thuế + thuế ≠ tổng thanh toán")
        if self.dong_hang:
            tong_dong = sum(d.thanh_tien for d in self.dong_hang)
            if abs(tong_dong - self.tong_tien_chua_thue) > 1:
                loi.append(f"Tổng các dòng hàng ({tong_dong:,}) ≠ tiền chưa thuế ({self.tong_tien_chua_thue:,})")
        for ten, mst in (("người bán", self.mst_nguoi_ban), ("người mua", self.mst_nguoi_mua)):
            if mst and not re.fullmatch(r"\d{10}(-\d{3})?", mst.strip()):
                loi.append(f"MST {ten} sai định dạng: {mst}")
        return loi
