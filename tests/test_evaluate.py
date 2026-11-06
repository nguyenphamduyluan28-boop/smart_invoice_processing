"""Bộ chấm điểm: nếu chấm sai thì mọi con số độ chính xác đều vô nghĩa."""
import copy
import unicodedata

from evaluate import _chuan_hoa, cham_cap


def test_chuan_hoa_khong_phat_loi_vi_khac_dinh_dang():
    assert _chuan_hoa("tong_thanh_toan", "122619200.0") == _chuan_hoa("tong_thanh_toan", 122619200)
    assert _chuan_hoa("so_hoa_don", "00003932") == _chuan_hoa("so_hoa_don", "3932")
    assert _chuan_hoa("ten_nguoi_ban", "  Công  ty AN KHANG ") == _chuan_hoa("ten_nguoi_ban", "CÔNG TY An Khang")
    # Cùng chữ "Hoà" nhưng mã Unicode khác nhau (NFD vs NFC) — mắt người thấy giống hệt
    assert _chuan_hoa("ten_hang", unicodedata.normalize("NFD", "Hoà")) == _chuan_hoa("ten_hang", "Hoà")
    assert _chuan_hoa("thue_suat", "10 %") == _chuan_hoa("thue_suat", "10%")


def test_chuan_hoa_van_bat_loi_that():
    # MST: số 0 đầu là một phần của mã, không được "chuẩn hoá" mất
    assert _chuan_hoa("mst_nguoi_ban", "0061594994") != _chuan_hoa("mst_nguoi_ban", "061594994")
    # Dấu tiếng Việt khác nhau là sai thật
    assert _chuan_hoa("ten_nguoi_ban", "THỰC PHẨM") != _chuan_hoa("ten_nguoi_ban", "THỰC PHẦM")


def test_cham_cap_dem_dung_so_loi(hd_dict, capsys):
    sai = copy.deepcopy(hd_dict)
    sai["mst_nguoi_ban"] = "911417075"
    sai["dong_hang"][2]["ten_hang"] = "Giấy in A4"
    cham_cap([("a", hd_dict, copy.deepcopy(hd_dict)), ("b", hd_dict, sai)])
    out = capsys.readouterr().out
    assert "Hoá đơn đúng 100% mọi trường: 1/2" in out
    assert "b | mst_nguoi_ban" in out
    assert "b | 3 | ten_hang" in out


def test_dong_hang_ai_bo_sot_bi_tinh_sai(hd_dict, capsys):
    thieu = copy.deepcopy(hd_dict)
    thieu["dong_hang"] = thieu["dong_hang"][:2]
    cham_cap([("c", hd_dict, thieu)])
    assert "c | 3 | thanh_tien" in capsys.readouterr().out
