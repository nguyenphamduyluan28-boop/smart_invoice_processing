"""Tìm model MIỄN PHÍ trên OpenRouter dùng được cho app: đọc được ẢNH và trả được JSON theo khuôn.

Chạy (từ thư mục hoa-don-ai, đã kích hoạt .venv):
    python tools/kiem_tra_openrouter.py

Script đọc OPENROUTER_API_KEY từ file .env, KHÔNG in key ra màn hình.
Mỗi model chỉ được hỏi một câu rất ngắn.
"""
import json
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")
key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
if not key:
    raise SystemExit("Chưa có OPENROUTER_API_KEY trong file .env")

client = httpx.Client(timeout=60, headers={"Authorization": f"Bearer {key}", "X-Title": "Hoa Don AI"})
ds = client.get("https://openrouter.ai/api/v1/models").json().get("data", [])

phu_hop = []
for m in ds:
    mien_phi = m["id"].endswith(":free")
    doc_anh = "image" in (m.get("architecture", {}).get("input_modalities") or [])
    tham_so = m.get("supported_parameters") or []
    tra_json = "response_format" in tham_so or "structured_outputs" in tham_so
    if mien_phi and doc_anh:
        phu_hop.append((m["id"], tra_json))

print(f"Có {sum(1 for m in ds if m['id'].endswith(':free'))} model miễn phí, "
      f"trong đó {len(phu_hop)} model đọc được ảnh. Đang thử từng model...\n")
print(f"{'Model':<55}{'JSON khuôn':<12}{'Kết quả':<24}{'Thời gian':>9}")
for ten, tra_json in sorted(phu_hop):
    t0 = time.time()
    body = {
        "model": ten,
        "messages": [{"role": "user", "content": "Trả về JSON với trang_thai = \"OK\""}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    try:
        r = client.post("https://openrouter.ai/api/v1/chat/completions", json=body)
        if r.status_code == 200 and "error" not in r.json():
            noi_dung = r.json()["choices"][0]["message"].get("content") or ""
            kq = "TRẢ LỜI ĐƯỢC" if "OK" in noi_dung else "Trả lời sai dạng"
        else:
            kq = {429: "Hết lượt (429)", 404: "Không có / quyền dữ liệu (404)", 400: "Không hỗ trợ (400)",
                  402: "Cần nạp credit (402)"}.get(r.status_code, f"Lỗi {r.status_code}")
    except Exception as e:
        kq = type(e).__name__
    print(f"{ten:<55}{'có' if tra_json else 'không':<12}{kq:<24}{time.time() - t0:>7.1f}s")
    time.sleep(3)  # giãn nhịp để không vượt hạn mức theo phút của gói miễn phí

print("\nChọn model 'TRẢ LỜI ĐƯỢC', ưu tiên cột 'JSON khuôn' = có, rồi ghi vào .env:")
print("  LLM_PROVIDER=openrouter")
print("  OPENROUTER_MODEL=<model chính>")
print("  OPENROUTER_MODEL_DU_PHONG=<model khác, cách nhau dấu phẩy>")
print("Lỗi 404 với model miễn phí: vào openrouter.ai > Settings > Privacy và bật quyền cho endpoint miễn phí.")
