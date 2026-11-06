"""Xuất chứng từ ĐÃ DUYỆT ra Excel, mỗi dòng hàng một dòng bút toán.

Đây là "mẫu nhập chung". Mỗi phần mềm kế toán (MISA, Fast, ...) có mẫu nhập
Excel riêng: tải mẫu của phần mềm khách đang dùng rồi sửa danh sách COT bên dưới
cho khớp tên và thứ tự cột.
"""
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from schema import HoaDon
from tai_khoan import TK_DOI_UNG_MAC_DINH, TK_THUE_DAU_VAO

COT = [
    ("Ngày hạch toán", 14), ("Ngày hoá đơn", 14), ("Ký hiệu HĐ", 12), ("Số HĐ", 10),
    ("MST người bán", 16), ("Tên người bán", 40), ("Diễn giải", 36),
    ("TK Nợ", 9), ("TK Có", 9), ("Số tiền", 16), ("Thuế suất", 10),
    ("Tiền thuế", 14), ("TK thuế", 9), ("Mã chứng từ hệ thống", 12),
]


def _ty_le(thue_suat: str | None) -> float:
    try:
        return float((thue_suat or "").strip().rstrip("%")) / 100
    except ValueError:  # "KCT", "KKKNT"...
        return 0.0


def tao_excel(ds_chung_tu: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Hạch toán mua vào"
    ws.append([c for c, _ in COT])
    for i, (_, rong) in enumerate(COT, 1):
        ws.column_dimensions[get_column_letter(i)].width = rong
        o = ws.cell(row=1, column=i)
        o.font = Font(bold=True, color="FFFFFF")
        o.fill = PatternFill("solid", fgColor="1F4E79")
        o.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    bi_loai = []
    for ct in ds_chung_tu:
        ly_do = HoaDon.model_validate(ct["du_lieu"]).ly_do_khong_du_dieu_kien()
        if ly_do and not ct.get("xac_nhan_ngoai_le"):
            bi_loai.append((ct["id"], ct.get("ten_file", ""), "; ".join(ly_do)))
            continue  # không đưa chứng từ không hợp lệ vào sổ
        hd, hach_toan = ct["du_lieu"], ct["hach_toan"] or []
        dong = hd["dong_hang"]
        ngay = date.fromisoformat(hd["ngay_lap"]) if hd.get("ngay_lap") else None
        # Thuế từng dòng làm tròn có thể lệch tổng thuế trên hoá đơn vài đồng.
        # Dồn phần chênh vào dòng cuối để tổng luôn khớp hoá đơn — chi tiết nhỏ nhưng kế toán rất để ý.
        thue_dong = [round(d["thanh_tien"] * _ty_le(d.get("thue_suat"))) for d in dong]
        if thue_dong:
            thue_dong[-1] += hd["tien_thue"] - sum(thue_dong)
        for j, d in enumerate(dong):
            tk_no = hach_toan[j]["tk_no"] if j < len(hach_toan) else None
            ws.append([
                ngay, ngay, hd.get("ky_hieu"), hd.get("so_hoa_don"),
                hd.get("mst_nguoi_ban"), hd["ten_nguoi_ban"], d["ten_hang"],
                tk_no, TK_DOI_UNG_MAC_DINH, d["thanh_tien"], d.get("thue_suat"),
                thue_dong[j], TK_THUE_DAU_VAO if thue_dong[j] else None, ct["id"],
            ])
    for row in ws.iter_rows(min_row=2):
        row[0].number_format = row[1].number_format = "dd/mm/yyyy"
        for o in (row[9], row[11]):
            o.number_format = "#,##0"
    ws.freeze_panes = "A2"

    if bi_loai:  # sheet riêng để kế toán biết chứng từ nào chưa được đưa vào và vì sao
        ws2 = wb.create_sheet("Không xuất (cần xử lý)")
        ws2.append(["Mã chứng từ hệ thống", "Tên file", "Lý do không xuất"])
        for o in ws2[1]:
            o.font = Font(bold=True)
        for dong in bi_loai:
            ws2.append(list(dong))
        ws2.column_dimensions["B"].width = 50
        ws2.column_dimensions["C"].width = 70
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
