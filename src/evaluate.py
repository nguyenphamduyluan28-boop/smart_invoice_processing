"""Bước 5: Chấm điểm — so kết quả với đáp án đúng, từng trường một.

Không có bước này thì bạn chỉ "cảm thấy" AI chạy tốt. Có nó, bạn nói được:
"đúng 96% trên 50 hoá đơn, sai nhiều nhất ở MST người mua".

Ví dụ:
  python src/evaluate.py output/llm data/labels
"""
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

TRUONG = [
    "ky_hieu", "so_hoa_don", "ngay_lap", "ten_nguoi_ban", "mst_nguoi_ban",
    "ten_nguoi_mua", "mst_nguoi_mua", "tong_tien_chua_thue", "tien_thue",
    "tong_thanh_toan", "so_dong_hang",
]
TRUONG_TIEN = {"tong_tien_chua_thue", "tien_thue", "tong_thanh_toan", "don_gia", "thanh_tien"}
TRUONG_DONG = ["ten_hang", "so_luong", "don_gia", "thanh_tien", "thue_suat"]  # chấm từng dòng hàng


def _chuan_hoa(truong: str, gia_tri):
    if gia_tri is None:
        return None
    if truong in TRUONG_TIEN:
        return round(float(gia_tri))
    if truong == "so_luong":
        return round(float(gia_tri), 3)
    if truong == "thue_suat":
        return str(gia_tri).replace(" ", "").upper()
    s = unicodedata.normalize("NFC", str(gia_tri)).strip()
    if truong.startswith("mst"):
        return re.sub(r"[^\d-]", "", s)
    if truong == "so_hoa_don":
        return s.lstrip("0") or "0"
    return re.sub(r"\s+", " ", s).casefold()


def _lay(d: dict, truong: str):
    return len(d.get("dong_hang", [])) if truong == "so_dong_hang" else d.get(truong)


def cham_diem(thu_muc_du_doan: str, thu_muc_dap_an: str):
    """Chấm điểm theo 2 thư mục JSON: kết quả AI và đáp án (cùng tên file)."""
    cap, thieu = [], []
    for f_dap_an in sorted(Path(thu_muc_dap_an).glob("*.json")):
        f_du_doan = Path(thu_muc_du_doan) / f_dap_an.name
        if not f_du_doan.exists():
            thieu.append(f_dap_an.stem)
            continue
        cap.append((f_dap_an.stem, json.loads(f_dap_an.read_text(encoding="utf-8")),
                    json.loads(f_du_doan.read_text(encoding="utf-8"))))
    cham_cap(cap, thieu)


def cham_cap(cap: list[tuple[str, dict, dict]], thieu: list[str] | None = None):
    """Lõi chấm điểm: nhận danh sách (tên, đáp án, kết quả AI) từ bất kỳ nguồn nào —
    thư mục JSON, hoặc cơ sở dữ liệu của app (xem cham_diem_thuc_te.py)."""
    thieu = thieu or []
    dung = defaultdict(int)
    tong = defaultdict(int)
    theo_model = defaultdict(lambda: [0, 0, 0, 0])  # [trường đúng, tổng trường, hoá đơn đúng hết, số hoá đơn]
    loi = []
    # Chấm DÒNG HÀNG: phần đầu hoá đơn đúng chưa đủ — hạch toán dựa trên từng dòng.
    dong_dung, dong_tong, loi_dong = defaultdict(int), defaultdict(int), []
    for ten, dap_an, du_doan in cap:
        ds_a, ds_b = dap_an.get("dong_hang") or [], du_doan.get("dong_hang") or []
        for i, dong_a in enumerate(ds_a):  # so theo thứ tự dòng; dòng AI bỏ sót = sai mọi trường
            dong_b = ds_b[i] if i < len(ds_b) else {}
            for t in TRUONG_DONG:
                a, b = _chuan_hoa(t, dong_a.get(t)), _chuan_hoa(t, dong_b.get(t))
                dong_tong[t] += 1
                if a == b:
                    dong_dung[t] += 1
                else:
                    loi_dong.append((ten, i + 1, t, dong_a.get(t), dong_b.get(t)))
    for ten, dap_an, du_doan in cap:
        tm = theo_model[du_doan.get("_model") or "(không ghi model)"]
        sai_truoc = len(loi)
        for t in TRUONG:
            a, b = _chuan_hoa(t, _lay(dap_an, t)), _chuan_hoa(t, _lay(du_doan, t))
            tong[t] += 1
            if a == b:
                dung[t] += 1
            else:
                loi.append((ten, t, _lay(dap_an, t), _lay(du_doan, t)))
        so_sai = len(loi) - sai_truoc
        tm[0] += len(TRUONG) - so_sai
        tm[1] += len(TRUONG)
        tm[2] += so_sai == 0
        tm[3] += 1

    so_hd = max(tong.values(), default=0)
    print(f"Số hoá đơn chấm: {so_hd}" + (f" | Không có kết quả: {', '.join(thieu)}" if thieu else ""))
    print(f"\n{'Trường':<22}{'Đúng':>8}{'Tỷ lệ':>10}")
    for t in TRUONG:
        if tong[t]:
            print(f"{t:<22}{dung[t]:>5}/{tong[t]:<3}{dung[t] / tong[t]:>9.0%}")
    tong_dung, tong_all = sum(dung.values()), sum(tong.values())
    if tong_all:
        print(f"\nĐộ chính xác toàn bộ trường: {tong_dung / tong_all:.1%}")
        hd_dung_het = so_hd - len({l[0] for l in loi})
        print(f"Hoá đơn đúng 100% mọi trường: {hd_dung_het}/{so_hd}")
    if len(theo_model) > 1 or "(không ghi model)" not in theo_model:
        print("\nTheo model:")
        for m, (d, t, hd_dung, n) in sorted(theo_model.items()):
            print(f"  {m:<40} {d / t:.1%} trường đúng · {hd_dung}/{n} hoá đơn đúng hết")
    if loi:
        print("\nChi tiết sai (hoá đơn | trường | đáp án | kết quả):")
        for hd, t, a, b in loi:
            print(f"  {hd} | {t} | {a!r} | {b!r}")
    if dong_tong:
        so_dong = max(dong_tong.values())
        print(f"\n--- DÒNG HÀNG ({so_dong} dòng) ---")
        print(f"{'Trường':<22}{'Đúng':>10}{'Tỷ lệ':>10}")
        for t in TRUONG_DONG:
            print(f"{t:<22}{dong_dung[t]:>6}/{dong_tong[t]:<4}{dong_dung[t] / dong_tong[t]:>9.1%}")
        print(f"Độ chính xác dòng hàng: {sum(dong_dung.values()) / sum(dong_tong.values()):.1%}")
        if loi_dong:
            print("\nChi tiết sai dòng hàng (hoá đơn | dòng | trường | đáp án | kết quả):")
            for hd, i, t, a, b in loi_dong[:40]:
                print(f"  {hd} | {i} | {t} | {a!r} | {b!r}")
            if len(loi_dong) > 40:
                print(f"  ... và {len(loi_dong) - 40} chỗ sai khác")


if __name__ == "__main__":
    cham_diem(sys.argv[1], sys.argv[2])
