"""Kiểm tra nhanh các model Gemini mà key của bạn dùng được, và model nào đang trả lời.

Chạy (từ thư mục hoa-don-ai):
    python tools/kiem_tra_model.py

Script đọc key từ file .env, KHÔNG in key ra màn hình. Mỗi model chỉ được hỏi
một câu rất ngắn nên gần như không tốn hạn mức.
"""
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import errors, types

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
key = (os.environ.get("GEMINI_API_KEY") or "").strip()
if not key:
    raise SystemExit("Chưa có GEMINI_API_KEY trong file .env")

client = genai.Client(api_key=key, http_options=types.HttpOptions(timeout=30_000))

ds = []
for m in client.models.list():
    ten = m.name.replace("models/", "")
    hanh_dong = getattr(m, "supported_actions", None) or []
    # Bỏ các model chuyên dụng không đọc được chứng từ: chuyển văn bản thành giọng nói (tts),
    # âm thanh, tạo ảnh, hội thoại trực tiếp (live), nhúng vector (embedding)
    chuyen_dung = ("tts", "audio", "image", "live", "embedding", "native")
    if ("generateContent" in hanh_dong and ten.startswith("gemini") and ("flash" in ten or "lite" in ten)
            and not any(k in ten for k in chuyen_dung)):
        ds.append(ten)

print(f"Tìm thấy {len(ds)} model Flash/Lite. Đang thử từng model...\n")
print(f"{'Model':<40}{'Kết quả':<22}{'Thời gian':>10}")
for ten in sorted(ds, reverse=True):
    t0 = time.time()
    try:
        # Hỏi đúng kiểu app dùng: bắt trả JSON theo khuôn, để chắc model làm được structured output
        resp = client.models.generate_content(
            model=ten, contents="Trả về JSON với trang_thai = 'OK'",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema={"type": "object", "properties": {"trang_thai": {"type": "string"}}, "required": ["trang_thai"]},
            ),
        )
        kq = "TRẢ LỜI ĐƯỢC" if "OK" in (resp.text or "") else "Trả lời sai dạng"
    except errors.APIError as e:
        kq = {503: "Quá tải (503)", 429: "Hết hạn mức (429)", 404: "Không có (404)",
              400: "Không hỗ trợ (400)"}.get(e.code, f"Lỗi {e.code}")
    except Exception as e:  # mạng chậm, timeout...
        kq = type(e).__name__
    print(f"{ten:<40}{kq:<22}{time.time() - t0:>8.1f}s")

print("\nChọn một model 'TRẢ LỜI ĐƯỢC' và ghi vào .env:")
print("  GEMINI_MODEL=<model chính>")
print("  GEMINI_MODEL_DU_PHONG=<model dự phòng>")
