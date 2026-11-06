"""Quy trình xử lý MỘT chứng từ — được gọi ở chế độ nền sau khi tải lên.

  đọc (XML bằng code / PDF-ảnh bằng AI) → kiểm tra nghiệp vụ → kiểm tra trùng
  → gợi ý hạch toán → gắn trạng thái OK hoặc CẦN DUYỆT

Mọi lỗi được bắt lại và ghi vào chứng từ (trạng thái LOI) để có thể xử lý lại,
thay vì làm sập cả hệ thống.
"""
import time
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

import db
from doi_tac import cac_cap_mst_ten, chuan_hoa_ten
from parse_xml import doc_xml
from schema import HoaDon
from tai_khoan import goi_y_hach_toan


def _danh_gia(ct: dict, hd: HoaDon, hach_toan: list[dict]) -> list[str]:
    canh_bao = hd.kiem_tra()
    if hd.do_tin_cay_thap:
        canh_bao.append("AI không chắc chắn: " + ", ".join(hd.do_tin_cay_thap))
    trung = db.tim_hoa_don_trung(ct["khach_hang_id"], hd.mst_nguoi_ban, hd.ky_hieu, hd.so_hoa_don, ct["id"])
    if trung:
        canh_bao.append(f"Có thể TRÙNG với chứng từ #{trung} (cùng người bán, ký hiệu, số hoá đơn)")
    kh = db.lay_khach_hang(ct["khach_hang_id"])
    if kh and kh.get("mst") and hd.mst_nguoi_mua and hd.mst_nguoi_mua != kh["mst"]:
        canh_bao.append(f"MST người mua ({hd.mst_nguoi_mua}) khác MST khách hàng ({kh['mst']}) — có phải hoá đơn của khách này?")
    if any(not h.get("tk_no") for h in hach_toan):
        canh_bao.append("Có dòng hàng chưa có tài khoản hạch toán")
    return canh_bao


def xu_ly_chung_tu(ct_id: int):
    ct = db.lay_chung_tu(ct_id)
    t0 = time.time()
    db.cap_nhat(ct_id, trang_thai="DANG_XU_LY", loi=None, bat_dau_xu_ly=datetime.now().isoformat(timespec="seconds"))
    try:
        path = Path(ct["duong_dan"])
        token = {"input_tokens": 0, "output_tokens": 0, "model": None}
        ghi_chu = []
        du_lieu_goc = None  # XML đọc bằng code, không cần đo
        if path.suffix.lower() == ".xml":
            hd = doc_xml(path)
            for mst, ten in cac_cap_mst_ten(hd):  # XML là nguồn chuẩn -> nạp vào danh bạ
                db.luu_doi_tac(mst, ten, "xml")
        else:
            from extract_llm import trich_xuat
            hd, token = trich_xuat(path)
            du_lieu_goc = hd.model_dump(mode="json") | {"_model": token.get("model")}
            ghi_chu = chuan_hoa_ten(hd, db.tra_doi_tac)  # AI đọc, danh bạ kiểm
        hach_toan = goi_y_hach_toan(hd)
        canh_bao = _danh_gia(ct, hd, hach_toan)
        db.cap_nhat(
            ct_id,
            du_lieu=hd.model_dump(mode="json"),
            # Bản gốc AI đọc (trước khi danh bạ chuẩn hoá và trước khi kế toán sửa).
            # Kế toán duyệt xong, so bản này với bản đã duyệt = đo độ chính xác trên dữ liệu THẬT.
            du_lieu_ai=du_lieu_goc,
            hach_toan=hach_toan,
            canh_bao=canh_bao,
            trang_thai="CAN_DUYET" if canh_bao else "OK",
            token_vao=token["input_tokens"],
            token_ra=token["output_tokens"],
            model=token.get("model") or ("code (XML)" if path.suffix.lower() == ".xml" else None),
            ghi_chu=ghi_chu,
            so_giay_xu_ly=round(time.time() - t0, 1),
        )
    except Exception as e:
        db.cap_nhat(ct_id, trang_thai="LOI", loi=f"{type(e).__name__}: {e}", so_giay_xu_ly=round(time.time() - t0, 1))


def _so(v):
    v = (v or "").replace(".", "").replace(",", "").strip()
    return int(v) if v else None


def luu_chinh_sua(ct_id: int, form: dict, duyet: bool) -> list[str]:
    """Kế toán sửa trên màn hình → kiểm tra lại → lưu. Trả về danh sách lỗi nhập (nếu có)."""
    ct = db.lay_chung_tu(ct_id)
    cu = ct["du_lieu"] or {}
    hach_toan_cu = ct["hach_toan"] or []
    so_dong = int(form.get("so_dong", 0))
    dong_hang, hach_toan = [], []
    for i in range(so_dong):
        p = f"dong_{i}_"
        dong_hang.append({
            "ten_hang": form.get(p + "ten_hang", ""),
            "don_vi_tinh": form.get(p + "don_vi_tinh") or None,
            "so_luong": float(form[p + "so_luong"]) if form.get(p + "so_luong") else None,
            "don_gia": _so(form.get(p + "don_gia")),
            "thanh_tien": _so(form.get(p + "thanh_tien")) or 0,
            "thue_suat": form.get(p + "thue_suat") or None,
        })
        tk = (form.get(p + "tk_no") or "").strip() or None
        cu_i = hach_toan_cu[i] if i < len(hach_toan_cu) else {}
        if tk and tk == cu_i.get("tk_no"):
            hach_toan.append(cu_i)
        else:
            hach_toan.append({"tk_no": tk, "nguon": "kế toán" if tk else "chưa rõ", "ly_do": "Kế toán chỉnh tay" if tk else ""})

    du_lieu = {
        **cu,
        **{k: (form.get(k) or None) for k in ("ky_hieu", "so_hoa_don", "ngay_lap", "ten_nguoi_ban",
                                               "mst_nguoi_ban", "ten_nguoi_mua", "mst_nguoi_mua")},
        **{k: _so(form.get(k)) for k in ("tong_tien_chua_thue", "tien_thue", "tong_thanh_toan")},
        "dong_hang": dong_hang,
        "do_tin_cay_thap": [],  # kế toán đã xem → không còn "AI không chắc"
    }
    try:
        hd = HoaDon.model_validate(du_lieu)
    except ValidationError as e:
        return [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]

    canh_bao = _danh_gia(ct, hd, hach_toan)
    truong = dict(du_lieu=hd.model_dump(mode="json"), hach_toan=hach_toan, canh_bao=canh_bao)

    # Cổng chặn: chứng từ không đủ điều kiện thì KHÔNG được duyệt,
    # trừ khi kế toán chủ động xác nhận và ghi lý do (để sau này truy vết được ai, vì sao).
    ly_do_chan = hd.ly_do_khong_du_dieu_kien()
    if duyet and ly_do_chan:
        ly_do_xac_nhan = (form.get("ly_do_xac_nhan") or "").strip()
        if not (form.get("xac_nhan_ngoai_le") and ly_do_xac_nhan):
            db.cap_nhat(ct_id, **truong, trang_thai="CAN_DUYET")  # vẫn lưu phần đã sửa
            return [f"Chưa thể duyệt: {'; '.join(ly_do_chan)}. "
                    "Sửa lại thông tin, hoặc tick ô xác nhận và ghi lý do nếu chắc chắn chứng từ hợp lệ."]
        truong["xac_nhan_ngoai_le"] = ly_do_xac_nhan
    elif not ly_do_chan:
        truong["xac_nhan_ngoai_le"] = None  # đã đủ điều kiện thì xoá xác nhận ngoại lệ cũ

    if duyet:
        truong.update(trang_thai="DA_DUYET", duyet_luc=datetime.now().isoformat(timespec="seconds"))
        for mst, ten in cac_cap_mst_ten(hd):  # kế toán đã xác nhận -> tên chuẩn cho lần sau
            db.luu_doi_tac(mst, ten, "kế toán duyệt")
    else:
        truong.update(trang_thai="CAN_DUYET" if canh_bao else "OK")
    db.cap_nhat(ct_id, **truong)
    return []
