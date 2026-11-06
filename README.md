# Hoá Đơn AI — Tuần 1–2: đọc chứng từ kế toán bằng LLM

Dự án học-bằng-làm. Hết 2 tuần bạn có một chương trình **đọc hoá đơn XML, PDF và ảnh chụp, trả về dữ liệu có cấu trúc, tự kiểm tra lỗi nghiệp vụ, và đo được độ chính xác bằng con số**.

## Bạn học được gì

| Kỹ năng | Nằm ở file |
| --- | --- |
| Structured output (ép AI trả đúng khuôn JSON) | `src/schema.py`, `src/extract_llm.py` |
| Tool calling (AI gọi "công cụ" do mình định nghĩa) | `src/extract_llm.py` |
| Xử lý lỗi + tự sửa (retry, self-correction) | `src/extract_llm.py`, `src/run_batch.py` |
| Không dùng AI khi không cần (XML đọc bằng code) | `src/parse_xml.py` |
| Kiểm tra nghiệp vụ bằng code thường | `HoaDon.kiem_tra()` trong `src/schema.py` |
| Eval: đo độ chính xác từng trường | `src/evaluate.py` |

## Cấu trúc

```
hoa-don-ai/
├── src/
│   ├── schema.py        # Khuôn dữ liệu hoá đơn + kiểm tra nghiệp vụ
│   ├── parse_xml.py     # Đọc XML hoá đơn điện tử (không dùng AI)
│   ├── extract_llm.py   # Đọc PDF/ảnh bằng LLM
│   ├── run_batch.py     # Xử lý cả thư mục
│   └── evaluate.py      # Chấm điểm so với đáp án
├── data/
│   ├── samples/         # 6 hoá đơn mẫu: XML + PDF/PNG (dữ liệu giả)
│   └── labels/          # Đáp án đúng của từng hoá đơn
└── tools/make_samples.py  # Sinh thêm hoá đơn mẫu
```

## Cài đặt (15 phút)

Cần Python 3.10 trở lên (`python --version`).

**Windows (PowerShell):**

```powershell
cd hoa-don-ai
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux:**

```bash
cd hoa-don-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Mở file `.env` và chọn AI (xem mục "Chọn AI" ngay dưới).

## Chọn AI: Gemini hoặc Claude

Toàn bộ phần gọi AI nằm trong `src/llm.py`; đổi AI chỉ bằng file `.env`, không phải sửa code.

**Gemini (Google):**

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=AIza...      # tạo tại https://aistudio.google.com → Get API key
GEMINI_MODEL=               # để trống = model mặc định
```

Gói miễn phí của Gemini API có giới hạn số lần gọi, và theo điều khoản của Google, dữ liệu gửi qua gói miễn phí có thể được dùng để cải thiện sản phẩm. Với gói miễn phí, **chỉ dùng hoá đơn mẫu giả**, không dùng chứng từ thật của khách hàng. Kiểm tra điều khoản và hạn mức hiện hành trên trang của Google.

**Claude (Anthropic):**

```
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...  # tạo tại https://console.anthropic.com → API Keys (nạp tiền trước)
LLM_MODEL=                    # để trống = model mặc định
```

Gói Google AI Pro hay gói Claude để chat **không** kèm API key; API key là dịch vụ riêng, tính theo lượng dùng.

Bài tập so sánh: chạy cùng bộ chứng từ với `LLM_PROVIDER=gemini` rồi `claude`, lưu vào `output/gemini` và `output/claude`, chấm điểm cả hai bằng `evaluate.py`.

## Chạy theo 5 bước

Chạy các lệnh dưới đây từ thư mục `hoa-don-ai`.

**Bước 1 — Xem khuôn dữ liệu.** Mở `src/schema.py`, đọc từng trường. Đây là "hợp đồng" giữa bạn và AI.

**Bước 2 — Đọc XML (không tốn tiền):**

```bash
python src/parse_xml.py data/samples/hd_001.xml
python src/run_batch.py "data/samples/*.xml" --out output/xml
python src/evaluate.py output/xml data/labels
```

Kết quả phải là 100%. Đây là mốc chuẩn: với XML, code thường đã hoàn hảo, không cần AI.

**Bước 3 — Đọc 1 PDF bằng LLM:**

```bash
python src/extract_llm.py data/samples/hd_001.pdf
```

So JSON in ra với file PDF. Để ý dòng `Token:` — đó là chi phí của bạn.

**Bước 4 — Đọc cả PDF và ảnh chụp:**

```bash
python src/run_batch.py "data/samples/*.pdf" "data/samples/*.png" --out output/llm
```

Dòng nào báo `CẦN DUYỆT` là chỗ một kế toán viên phải xem lại. Đây chính là human-in-the-loop.

**Bước 5 — Chấm điểm:**

```bash
python src/evaluate.py output/llm data/labels
```

Bạn có bảng độ chính xác từng trường và danh sách chỗ sai. Ghi lại con số này — đó là "phiên bản 0" của bạn.

## Bài tập 2 tuần (làm theo thứ tự)

- [ ] **Ngày 1–2:** Chạy xong 5 bước. Đọc hiểu từng dòng `extract_llm.py`.
- [ ] **Ngày 3:** Sinh 30 hoá đơn: `python tools/make_samples.py 30`, chạy lại bước 4–5.
- [ ] **Ngày 4:** Làm hỏng có chủ đích: xoá câu "bỏ dấu chấm phân cách" trong `HUONG_DAN`, chạy lại, xem điểm đổi ra sao. Bạn vừa làm "prompt ablation".
- [ ] **Ngày 5–6:** Thử 2 model khác nhau (đổi `LLM_MODEL` trong `.env`). Lập bảng: độ chính xác — thời gian — chi phí/hoá đơn. Chọn model và giải thích vì sao.
- [ ] **Ngày 7:** Làm ảnh khó hơn trong `ghi_png` (nghiêng nhiều, mờ hơn). Ghi lại điểm tụt ở trường nào.
- [ ] **Ngày 8–9:** Thêm trường mới vào `HoaDon` (ví dụ `hinh_thuc_thanh_toan`), cập nhật đáp án và `evaluate.py`.
- [ ] **Ngày 10:** Viết `src/app.py` bằng FastAPI: 1 endpoint upload file → trả JSON.
- [ ] **Ngày 11–12:** Thu thập 10–20 hoá đơn thật **của chính bạn hoặc đã xoá thông tin**, tự gán đáp án, chấm điểm. Điểm trên dữ liệu thật mới là con số đáng tin.
- [ ] **Ngày 13–14:** Viết README kết quả + quay video demo 2–3 phút. Đưa lên GitHub (không đưa `.env` và dữ liệu thật).

---

# Tuần 3–6: Web app duyệt chứng từ

Từ công cụ chạy bằng lệnh thành **ứng dụng web cho công ty kế toán**: nhiều khách hàng, tải lên hàng loạt, AI đọc ở chế độ nền, kế toán duyệt trên màn hình, xuất Excel hạch toán.

## Chạy

```bash
pip install -r requirements.txt     # cài thêm FastAPI, openpyxl...
python src/app.py
```

Mở http://127.0.0.1:8000

## Thử ngay (không tốn tiền)

1. Thêm khách hàng, ví dụ "Công ty Sao Mai" (MST để trống).
2. Tải lên 6 file `data/samples/*.xml` → tất cả chạy xong ngay, có gợi ý tài khoản.
3. Tải lên lại `hd_002.xml` → hệ thống báo đã có, **không tạo bản trùng**.
4. Sửa 1 ký tự trong `hd_003.xml` (ví dụ thêm dòng trống), lưu thành `hd_003_bansao.xml` rồi tải lên → bị gắn **"Có thể TRÙNG với chứng từ #3"**.
5. Bấm vào một chứng từ → kiểm tra → **Duyệt & sang chứng từ tiếp**.
6. Bấm **Xuất Excel** → file bút toán: Nợ 1531/6422…, Có 331, thuế 1331.
7. Có API key thì tải thêm PDF/PNG: ô AI không chắc sẽ tô vàng.

## Kiến thức mới trong giai đoạn này

| Kỹ năng | Ở đâu | Ý chính |
| --- | --- | --- |
| Multi-tenant | `db.py` | Mọi chứng từ thuộc một khách hàng; mọi truy vấn lọc theo khách hàng |
| Idempotency | `db.py`, `app.py` | Mã băm SHA-256 của file: tải lại không tạo bản trùng |
| Chống trùng nghiệp vụ | `db.tim_hoa_don_trung` | Cùng người bán + ký hiệu + số HĐ = cùng hoá đơn, dù file khác |
| Xử lý nền | `app.py` (BackgroundTasks) | Trả trang ngay, AI đọc sau; lỗi 1 file không làm hỏng cả lô |
| Quy tắc trước, AI sau | `tai_khoan.py` | Quy tắc miễn phí cho ca phổ biến; AI chỉ được chọn trong danh mục (enum) |
| Human-in-the-loop | `chi_tiet.html`, `xu_ly.luu_chinh_sua` | Kế toán sửa → kiểm tra lại → duyệt; nguồn gợi ý ghi rõ quy tắc / AI / kế toán |
| Chi tiết kế toán | `xuat_excel.py` | Thuế từng dòng làm tròn, phần lệch dồn vào dòng cuối để tổng khớp hoá đơn |

## Kiểm thử tự động (tuần 3)

```bash
pip install -r requirements.txt   # có thêm pytest
pytest -v                         # 30 test, chạy dưới 1 giây, KHÔNG gọi AI, không cần API key
```

| File test | Bảo vệ điều gì |
| --- | --- |
| `tests/test_schema.py` | Cổng chặn duyệt (thiếu ký hiệu/số/ngày/MST, không phải hoá đơn, MST 9 số, ngày tương lai) và cảnh báo lệch tổng |
| `tests/test_parse_xml.py` | Đọc XML đúng 100%, giữ số 0 đầu của MST, nhận biết hoá đơn bán hàng |
| `tests/test_evaluate.py` | Bộ chấm điểm không chấm oan (khác định dạng) và không bỏ sót lỗi thật (mất số 0, sai dấu, thiếu dòng) |
| `tests/test_db_va_duyet.py` | Chống trùng file, tách khách hàng, phát hiện hoá đơn trùng, duyệt ngoại lệ phải có lý do |
| `tests/test_doi_tac_va_excel.py` | Danh bạ MST sửa tên sai dấu; Excel tổng thuế khớp hoá đơn, không xuất chứng từ không hợp lệ |
| `tests/test_tai_khoan_va_khach_hang.py` | Chỉ hỏi AI dòng hàng quy tắc không nhận ra, và tính đủ token; từ chối MST khách hàng sai |

Mỗi test dùng cơ sở dữ liệu tạm (`tmp_path`), không đụng `data/app.db`. Khi đưa repo lên GitHub,
file `ci/test.yml` (chép vào thư mục `.github/workflows/` của repo) sẽ tự chạy bộ test mỗi lần push (CI).

Thói quen nên giữ: **sửa lỗi nào thì thêm một test cho lỗi đó** (ví dụ test MST `061594994` lấy từ lỗi AI ở bộ khó).

## Bài tập tuần 3–6

- [ ] Thêm 5 quy tắc hạch toán mới cho ngành của khách bạn nhắm tới (ví dụ nhà hàng: thực phẩm → 152/1561).
- [ ] Đổi danh sách `COT` trong `xuat_excel.py` theo mẫu nhập Excel thật của phần mềm kế toán bạn biết; nhập thử.
- [ ] Đo "tỷ lệ gợi ý tài khoản đúng": thêm `tk_no` vào đáp án, viết thêm phần chấm điểm.
- [ ] Thêm đăng nhập đơn giản (mỗi nhân viên một tài khoản) và ghi ai đã duyệt.
- [ ] Đổi SQLite sang PostgreSQL, triển khai lên một VPS hoặc cloud, có HTTPS.
- [ ] Cho 1 kế toán viên thật dùng thử với 20 chứng từ **đã xoá thông tin nhạy cảm**; ghi lại họ vướng ở đâu.

> Danh mục tài khoản và quy tắc trong `tai_khoan.py` chỉ là mẫu để học. Kế toán phải điều chỉnh theo chế độ kế toán và chính sách của doanh nghiệp.

---

# Đo độ chính xác trên chứng từ THẬT (cổng 1)

Không cần tự gõ đáp án: app giữ lại bản AI đọc ban đầu; khi kế toán **duyệt** (đã đối chiếu, sửa nếu sai),
bản đã duyệt chính là đáp án. So hai bản = độ chính xác thật.

1. Che thông tin nhạy cảm nếu cần; **không dùng gói AI miễn phí cho chứng từ thật của người khác**
   (dùng gói trả phí/credit, Claude, hoặc AI chạy trên máy).
2. Tải 20 chứng từ thật (PDF/ảnh) lên app, xử lý xong thì **mở từng tờ, đối chiếu kỹ với bản gốc, sửa chỗ sai, rồi Duyệt**.
3. Chạy:

```
python src/cham_diem_thuc_te.py
```

Kết quả: độ chính xác từng trường, theo model, và danh sách những gì kế toán đã phải sửa.

## Để đưa vào CV

Viết bằng con số, ví dụ:

> Xây hệ thống trích xuất hoá đơn GTGT tiếng Việt bằng LLM (structured output, tool calling, self-correction). Bộ eval 50 chứng từ: chính xác 96% theo trường, 2,1 giây và ~X đồng/chứng từ. Tự động gắn cờ chứng từ cần duyệt khi lệch tổng tiền hoặc sai định dạng MST.

## Lưu ý

- Dữ liệu mẫu là **giả**: tên công ty và MST hư cấu.
- Không đưa hoá đơn thật của người khác lên GitHub hay gửi đi khi chưa có sự đồng ý. Luật Bảo vệ dữ liệu cá nhân có hiệu lực từ 1/1/2026.
- Mỗi lần chạy bước 3–4 là tốn tiền API. Hãy thử trên 1–2 file trước khi chạy cả lô.
