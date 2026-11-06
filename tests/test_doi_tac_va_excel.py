"""Danh bạ MST sửa tên AI đọc sai, và file Excel xuất ra khớp hoá đơn."""
from io import BytesIO

from openpyxl import load_workbook

from doi_tac import chuan_hoa_ten, chuan_mst
from schema import HoaDon
from xuat_excel import tao_excel


def test_danh_ba_sua_ten_ai_doc_sai_dau(hd_dict):
    hd_dict["ten_nguoi_ban"] = "CÔNG TY THỰC PHẦM AN KHANG"  # lỗi dấu AI hay mắc
    danh_ba = {"0911417075": "CÔNG TY THỰC PHẨM AN KHANG"}
    hd = HoaDon.model_validate(hd_dict)
    ghi_chu = chuan_hoa_ten(hd, danh_ba.get)
    assert hd.ten_nguoi_ban == "CÔNG TY THỰC PHẨM AN KHANG"
    assert len(ghi_chu) == 1  # người duyệt được báo là đã sửa


def test_danh_ba_khong_dung_khi_mst_sai_dinh_dang():
    assert chuan_mst("061594994") is None  # không tra danh bạ bằng MST hỏng
    assert chuan_mst("0911 417 075") == "0911417075"


def _doc(xlsx: bytes):
    return load_workbook(BytesIO(xlsx))


def test_excel_tong_thue_khop_hoa_don_du_lam_tron_tung_dong(hd_dict):
    # 3 dòng 8% có thuế lẻ: làm tròn từng dòng sẽ lệch tổng nếu không dồn chênh lệch
    hd_dict["dong_hang"] = [{"ten_hang": f"Phí dịch vụ {i}", "thanh_tien": 33333, "thue_suat": "8%"} for i in range(3)]
    hd_dict |= {"tong_tien_chua_thue": 99999, "tien_thue": 8000, "tong_thanh_toan": 107999}
    ws = _doc(tao_excel([{"id": 1, "du_lieu": hd_dict, "hach_toan": []}]))["Hạch toán mua vào"]
    tien_thue = [r[11] for r in ws.iter_rows(min_row=2, values_only=True)]
    assert sum(tien_thue) == 8000


def test_excel_khong_xuat_chung_tu_khong_hop_le_tru_khi_da_xac_nhan(hd_dict):
    thieu = hd_dict | {"mst_nguoi_ban": None}
    wb = _doc(tao_excel([
        {"id": 1, "ten_file": "ok.xml", "du_lieu": hd_dict, "hach_toan": []},
        {"id": 2, "ten_file": "canva.pdf", "du_lieu": thieu, "hach_toan": []},
        {"id": 3, "ten_file": "xang.pdf", "du_lieu": thieu, "hach_toan": [], "xac_nhan_ngoai_le": "bán lẻ"},
    ]))
    ma_da_xuat = {r[13] for r in wb["Hạch toán mua vào"].iter_rows(min_row=2, values_only=True)}
    assert ma_da_xuat == {1, 3}
    bi_loai = list(wb["Không xuất (cần xử lý)"].iter_rows(min_row=2, values_only=True))
    assert [r[0] for r in bi_loai] == [2] and "MST người bán" in bi_loai[0][2]
