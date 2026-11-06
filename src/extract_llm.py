"""Bước 3: Dùng AI đọc hoá đơn PDF / ảnh chụp và trả về đúng khuôn HoaDon.

Phần gọi AI nằm trong llm.py — chạy được với cả Claude và Gemini, chọn bằng
LLM_PROVIDER trong file .env. File này chỉ lo phần nghiệp vụ: lời dặn cho AI
(như dặn một kế toán viên mới) và khuôn dữ liệu cần trả về.

Ba kỹ thuật được dùng:
  1. Structured output: ép AI trả JSON đúng khuôn HoaDon, không phải văn tự do.
  2. Kiểm tra bằng Pydantic: JSON sai kiểu thì gửi lỗi lại để AI tự sửa — tối đa 1 lần.
  3. Ghi lại token đã dùng để tính chi phí cho mỗi chứng từ.
"""
import json
import sys
from pathlib import Path

import llm
from schema import HoaDon

HUONG_DAN = """Bạn là kế toán viên Việt Nam cẩn thận, đang nhập liệu hoá đơn đầu vào.
Quy tắc:
- Xác định loại chứng từ theo tiêu đề: "Hoá đơn giá trị gia tăng" = GTGT, "Hoá đơn bán hàng" = BAN_HANG, không phải hoá đơn = KHAC.
- Người mua: nếu có "Tên đơn vị" thì ghi tên đơn vị (công ty), không ghi họ tên người đi mua hàng. Nếu KHÔNG có tên đơn vị (người mua là cá nhân) thì ghi họ tên người mua — không được để trống khi trên hoá đơn có ghi.
- Chỉ ghi những gì THẤY trên chứng từ. Không suy đoán, không tự tính ra số không có trên hoá đơn.
- Số tiền ghi dạng số nguyên VND, bỏ dấu chấm/phẩy phân cách hàng nghìn (ví dụ 1.250.000 -> 1250000).
- Ngày ghi dạng YYYY-MM-DD.
- Mã số thuế chỉ gồm chữ số và dấu gạch ngang. Đó là CHUỖI KÝ TỰ, không phải con số: chép đủ từng chữ số, GIỮ NGUYÊN số 0 ở đầu (ví dụ 0061594994). MST thường có đúng 10 chữ số (hoặc 10 số-3 số); đếm lại trước khi trả lời.
- Số tiền viết bằng chữ thì đổi ra số: "10 triệu" -> 10000000, "2,5 tr" -> 2500000.
- Thông tin KHÔNG CÓ trên chứng từ (ví dụ MST, ký hiệu, số hoá đơn): để trống (null). Tuyệt đối không tự nghĩ ra.
- Trường nào có nhưng không đọc rõ: vẫn điền giá trị tốt nhất, và đưa TÊN trường đó vào do_tin_cay_thap."""


def trich_xuat(path: str | Path, client=None):
    """Trả về (HoaDon, {"input_tokens":..., "output_tokens":...})."""
    return llm.goi_co_cau_truc(HUONG_DAN, "Đọc hoá đơn trong file đính kèm.", HoaDon, tep_path=path, client=client)


if __name__ == "__main__":
    print(f"AI: {llm.nha_cung_cap()} / {llm.ten_model()}")
    hd, token = trich_xuat(sys.argv[1])
    print(hd.model_dump_json(indent=2))
    print("Kiểm tra nghiệp vụ:", hd.kiem_tra() or "OK")
    print("Token:", json.dumps(token))
