"""Gợi ý tài khoản (quy tắc trước, AI sau) và kiểm tra MST khách hàng.

Hai test đầu sinh ra từ một lỗi thật thấy trên màn hình duyệt: chứng từ XML báo
"0 token" nhưng xử lý mất 15 giây — vì AI được hỏi gợi ý tài khoản mà token không được tính.
"""
import tai_khoan
from schema import HoaDon


def _ai_gia(dong, hd):
    return {"tk_no": "6422", "nguon": "AI (giả)", "ly_do": "test"}, {"input_tokens": 100, "output_tokens": 20}


def test_chi_hoi_ai_dong_quy_tac_khong_nhan_ra_va_cong_token(hd_dict, monkeypatch):
    monkeypatch.setattr(tai_khoan.llm, "co_api", lambda: True)
    monkeypatch.setattr(tai_khoan, "_hoi_ai", _ai_gia)
    hd_dict["dong_hang"].append({"ten_hang": "Suất ăn trưa văn phòng", "thanh_tien": 177000, "thue_suat": "8%"})
    dem = {"input_tokens": 0, "output_tokens": 0}
    ket_qua = tai_khoan.goi_y_hach_toan(HoaDon.model_validate(hd_dict), dem)
    assert [k["nguon"] for k in ket_qua] == ["quy tắc", "quy tắc", "quy tắc", "AI (giả)"]
    assert dem == {"input_tokens": 100, "output_tokens": 20}  # chỉ 1 dòng hỏi AI


def test_khong_co_key_thi_khong_hoi_ai(hd_dict, monkeypatch):
    monkeypatch.setattr(tai_khoan.llm, "co_api", lambda: False)
    hd_dict["dong_hang"] = [{"ten_hang": "Suất ăn trưa văn phòng", "thanh_tien": 177000}]
    assert tai_khoan.goi_y_hach_toan(HoaDon.model_validate(hd_dict))[0]["tk_no"] is None


def test_mst_khach_hang_sai_dinh_dang_thi_khong_canh_bao_nham(db_tam, hd_dict):
    from xu_ly import _danh_gia
    kh = db_tam.them_khach_hang("AH", "344")  # khách tạo từ trước khi có kiểm tra MST
    ct = db_tam.lay_chung_tu(db_tam.them_chung_tu(kh, "a.xml", "/a", "s1"))
    canh_bao = _danh_gia(ct, HoaDon.model_validate(hd_dict), [{"tk_no": "6422"}] * 3)
    assert not any("khác MST khách hàng" in c for c in canh_bao)


def test_tao_khach_hang_tu_choi_mst_sai(db_tam):
    from fastapi.testclient import TestClient
    import app
    client = TestClient(app.app)
    r = client.post("/khach-hang", data={"ten": "AH", "mst": "344"}, follow_redirects=False)
    assert "kh%C3%B4ng%20h%E1%BB%A3p%20l%E1%BB%87" in r.headers["location"]  # "không hợp lệ"
    assert db_tam.ds_khach_hang() == []
    client.post("/khach-hang", data={"ten": "Sao Mai", "mst": "0645 568 151"}, follow_redirects=False)
    assert db_tam.ds_khach_hang()[0]["mst"] == "0645568151"  # bỏ dấu cách khi lưu
