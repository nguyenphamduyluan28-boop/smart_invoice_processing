"""Cơ sở dữ liệu (chống trùng, tách khách hàng) và cổng chặn duyệt."""
import sqlite3

import pytest

from schema import HoaDon


def _tao_chung_tu(db, du_lieu, kh_id=None, sha="sha-1"):
    kh_id = kh_id or db.them_khach_hang("Công ty Sao Mai", "0645568151")
    ct_id = db.them_chung_tu(kh_id, "hd.pdf", "/tmp/hd.pdf", sha)
    db.cap_nhat(ct_id, du_lieu=du_lieu, hach_toan=[{"tk_no": "1531"}] * len(du_lieu["dong_hang"]),
                trang_thai="CAN_DUYET")
    return kh_id, ct_id


def _form(du_lieu, **them):
    """Giả lập form màn hình duyệt (số tiền gõ có dấu chấm như kế toán hay gõ)."""
    f = {k: str(du_lieu.get(k) or "") for k in ("ky_hieu", "so_hoa_don", "ngay_lap", "ten_nguoi_ban",
                                                 "mst_nguoi_ban", "ten_nguoi_mua", "mst_nguoi_mua")}
    f |= {k: f"{du_lieu[k]:,}".replace(",", ".") for k in ("tong_tien_chua_thue", "tien_thue", "tong_thanh_toan")}
    f["so_dong"] = str(len(du_lieu["dong_hang"]))
    for i, d in enumerate(du_lieu["dong_hang"]):
        for k, v in d.items():
            f[f"dong_{i}_{k}"] = "" if v is None else str(v)
        f[f"dong_{i}_tk_no"] = "1531"
    return f | them


def test_cung_file_tai_2_lan_chi_luu_1(db_tam):
    kh = db_tam.them_khach_hang("A", None)
    db_tam.them_chung_tu(kh, "x.pdf", "/x", "abc")
    with pytest.raises(sqlite3.IntegrityError):
        db_tam.them_chung_tu(kh, "x (1).pdf", "/x1", "abc")


def test_cung_file_o_2_khach_hang_khac_nhau_van_duoc(db_tam):
    a, b = db_tam.them_khach_hang("A", None), db_tam.them_khach_hang("B", None)
    db_tam.them_chung_tu(a, "x.pdf", "/x", "abc")
    db_tam.them_chung_tu(b, "x.pdf", "/x", "abc")
    assert db_tam.tim_theo_sha(a, "abc") != db_tam.tim_theo_sha(b, "abc")


def test_phat_hien_hoa_don_trung_du_khac_file_va_so_0_dau(db_tam, hd_dict):
    kh, ct1 = _tao_chung_tu(db_tam, hd_dict, sha="file-xml")
    _, ct2 = _tao_chung_tu(db_tam, hd_dict | {"so_hoa_don": "00003932"}, kh_id=kh, sha="file-pdf")
    assert db_tam.tim_hoa_don_trung(kh, "0911417075", "C26TKK", "00003932", ct2) == ct1


def test_chan_duyet_khi_thieu_mst(db_tam, hd_dict):
    hd_dict["mst_nguoi_ban"] = None
    _, ct = _tao_chung_tu(db_tam, hd_dict)
    loi = __import__("xu_ly").luu_chinh_sua(ct, _form(hd_dict), duyet=True)
    assert loi and loi[0].startswith("Chưa thể duyệt")
    assert db_tam.lay_chung_tu(ct)["trang_thai"] == "CAN_DUYET"


def test_xac_nhan_ngoai_le_phai_co_ly_do(db_tam, hd_dict):
    from xu_ly import luu_chinh_sua
    hd_dict["mst_nguoi_ban"] = None
    _, ct = _tao_chung_tu(db_tam, hd_dict)
    assert luu_chinh_sua(ct, _form(hd_dict, xac_nhan_ngoai_le="on"), duyet=True)  # tick mà không ghi lý do
    assert luu_chinh_sua(ct, _form(hd_dict, xac_nhan_ngoai_le="on", ly_do_xac_nhan="Hoá đơn bán lẻ xăng dầu"),
                         duyet=True) == []
    ct_sau = db_tam.lay_chung_tu(ct)
    assert ct_sau["trang_thai"] == "DA_DUYET"
    assert ct_sau["xac_nhan_ngoai_le"] == "Hoá đơn bán lẻ xăng dầu"


def test_duyet_hop_le_nap_danh_ba_doi_tac(db_tam, hd_dict):
    from xu_ly import luu_chinh_sua
    _, ct = _tao_chung_tu(db_tam, hd_dict)
    assert luu_chinh_sua(ct, _form(hd_dict), duyet=True) == []
    assert db_tam.lay_chung_tu(ct)["trang_thai"] == "DA_DUYET"
    assert db_tam.tra_doi_tac("0911417075") == hd_dict["ten_nguoi_ban"]
    # Số tiền gõ "122.619.200" được hiểu đúng
    assert HoaDon.model_validate(db_tam.lay_chung_tu(ct)["du_lieu"]).tong_thanh_toan == 122619200
