"""Đọc XML hoá đơn điện tử bằng code — phải đúng 100%, không cần AI."""
from parse_xml import doc_xml

XML = """<?xml version="1.0" encoding="UTF-8"?>
<HDon xmlns="http://example.com/hoadon"><DLHDon><TTChung><THDon>{tieu_de}</THDon>
<KHHDon>C26TKK</KHHDon><SHDon>00003932</SHDon><NLap>2026-01-02</NLap></TTChung>
<NDHDon><NBan><Ten>CÔNG TY AN KHANG</Ten><MST>0061594994</MST></NBan>
<NMua><Ten>CÔNG TY SAO MAI</Ten><MST>0645568151</MST></NMua>
<DSHHDVu>
<HHDVu><THHDVu>Giấy in A4</THHDVu><DVTinh>ram</DVTinh><SLuong>14</SLuong><DGia>118000</DGia><ThTien>1652000</ThTien><TSuat>10%</TSuat></HHDVu>
<HHDVu><THHDVu>Cước vận chuyển</THHDVu><SLuong>1.5</SLuong><ThTien>300000</ThTien><TSuat>8%</TSuat></HHDVu>
</DSHHDVu>
<TToan><TgTCThue>1952000</TgTCThue><TgTThue>189200</TgTThue><TgTTTBSo>2141200</TgTTTBSo></TToan>
</NDHDon></DLHDon></HDon>"""


def _ghi(tmp_path, tieu_de="Hóa đơn giá trị gia tăng"):
    f = tmp_path / "hd.xml"
    f.write_text(XML.format(tieu_de=tieu_de), encoding="utf-8")
    return f


def test_doc_du_cac_truong_va_bo_namespace(tmp_path):
    hd = doc_xml(_ghi(tmp_path))
    assert hd.loai_hoa_don == "GTGT"
    assert (hd.ky_hieu, hd.so_hoa_don, str(hd.ngay_lap)) == ("C26TKK", "00003932", "2026-01-02")
    assert hd.mst_nguoi_ban == "0061594994"  # XML là chuỗi -> giữ nguyên số 0 đầu
    assert (hd.tong_tien_chua_thue, hd.tien_thue, hd.tong_thanh_toan) == (1952000, 189200, 2141200)
    assert [d.thue_suat for d in hd.dong_hang] == ["10%", "8%"]
    assert hd.dong_hang[1].so_luong == 1.5 and hd.dong_hang[1].don_gia is None
    assert hd.kiem_tra() == []


def test_nhan_biet_hoa_don_ban_hang(tmp_path):
    assert doc_xml(_ghi(tmp_path, "HÓA ĐƠN BÁN HÀNG")).loai_hoa_don == "BAN_HANG"
