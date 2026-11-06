"""Web app duyệt chứng từ.

Chạy (từ thư mục hoa-don-ai):
    python src/app.py
rồi mở http://127.0.0.1:8000
"""
import hashlib
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from xml.dom import minidom

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

GOC = Path(__file__).resolve().parents[1]
load_dotenv(GOC / ".env")

import db  # noqa: E402
import llm  # noqa: E402
from tai_khoan import DANH_MUC  # noqa: E402
from xu_ly import luu_chinh_sua, xu_ly_chung_tu  # noqa: E402
from xuat_excel import tao_excel  # noqa: E402

THU_MUC_TAI_LEN = GOC / "data" / "uploads"
DUOI_HO_TRO = {".xml", ".pdf", ".png", ".jpg", ".jpeg", ".webp"}
NHAN = {"DANG_XU_LY": "Đang xử lý", "OK": "OK", "CAN_DUYET": "Cần duyệt", "DA_DUYET": "Đã duyệt", "LOI": "Lỗi"}

app = FastAPI(title="Hoá Đơn AI")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.filters["tien"] = lambda n: "" if n is None else f"{int(n):,}".replace(",", ".")
templates.env.globals.update(NHAN=NHAN, DANH_MUC=DANH_MUC)
db.khoi_tao()


def _ve_trang_chu(kh: int, thong_bao: str = "") -> RedirectResponse:
    return RedirectResponse(f"/?kh={kh}&thong_bao={quote(thong_bao)}", status_code=303)


@app.get("/", response_class=HTMLResponse)
def trang_chu(request: Request, kh: int | None = None, loc: str | None = None, thong_bao: str = ""):
    ds_kh = db.ds_khach_hang()
    if kh is None and ds_kh:
        kh = ds_kh[0]["id"]
    tat_ca = db.ds_chung_tu(kh) if kh else []
    thong_ke = Counter(c["trang_thai"] for c in tat_ca)
    return templates.TemplateResponse(request, "index.html", {
        "ds_kh": ds_kh, "kh": db.lay_khach_hang(kh) if kh else None,
        "chung_tu": [c for c in tat_ca if not loc or c["trang_thai"] == loc],
        "thong_ke": thong_ke, "loc": loc, "thong_bao": thong_bao,
        "ai": f"{llm.nha_cung_cap()} / {llm.ten_model()}" + ("" if llm.co_api() else " (chưa có key)"),
        "tong_token": sum((c["token_vao"] or 0) + (c["token_ra"] or 0) for c in tat_ca),
    })


@app.post("/khach-hang")
def tao_khach_hang(ten: str = Form(...), mst: str = Form("")):
    from doi_tac import chuan_mst
    if mst.strip() and not chuan_mst(mst):
        return RedirectResponse(f"/?thong_bao={quote(f'MST {mst} không hợp lệ (cần 10 chữ số hoặc 10 số-3 số) — chưa thêm khách hàng')}",
                                status_code=303)
    kh = db.them_khach_hang(ten, chuan_mst(mst))
    return _ve_trang_chu(kh, f"Đã thêm khách hàng {ten}")


@app.post("/tai-len")
async def tai_len(background: BackgroundTasks, kh: int = Form(...), tep: list[UploadFile] = File(...)):
    if not db.lay_khach_hang(kh):
        raise HTTPException(404, "Không có khách hàng này")
    moi = trung = bo_qua = 0
    for f in tep:
        duoi = Path(f.filename or "").suffix.lower()
        if duoi not in DUOI_HO_TRO:
            bo_qua += 1
            continue
        noi_dung = await f.read()
        sha = hashlib.sha256(noi_dung).hexdigest()
        if db.tim_theo_sha(kh, sha):  # idempotency: file y hệt đã tải lên rồi
            trung += 1
            continue
        dich = THU_MUC_TAI_LEN / str(kh) / f"{sha[:16]}{duoi}"
        dich.parent.mkdir(parents=True, exist_ok=True)
        dich.write_bytes(noi_dung)
        ct_id = db.them_chung_tu(kh, f.filename, str(dich), sha)
        background.add_task(xu_ly_chung_tu, ct_id)  # chạy nền, lần lượt từng file
        moi += 1
    tb = f"Đã nhận {moi} chứng từ"
    if trung:
        tb += f", bỏ qua {trung} file đã tải trước đó"
    if bo_qua:
        tb += f", bỏ qua {bo_qua} file không hỗ trợ"
    return _ve_trang_chu(kh, tb)


@app.get("/chung-tu/{ct_id}", response_class=HTMLResponse)
def chi_tiet(request: Request, ct_id: int, loi_nhap: str = ""):
    ct = db.lay_chung_tu(ct_id)
    if not ct:
        raise HTTPException(404)
    noi_dung_xml = None
    if ct["duong_dan"].endswith(".xml"):
        tho = Path(ct["duong_dan"]).read_text(encoding="utf-8", errors="replace")
        try:  # in XML có thụt lề cho dễ đọc
            noi_dung_xml = "\n".join(l for l in minidom.parseString(tho.encode()).toprettyxml(indent="  ").splitlines() if l.strip())
        except Exception:
            noi_dung_xml = tho
    ly_do_chan = []
    if ct["du_lieu"]:
        from schema import HoaDon
        ly_do_chan = HoaDon.model_validate(ct["du_lieu"]).ly_do_khong_du_dieu_kien()
    da_cho = None
    if ct["trang_thai"] == "DANG_XU_LY" and ct.get("bat_dau_xu_ly"):
        da_cho = int((datetime.now() - datetime.fromisoformat(ct["bat_dau_xu_ly"])).total_seconds())
    return templates.TemplateResponse(request, "chi_tiet.html", {
        "ct": ct, "da_cho": da_cho, "ly_do_chan": ly_do_chan, "kh": db.lay_khach_hang(ct["khach_hang_id"]), "hd": ct["du_lieu"],
        "hach_toan": ct["hach_toan"] or [], "nghi_ngo": set((ct["du_lieu"] or {}).get("do_tin_cay_thap") or []),
        "loi_nhap": [l for l in loi_nhap.split("|") if l], "noi_dung_xml": noi_dung_xml,
        "loai": Path(ct["duong_dan"]).suffix.lower(),
    })


@app.post("/chung-tu/{ct_id}")
async def luu(request: Request, ct_id: int):
    form = dict(await request.form())
    duyet = form.pop("hanh_dong", "luu") == "duyet"
    loi = luu_chinh_sua(ct_id, form, duyet)
    if loi:
        return RedirectResponse(f"/chung-tu/{ct_id}?loi_nhap={quote('|'.join(loi))}", status_code=303)
    ct = db.lay_chung_tu(ct_id)
    if duyet:
        tiep = next((c for c in reversed(db.ds_chung_tu(ct["khach_hang_id"])) if c["trang_thai"] in ("CAN_DUYET", "OK")), None)
        if tiep:  # duyệt xong tự chuyển sang chứng từ tiếp theo — tiết kiệm thao tác
            return RedirectResponse(f"/chung-tu/{tiep['id']}", status_code=303)
        return _ve_trang_chu(ct["khach_hang_id"], "Đã duyệt hết chứng từ")
    return RedirectResponse(f"/chung-tu/{ct_id}", status_code=303)


@app.post("/chung-tu/{ct_id}/xu-ly-lai")
def xu_ly_lai(ct_id: int, background: BackgroundTasks):
    ct = db.lay_chung_tu(ct_id)
    db.cap_nhat(ct_id, trang_thai="DANG_XU_LY")
    background.add_task(xu_ly_chung_tu, ct_id)
    return _ve_trang_chu(ct["khach_hang_id"], f"Đang xử lý lại chứng từ #{ct_id}")


@app.get("/tep/{ct_id}")
def xem_tep(ct_id: int):
    ct = db.lay_chung_tu(ct_id)
    if not ct:
        raise HTTPException(404)
    return FileResponse(ct["duong_dan"])


@app.get("/xuat-excel")
def xuat_excel(kh: int):
    ds = db.ds_chung_tu(kh, "DA_DUYET")
    if not ds:
        return _ve_trang_chu(kh, "Chưa có chứng từ nào được duyệt để xuất")
    ten = f"hach_toan_kh{kh}.xlsx"
    return Response(
        tao_excel(list(reversed(ds))),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{ten}"'},
    )


if __name__ == "__main__":
    import uvicorn

    # reload=True: sửa file .py là server tự khởi động lại, không cần Ctrl+C.
    # (Sửa file .env thì vẫn phải tự khởi động lại.)
    thu_muc_src = str(Path(__file__).resolve().parent)
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True, app_dir=thu_muc_src, reload_dirs=[thu_muc_src])
