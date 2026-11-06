"""Bước 4: Xử lý cả thư mục chứng từ, lưu mỗi kết quả thành 1 file JSON.

Ví dụ:
  python src/run_batch.py "data/samples/*.xml" --out output/xml
  python src/run_batch.py "data/samples/*.pdf" "data/samples/*.png" --out output/llm
"""
import argparse
import glob
import json
import sys
import time
from pathlib import Path

from parse_xml import doc_xml


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mau", nargs="+", help="Mẫu đường dẫn file, ví dụ data/samples/*.pdf")
    ap.add_argument("--out", required=True, help="Thư mục lưu JSON kết quả")
    ap.add_argument("--nghi", type=float, default=0,
                    help="Nghỉ bao nhiêu giây giữa 2 lần gọi AI, để không vượt hạn mức theo phút (ví dụ --nghi 6)")
    ap.add_argument("--lam-lai", action="store_true",
                    help="Xử lý lại cả file đã có kết quả (mặc định: bỏ qua để chạy tiếp lô bị dừng giữa chừng)")
    args = ap.parse_args()

    if sys.prefix == sys.base_prefix:  # đang chạy Python của máy, không phải Python trong .venv
        print("CẢNH BÁO: bạn chưa kích hoạt môi trường .venv — các thư viện AI có thể không có.\n"
              "  Chạy trước:  .venv\\Scripts\\Activate.ps1   (hoặc gọi thẳng .venv\\Scripts\\python ...)\n")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted({f for m in args.mau for f in glob.glob(m)})
    if not files:
        print("Không tìm thấy file nào.")
        return

    tong_token = {"input_tokens": 0, "output_tokens": 0}
    bat_dau = time.time()
    bo_qua = 0
    da_goi_ai = False
    dem_model = {}
    for i, f in enumerate(files, 1):
        p = Path(f)
        if not args.lam_lai and (out / f"{p.stem}.json").exists():
            bo_qua += 1  # đã xử lý ở lần chạy trước -> không tốn tiền gọi AI lần nữa
            continue
        print(f"[{i}/{len(files)}] {p.name} ...", end=" ", flush=True)
        t0 = time.time()
        token = {"model": "code (XML)"}
        try:
            if p.suffix.lower() == ".xml":
                hd = doc_xml(p)
            else:
                from extract_llm import trich_xuat  # chỉ cần API key khi xử lý PDF/ảnh
                if args.nghi and da_goi_ai:
                    time.sleep(args.nghi)
                da_goi_ai = True
                hd, token = trich_xuat(p)
                for k in tong_token:
                    tong_token[k] += token[k]
                dem_model[token.get("model")] = dem_model.get(token.get("model"), 0) + 1
        except ImportError as e:  # thiếu thư viện: file nào cũng sẽ lỗi y hệt -> dừng ngay, khỏi chờ
            print(f"LỖI: {e}\n=> Thiếu thư viện. Kích hoạt .venv rồi chạy lại "
                  "(nếu đã kích hoạt: pip install -r requirements.txt).", flush=True)
            break
        except Exception as e:  # một file lỗi không được làm dừng cả lô
            print(f"LỖI ({time.time() - t0:.1f}s): {e}", flush=True)
            if "Chưa có" in str(e) and ".env" in str(e):  # thiếu key/model: lỗi cấu hình, dừng ngay
                break
            continue
        ket_qua = hd.model_dump(mode="json") | {"_model": token.get("model"), "_so_giay": round(time.time() - t0, 1)}
        (out / f"{p.stem}.json").write_text(json.dumps(ket_qua, ensure_ascii=False, indent=2), encoding="utf-8")
        canh_bao = hd.kiem_tra() + [f"AI không chắc: {', '.join(hd.do_tin_cay_thap)}"] * bool(hd.do_tin_cay_thap)
        trang_thai = "CẦN DUYỆT" if canh_bao else "OK"
        print(f"{trang_thai} ({time.time() - t0:.1f}s, {token.get('model')}) {'; '.join(canh_bao)}", flush=True)

    if bo_qua:
        print(f"Bỏ qua {bo_qua} file đã có kết quả từ lần chạy trước (thêm --lam-lai để xử lý lại).")
    if dem_model:
        print("Model đã dùng: " + ", ".join(f"{m}: {n} file" for m, n in dem_model.items()))
    print(f"\nXong {len(files) - bo_qua} file trong {time.time() - bat_dau:.1f}s. Token: {json.dumps(tong_token)}")


if __name__ == "__main__":
    main()
