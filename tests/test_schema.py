"""Kiểm tra nghiệp vụ trên khuôn HoaDon: cổng chặn duyệt và cảnh báo."""
from datetime import date, timedelta

from schema import HoaDon


def test_hoa_don_hop_le_khong_bi_chan_khong_canh_bao(hd_dict):
    hd = HoaDon.model_validate(hd_dict)
    assert hd.ly_do_khong_du_dieu_kien() == []
    assert hd.kiem_tra() == []


def test_thieu_4_truong_bat_buoc_bi_chan(hd_dict):
    for k in ("ky_hieu", "so_hoa_don", "ngay_lap", "mst_nguoi_ban"):
        hd_dict[k] = None
    ly_do = HoaDon.model_validate(hd_dict).ly_do_khong_du_dieu_kien()
    assert ly_do == ["thiếu ký hiệu, số hoá đơn, ngày lập, MST người bán"]


def test_khong_phai_hoa_don_bi_chan(hd_dict):
    hd_dict["loai_hoa_don"] = "KHAC"
    assert "không phải hoá đơn" in HoaDon.model_validate(hd_dict).ly_do_khong_du_dieu_kien()


def test_mst_mat_so_0_dau_bi_chan_va_canh_bao(hd_dict):
    # Đúng lỗi AI mắc ở kho_025: "0061594994" đọc thành "061594994" (9 chữ số)
    hd_dict["mst_nguoi_ban"] = "061594994"
    hd = HoaDon.model_validate(hd_dict)
    assert any("sai định dạng" in x for x in hd.ly_do_khong_du_dieu_kien())
    assert any("MST người bán sai định dạng" in x for x in hd.kiem_tra())


def test_mst_chi_nhanh_13_so_hop_le(hd_dict):
    hd_dict["mst_nguoi_ban"] = "0911417075-001"
    assert HoaDon.model_validate(hd_dict).ly_do_khong_du_dieu_kien() == []


def test_ngay_o_tuong_lai_bi_chan(hd_dict):
    hd_dict["ngay_lap"] = (date.today() + timedelta(days=1)).isoformat()
    assert any("tương lai" in x for x in HoaDon.model_validate(hd_dict).ly_do_khong_du_dieu_kien())


def test_tong_tien_lech_thi_canh_bao(hd_dict):
    hd_dict["tong_thanh_toan"] += 1000
    assert "Tiền chưa thuế + thuế ≠ tổng thanh toán" in HoaDon.model_validate(hd_dict).kiem_tra()


def test_lech_1_dong_do_lam_tron_thi_bo_qua(hd_dict):
    hd_dict["tong_thanh_toan"] += 1
    assert HoaDon.model_validate(hd_dict).kiem_tra() == []


def test_tong_dong_hang_khac_tien_chua_thue_thi_canh_bao(hd_dict):
    hd_dict["dong_hang"].pop()  # AI bỏ sót một dòng hàng
    assert any("Tổng các dòng hàng" in x for x in HoaDon.model_validate(hd_dict).kiem_tra())


def test_hoa_don_ban_hang_chi_canh_bao_khong_chan(hd_dict):
    hd_dict["loai_hoa_don"] = "BAN_HANG"
    hd = HoaDon.model_validate(hd_dict)
    assert hd.ly_do_khong_du_dieu_kien() == []
    assert any("BÁN HÀNG" in x for x in hd.kiem_tra())
