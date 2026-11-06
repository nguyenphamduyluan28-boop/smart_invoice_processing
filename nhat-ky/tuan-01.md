# Nhật ký tuần 1: Dạy AI đọc hoá đơn GTGT tiếng Việt — 99,4% và những chỗ nó vẫn sai

> Bản nháp. Sửa lại theo giọng của bạn trước khi đăng.

## Tôi đang làm gì

Tôi xây một công cụ giúp kế toán **đọc hoá đơn đầu vào tự động**: nhận file XML, PDF hoặc ảnh chụp, trả về dữ liệu có cấu trúc (ký hiệu, số hoá đơn, MST, dòng hàng, tiền thuế…), tự kiểm tra lỗi nghiệp vụ và gắn cờ những tờ cần người xem lại.

Mục tiêu tuần 1 chỉ có một: **có một con số đo được**, thay vì cảm giác "AI có vẻ đọc tốt".

## Cách làm

1. **Khuôn dữ liệu trước, AI sau.** Định nghĩa khuôn `HoaDon` bằng Pydantic, rồi ép AI trả đúng khuôn đó (structured output). AI không được viết văn tự do.
2. **XML thì không dùng AI.** Hoá đơn điện tử XML đọc bằng code thường: nhanh, miễn phí, đúng 100%. AI chỉ dùng cho PDF và ảnh chụp.
3. **Một lớp kiểm tra bằng code thường:** tiền chưa thuế + thuế = tổng thanh toán, tổng các dòng = tiền chưa thuế, MST đúng định dạng, ngày không ở tương lai, loại hoá đơn (GTGT hay bán hàng).
4. **Bộ chấm điểm:** 30 hoá đơn mẫu (20 PDF, 10 ảnh chụp giả lập nghiêng/mờ) có đáp án sẵn, so từng trường.

## Kết quả

| Chỉ số | Kết quả |
| --- | --- |
| Độ chính xác toàn bộ trường | **99,4%** |
| Hoá đơn đúng 100% mọi trường | 28/30 |
| Ký hiệu, số HĐ, ngày, MST, tiền, số dòng hàng | 100% |
| Thời gian | ~4–5 giây/tờ cho AI (khoảng 10 giây khi giãn nhịp gọi để không vượt hạn mức) |
| Token trung bình | ~965 vào + ~383 ra mỗi tờ |

*(Dữ liệu là hoá đơn mẫu giả, sạch hơn chứng từ thật nhiều. Con số thật sẽ thấp hơn — đó là việc của tuần 2.)*

## Ba điều tôi học được

**1. Lỗi của AI không ổn định.** Cả 2 lỗi đều là đọc "THỰC PHẨM" thành "THỰC PHẦM" (nhầm dấu ở chữ in hoa). Nhưng cùng tên công ty đó xuất hiện 9 lần, AI đọc đúng 7 lần, sai 2 lần — cùng phông chữ, cùng cài đặt. Sửa prompt không chữa dứt được kiểu lỗi này. Cách đúng là **"AI đọc, dữ liệu chuẩn kiểm"**: MST thì AI đọc đúng 100%, nên tên công ty nên lấy theo danh bạ MST thay vì tin chữ AI đọc.

**2. Dữ liệu thử phải giống đời thật.** Khi làm danh bạ MST, tôi phát hiện bộ dữ liệu mẫu của chính mình sinh MST ngẫu nhiên cho mỗi tờ — cùng một công ty mà mỗi hoá đơn một MST. Danh bạ vì thế "không sửa được gì". Lỗi không nằm ở thuật toán mà ở dữ liệu thử. Đã sửa: mỗi công ty một MST cố định.

**3. Đưa AI vào chạy thật khác hẳn gọi thử.** Trong một buổi tôi gặp đủ: model quá tải (503), hết hạn mức miễn phí (429), request treo không trả lời, một model trong danh sách hoá ra là model chuyển chữ thành giọng nói. Hệ thống phải: giới hạn thời gian chờ, thử lại có giãn cách, phân biệt hết hạn mức theo phút hay theo ngày, tự chuyển sang model dự phòng, và **ghi lại model nào đã đọc tờ nào** — nếu không thì không so sánh được gì.

## Tuần tới

- Chạy lại bộ mẫu mới (MST cố định) để đo tác dụng của danh bạ MST.
- 20 chứng từ thật (đã che thông tin) — để có con số đáng tin.
- So sánh 2–3 model trên cùng bộ chấm điểm: độ chính xác, tốc độ, chi phí.

*Công nghệ: Python, Pydantic, FastAPI, SQLite, Gemini API (có thể đổi sang Claude bằng một dòng cấu hình).*
