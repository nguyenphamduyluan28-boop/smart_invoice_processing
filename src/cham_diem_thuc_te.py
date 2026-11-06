"""Đo độ chính xác của AI trên CHỨNG TỪ THẬT — không cần tự gõ đáp án.

Ý tưởng: khi kế toán duyệt một chứng từ, dữ liệu sau khi duyệt chính là ĐÁP ÁN ĐÚNG
(người đã đối chiếu với bản gốc). App giữ lại bản AI đọc ban đầu (cột du_lieu_ai).
So hai bản = AI đúng bao nhiêu trên dữ liệu thật, và kế toán phải sửa những gì.

Đây là cách các sản phẩm AI thật đo chất lượng: mỗi lần người dùng sửa là một mẫu đánh giá miễn phí.

Chạy (từ thư mục hoa-don-ai):
    python src/cham_diem_thuc_te.py            # mọi khách hàng
    python src/cham_diem_thuc_te.py --kh 1     # chỉ khách hàng số 1

Lưu ý: chỉ tính chứng từ PDF/ảnh đã DUYỆT và được xử lý từ phiên bản có lưu du_lieu_ai.
Chứng từ duyệt theo kiểu "xác nhận ngoại lệ" vẫn được tính (đáp án là bản kế toán đã xác nhận).
"""
import argparse

import db
from evaluate import cham_cap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kh", type=int, help="Mã khách hàng (mặc định: tất cả)")
    args = ap.parse_args()

    db.khoi_tao()  # bảo đảm có cột du_lieu_ai nếu cơ sở dữ liệu tạo từ bản cũ
    ds_kh = [db.lay_khach_hang(args.kh)] if args.kh else db.ds_khach_hang()
    cap, khong_tinh = [], 0
    for kh in ds_kh:
        for ct in db.ds_chung_tu(kh["id"], "DA_DUYET"):
            if not ct.get("du_lieu_ai"):
                khong_tinh += 1  # XML, hoặc xử lý trước khi app lưu bản gốc AI
                continue
            cap.append((f"#{ct['id']} {ct['ten_file'][:40]}", ct["du_lieu"], ct["du_lieu_ai"]))

    if not cap:
        print("Chưa có chứng từ PDF/ảnh nào được duyệt có lưu bản gốc AI.")
        print("Tải chứng từ lên app (sau bản cập nhật này), duyệt xong rồi chạy lại.")
        return
    print(f"Chấm {len(cap)} chứng từ đã duyệt (bỏ qua {khong_tinh} tờ XML hoặc xử lý từ bản cũ).\n")
    cham_cap(cap)


if __name__ == "__main__":
    main()
