"""Lớp gọi AI dùng chung — đổi nhà cung cấp chỉ bằng file .env.

    LLM_PROVIDER=gemini      -> Google Gemini (key lấy tại https://aistudio.google.com)
    LLM_PROVIDER=claude      -> Anthropic Claude (key lấy tại https://console.anthropic.com)
    LLM_PROVIDER=openrouter  -> OpenRouter, cổng chung tới nhiều model, có model miễn phí ":free"

Cả hai cùng nhận vào: lời dặn hệ thống + câu hỏi + (tuỳ chọn) một file PDF/ảnh
+ một khuôn Pydantic; và cùng trả về: một đối tượng đúng khuôn + số token đã dùng.
Phần còn lại của app không cần biết đang dùng AI nào. Đây là "adapter pattern",
giúp bạn so sánh model công bằng trên cùng một bộ eval.

Hai cách ép AI trả đúng khuôn (structured output):
  - Claude: khai báo một "công cụ" có input_schema = khuôn, bắt model gọi công cụ đó.
  - Gemini: khai báo response_schema = khuôn, model trả về JSON đúng khuôn.
  - OpenRouter: chuẩn kiểu OpenAI, response_format = json_schema (model không hỗ trợ thì
    lùi về "json_object" + đưa khuôn vào lời dặn).
Nếu kết quả vẫn sai kiểu, gửi lỗi lại để model tự sửa (tối đa 1 lần).
"""
import base64
import mimetypes
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

MODEL_MAC_DINH = {"claude": "claude-sonnet-4-5", "gemini": "gemini-flash-latest", "openrouter": ""}
BIEN_KEY = {"claude": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
BIEN_MODEL = {"claude": "LLM_MODEL", "gemini": "GEMINI_MODEL", "openrouter": "OPENROUTER_MODEL"}
LOAI_FILE = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


def nha_cung_cap() -> str:
    p = (os.environ.get("LLM_PROVIDER") or "").strip().lower()
    if p in MODEL_MAC_DINH:
        return p
    # Không ghi rõ: có key nào thì dùng cái đó
    if os.environ.get("GEMINI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-ant-"):
        return "gemini"
    return "claude"


def ten_model() -> str:
    p = nha_cung_cap()
    return (os.environ.get(BIEN_MODEL[p]) or "").strip() or MODEL_MAC_DINH[p]


def co_api() -> bool:
    p = nha_cung_cap()
    key = os.environ.get(BIEN_KEY[p], "").strip()
    if p == "claude":
        return key.startswith("sk-ant-")
    if p == "openrouter":
        return bool(key) and bool(ten_model())
    return bool(key)


def kiem_tra_cau_hinh():
    p = nha_cung_cap()
    if not os.environ.get(BIEN_KEY[p], "").strip() or (p == "claude" and not co_api()):
        raise RuntimeError(
            f"Chưa có {BIEN_KEY[p]} trong file .env (đang dùng LLM_PROVIDER={p}). "
            "Cần key để đọc PDF/ảnh — XML thì không cần."
        )
    if not ten_model():
        raise RuntimeError(f"Chưa ghi {BIEN_MODEL[p]} trong file .env, ví dụ một model có đuôi ':free'.")


def _doc_tep(path: str | Path) -> tuple[bytes, str]:
    path = Path(path)
    loai = mimetypes.guess_type(path.name)[0] or ""
    if loai not in LOAI_FILE:
        raise ValueError(f"Không hỗ trợ loại file: {path.name}")
    return path.read_bytes(), loai


def _inline_refs(schema: dict) -> dict:
    """Pydantic sinh schema có $defs/$ref; thay $ref bằng nội dung thật cho chắc ăn."""
    defs = schema.pop("$defs", {})

    def thay(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return thay(dict(defs[node["$ref"].split("/")[-1]]))
            return {k: thay(v) for k, v in node.items()}
        if isinstance(node, list):
            return [thay(v) for v in node]
        return node

    return thay(schema)


KHOA_SCHEMA_GEMINI = {"type", "properties", "required", "items", "enum", "anyOf", "description",
                      "format", "title", "minimum", "maximum", "minItems", "maxItems", "nullable"}


def _gon_cho_gemini(node):
    """Gemini chỉ hỗ trợ một phần JSON Schema: bỏ các khoá lạ (ví dụ "default") cho chắc ăn."""
    if isinstance(node, dict):
        return {k: (_gon_cho_gemini(v) if k != "properties" else {p: _gon_cho_gemini(x) for p, x in v.items()})
                for k, v in node.items() if k in KHOA_SCHEMA_GEMINI}
    if isinstance(node, list):
        return [_gon_cho_gemini(v) for v in node]
    return node


# ---------------- Claude ----------------
def _claude(he_thong, cau_hoi, Khuon, tep, client):
    import anthropic

    client = client or anthropic.Anthropic(max_retries=3)  # tự thử lại khi lỗi mạng / quá tải
    cong_cu = {
        "name": "ghi_ket_qua",
        "description": "Ghi kết quả đã đọc/phân tích vào hệ thống.",
        "input_schema": _inline_refs(Khuon.model_json_schema()),
    }
    noi_dung = []
    if tep:
        du_lieu, loai = tep
        b64 = base64.standard_b64encode(du_lieu).decode()
        kieu = "document" if loai == "application/pdf" else "image"
        noi_dung.append({"type": kieu, "source": {"type": "base64", "media_type": loai, "data": b64}})
    noi_dung.append({"type": "text", "text": cau_hoi + "\nGọi công cụ ghi_ket_qua để trả kết quả."})
    messages = [{"role": "user", "content": noi_dung}]
    token = {"input_tokens": 0, "output_tokens": 0, "model": f"claude/{ten_model()}"}

    for lan in range(2):
        resp = client.messages.create(
            model=ten_model(), max_tokens=4000, system=he_thong, tools=[cong_cu],
            tool_choice={"type": "tool", "name": "ghi_ket_qua"}, messages=messages,
        )
        token["input_tokens"] += resp.usage.input_tokens
        token["output_tokens"] += resp.usage.output_tokens
        khoi = next(b for b in resp.content if b.type == "tool_use")
        try:
            return Khuon.model_validate(khoi.input), token
        except ValidationError as e:
            if lan == 1:
                raise
            messages += [
                {"role": "assistant", "content": resp.content},
                {"role": "user", "content": [{
                    "type": "tool_result", "tool_use_id": khoi.id, "is_error": True,
                    "content": f"Dữ liệu không hợp lệ, hãy sửa và gọi lại công cụ:\n{e}",
                }]},
            ]


# ---------------- Gemini ----------------
MA_LOI_TAM_THOI = {429, 500, 503, 504}  # quá hạn mức / máy chủ quá tải: thử lại sau là được
SO_LAN_THU = 3  # chờ 2s, 4s giữa các lần
THOI_GIAN_CHO_GIAY = int(os.environ.get("GEMINI_TIMEOUT_GIAY") or 90)  # mỗi lần gọi tối đa bao lâu


def _cau_hinh_theo_model(cau_hinh, model: str):
    """Gemini 3.x "suy nghĩ" trước khi trả lời — càng nghĩ nhiều càng chậm và tốn token.
    Đọc chứng từ là việc trích xuất, không cần suy luận sâu: để mức 'low' cho nhanh.
    Đổi bằng GEMINI_THINKING trong .env (low / medium / high) để thử nghiệm và so sánh."""
    from google.genai import types

    muc = (os.environ.get("GEMINI_THINKING") or "low").strip().lower()
    if model.startswith("gemini-3") and muc:
        return cau_hinh.model_copy(update={"thinking_config": types.ThinkingConfig(thinking_level=muc)})
    return cau_hinh


def _phan_tich_429(e) -> tuple[bool, float | None, str]:
    """Đọc chi tiết lỗi 429 của Google: hết hạn mức theo PHÚT hay theo NGÀY, và nên chờ bao lâu.

    Hết hạn mức theo ngày thì thử lại vài giây sau là vô ích -> chuyển ngay sang model khác
    (mỗi model có hạn mức riêng)."""
    chi_tiet = (e.details or {}).get("error", {}).get("details", []) if isinstance(e.details, dict) else []
    theo_ngay, cho, ten_han_muc = False, None, ""
    for d in chi_tiet:
        loai = d.get("@type", "")
        if loai.endswith("QuotaFailure"):
            for v in d.get("violations", []):
                ten_han_muc = v.get("quotaId") or v.get("quotaMetric") or ""
                theo_ngay = theo_ngay or "PerDay" in ten_han_muc
        elif loai.endswith("RetryInfo"):
            try:
                cho = float(str(d.get("retryDelay", "")).rstrip("s"))
            except ValueError:
                pass
    mo_ta = "hết hạn mức THEO NGÀY" if theo_ngay else "hết hạn mức theo phút"
    return theo_ngay, cho, f"{mo_ta}{f' ({ten_han_muc})' if ten_han_muc else ''}"


def _gemini_goi(client, contents, cau_hinh):
    """Gọi Gemini, tự thử lại khi lỗi tạm thời; hết lượt thì đổi sang model dự phòng (nếu có).

    - 503/504: máy chủ Google quá tải -> chờ tăng dần rồi thử lại (exponential backoff).
    - 429: hết hạn mức. Theo phút -> chờ đúng thời gian Google gợi ý. Theo ngày -> bỏ model đó,
      chuyển ngay sang model dự phòng tiếp theo.
    - Mỗi lần gọi có giới hạn thời gian (GEMINI_TIMEOUT_GIAY) để không bao giờ treo vô hạn.
    GEMINI_MODEL_DU_PHONG có thể ghi nhiều model, cách nhau bằng dấu phẩy.
    """
    import httpx
    from google.genai import errors

    ds_model = [ten_model()]
    for m in (os.environ.get("GEMINI_MODEL_DU_PHONG") or "").split(","):
        if m.strip() and m.strip() not in ds_model:
            ds_model.append(m.strip())
    ghi_chu = []
    for model in ds_model:
        cau_hinh_model = _cau_hinh_theo_model(cau_hinh, model)
        for lan in range(SO_LAN_THU):
            cho = 2 ** (lan + 1)
            try:
                return client.models.generate_content(model=model, contents=contents, config=cau_hinh_model), model
            except errors.APIError as e:
                if e.code not in MA_LOI_TAM_THOI:
                    raise
                if e.code == 429:
                    theo_ngay, goi_y, mo_ta = _phan_tich_429(e)
                    ghi_chu.append(f"{model}: {mo_ta}")
                    if theo_ngay:
                        break  # chờ cũng vô ích -> sang model khác
                    cho = min(goi_y or cho, 60)
                else:
                    ghi_chu.append(f"{model}: quá tải (mã {e.code})")
            except httpx.TimeoutException:
                ghi_chu.append(f"{model}: quá {THOI_GIAN_CHO_GIAY} giây không phản hồi")
            if lan < SO_LAN_THU - 1:
                time.sleep(cho)
    het_ngay = any("THEO NGÀY" in g for g in ghi_chu)
    goi_y = ("Hạn mức miễn phí trong ngày đã dùng hết: đợi sang ngày hôm sau, thêm model khác vào "
             "GEMINI_MODEL_DU_PHONG, hoặc bật thanh toán/nhận credit trên AI Studio để có hạn mức cao hơn."
             if het_ngay else "Đây là lỗi tạm thời phía Google: thử lại sau ít phút.")
    raise RuntimeError(f"Gemini chưa trả lời được. {goi_y} Chi tiết: {'; '.join(dict.fromkeys(ghi_chu))}")


def _gemini(he_thong, cau_hoi, Khuon, tep, client):
    from google import genai
    from google.genai import types

    client = client or genai.Client(
        api_key=os.environ["GEMINI_API_KEY"].strip(),
        http_options=types.HttpOptions(timeout=THOI_GIAN_CHO_GIAY * 1000),  # mili-giây
    )
    phan = []
    if tep:
        du_lieu, loai = tep
        phan.append(types.Part.from_bytes(data=du_lieu, mime_type=loai))
    phan.append(types.Part(text=cau_hoi))
    contents = [types.Content(role="user", parts=phan)]
    cau_hinh = types.GenerateContentConfig(
        system_instruction=he_thong,
        temperature=0,
        response_mime_type="application/json",
        response_json_schema=_gon_cho_gemini(_inline_refs(Khuon.model_json_schema())),
    )
    token = {"input_tokens": 0, "output_tokens": 0, "model": None}

    for lan in range(2):
        resp, model_da_dung = _gemini_goi(client, contents, cau_hinh)
        token["model"] = f"gemini/{model_da_dung}"  # có thể là model dự phòng nếu model chính hết lượt
        u = resp.usage_metadata
        if u:
            token["input_tokens"] += u.prompt_token_count or 0
            # Gemini 2.5 có "suy nghĩ" nội bộ, cũng tính tiền như token đầu ra
            token["output_tokens"] += (u.candidates_token_count or 0) + (getattr(u, "thoughts_token_count", 0) or 0)
        try:
            return Khuon.model_validate_json(resp.text or ""), token
        except ValidationError as e:
            if lan == 1:
                raise
            contents += [
                resp.candidates[0].content,
                types.Content(role="user", parts=[types.Part(text=f"JSON chưa hợp lệ, hãy sửa và trả lại toàn bộ JSON:\n{e}")]),
            ]


# ---------------- OpenRouter ----------------
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _boc_json(van_ban: str) -> str:
    """Một số model bọc JSON trong ```json ... ``` dù đã dặn — gỡ lớp bọc đó ra."""
    t = (van_ban or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    return t.strip()


def _openrouter_goi(client, body: dict) -> dict:
    """Gửi 1 request, tự thử lại khi quá tải/hết lượt theo phút (429/5xx); trả về JSON phản hồi."""
    loi_cuoi = ""
    for lan in range(SO_LAN_THU):
        try:
            r = client.post(OPENROUTER_URL, json=body)
        except Exception as e:  # mạng chậm, timeout
            loi_cuoi = f"{type(e).__name__}"
        else:
            if r.status_code == 200:
                du_lieu = r.json()
                if "error" in du_lieu:  # OpenRouter đôi khi trả lỗi trong thân phản hồi 200
                    loi_cuoi = str(du_lieu["error"])[:300]
                else:
                    return du_lieu
            elif r.status_code in MA_LOI_TAM_THOI:
                loi_cuoi = f"mã {r.status_code}: {r.text[:200]}"
                cho = r.headers.get("retry-after")
                if cho and cho.isdigit() and lan < SO_LAN_THU - 1:
                    time.sleep(min(int(cho), 60))
                    continue
            else:
                # 400: model không hỗ trợ tham số nào đó; 401: sai key; 404: không có endpoint
                # (với model ":free", 404 hay do chưa bật quyền dữ liệu trong Settings > Privacy)
                raise RuntimeError(f"OpenRouter từ chối (mã {r.status_code}): {r.text[:400]}")
        if lan < SO_LAN_THU - 1:
            time.sleep(2 ** (lan + 1))
    raise RuntimeError(f"OpenRouter chưa trả lời được sau {SO_LAN_THU} lần thử: {loi_cuoi}")


def _openrouter(he_thong, cau_hoi, Khuon, tep, client):
    import json

    import httpx

    client = client or httpx.Client(
        timeout=THOI_GIAN_CHO_GIAY,
        headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY'].strip()}", "X-Title": "Hoa Don AI"},
    )
    schema = _inline_refs(Khuon.model_json_schema())
    noi_dung = []
    if tep:
        du_lieu, loai = tep
        b64 = base64.standard_b64encode(du_lieu).decode()
        if loai == "application/pdf":
            noi_dung.append({"type": "file", "file": {"filename": "chung_tu.pdf", "file_data": f"data:{loai};base64,{b64}"}})
        else:
            noi_dung.append({"type": "image_url", "image_url": {"url": f"data:{loai};base64,{b64}"}})
    noi_dung.append({"type": "text", "text": cau_hoi})

    ds_model = [ten_model()] + [m.strip() for m in (os.environ.get("OPENROUTER_MODEL_DU_PHONG") or "").split(",") if m.strip()]
    body = {
        "model": ds_model[0],
        "messages": [{"role": "system", "content": he_thong}, {"role": "user", "content": noi_dung}],
        "temperature": 0,
        "response_format": {"type": "json_schema", "json_schema": {"name": "ket_qua", "strict": False, "schema": schema}},
        # PDF có lớp chữ (hoá đơn điện tử) -> trích chữ miễn phí; PDF scan thì nên chuyển sang ảnh
        "plugins": [{"id": "file-parser", "pdf": {"engine": "pdf-text"}}],
    }
    if len(ds_model) > 1:
        body["models"] = ds_model  # OpenRouter tự chuyển sang model sau nếu model trước lỗi

    token = {"input_tokens": 0, "output_tokens": 0, "model": None}
    for lan in range(2):
        try:
            phan_hoi = _openrouter_goi(client, body)
        except RuntimeError as e:
            if "response_format" in str(e) or "json_schema" in str(e) or "structured" in str(e):
                # Model không hỗ trợ khuôn JSON -> chỉ yêu cầu "trả JSON", đưa khuôn vào lời dặn
                body["response_format"] = {"type": "json_object"}
                body["messages"][0]["content"] = (
                    he_thong + "\n\nChỉ trả về MỘT đối tượng JSON đúng khuôn (JSON Schema) sau, không thêm chữ nào khác:\n"
                    + json.dumps(schema, ensure_ascii=False)
                )
                phan_hoi = _openrouter_goi(client, body)
            else:
                raise
        u = phan_hoi.get("usage") or {}
        token["input_tokens"] += u.get("prompt_tokens") or 0
        token["output_tokens"] += u.get("completion_tokens") or 0
        token["model"] = f"openrouter/{phan_hoi.get('model') or body['model']}"
        van_ban = (phan_hoi["choices"][0]["message"].get("content") or "")
        try:
            return Khuon.model_validate_json(_boc_json(van_ban)), token
        except ValidationError as e:
            if lan == 1:
                raise
            body["messages"] += [
                {"role": "assistant", "content": van_ban},
                {"role": "user", "content": f"JSON chưa hợp lệ, hãy sửa và trả lại toàn bộ JSON:\n{e}"},
            ]


def goi_co_cau_truc(he_thong: str, cau_hoi: str, Khuon: type[BaseModel], tep_path=None, client=None):
    """Trả về (đối tượng Khuon, {"input_tokens":..., "output_tokens":..., "model": "nhà cung cấp/model"})."""
    if client is None:
        kiem_tra_cau_hinh()
    tep = _doc_tep(tep_path) if tep_path else None
    if nha_cung_cap() == "gemini":
        return _gemini(he_thong, cau_hoi, Khuon, tep, client)
    if nha_cung_cap() == "openrouter":
        return _openrouter(he_thong, cau_hoi, Khuon, tep, client)
    return _claude(he_thong, cau_hoi, Khuon, tep, client)
