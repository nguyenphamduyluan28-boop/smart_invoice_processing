"""Bước hậu xử lý: chuẩn hoá tên công ty theo danh bạ MST, KHÔNG gọi lại AI.

Tách thành bước riêng để đo được đúng tác dụng của nó:
    AI đọc  ->  hậu xử lý  ->  chấm điểm

Ví dụ (từ thư mục hoa-don-ai):
    python src/hau_xu_ly.py output/gemini --danh-ba-xml data/samples --out output/gemini_chuan
    python src/evaluate.py output/gemini_chuan data/labels

Danh bạ ở đây được dựng từ các hoá đơn XML trong thư mục, giả lập tình huống thật:
"công ty này đã từng gửi hoá đơn điện tử cho mình". Để công bằng, khi chuẩn hoá hoá đơn X
thì KHÔNG dùng file XML của chính hoá đơn X (vì ngoài đời không phải lúc nào cũng có).
Trong web app, danh bạ được nạp tự động từ XML và từ chứng từ kế toán đã duyệt (bảng doi_tac).
"""
import argparse
import json
from pathlib import Path

from doi_tac import cac_cap_mst_ten, chuan_hoa_ten
from parse_xml import doc_xml
from schema import HoaDon


def dung_danh_ba(thu_muc_xml: str) -> dict[str, dict[str, str]]:
    """{mst: {tên file xml: tên công ty}} — giữ cả nguồn để loại được file của chính hoá đơn đang xét."""
    danh_ba: dict[str, dict[str, str]] = {}
    for f in sorted(Path(thu_muc_xml).glob("*.xml")):
        for mst, ten in cac_cap_mst_ten(doc_xml(f)):
            danh_ba.setdefault(mst, {})[f.stem] = ten
    return danh_ba


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("vao", help="Thư mục JSON kết quả AI (ví dụ output/gemini)")
    ap.add_argument("--danh-ba-xml", required=True, help="Thư mục chứa hoá đơn XML để dựng danh bạ")
    ap.add_argument("--out", required=True, help="Thư mục lưu kết quả sau chuẩn hoá")
    args = ap.parse_args()

    danh_ba = dung_danh_ba(args.danh_ba_xml)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    so_sua = 0
    for f in sorted(Path(args.vao).glob("*.json")):
        du_lieu = json.loads(f.read_text(encoding="utf-8"))
        hd = HoaDon.model_validate(du_lieu)

        def tra_cuu(mst, stem=f.stem):
            nguon = {k: v for k, v in danh_ba.get(mst, {}).items() if k != stem}
            return next(iter(nguon.values()), None)

        ghi_chu = chuan_hoa_ten(hd, tra_cuu)
        for g in ghi_chu:
            print(f"{f.stem}: {g}")
        so_sua += bool(ghi_chu)
        thong_tin_them = {k: v for k, v in du_lieu.items() if k.startswith("_")}
        (out / f.name).write_text(
            json.dumps(hd.model_dump(mode="json") | thong_tin_them | {"_ghi_chu": ghi_chu}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(f"\nDanh bạ: {len(danh_ba)} MST. Đã chuẩn hoá tên ở {so_sua} hoá đơn. Kết quả trong {out}")


if __name__ == "__main__":
    main()
