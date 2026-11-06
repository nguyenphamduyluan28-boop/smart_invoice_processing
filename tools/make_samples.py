"""Sinh hoá đơn MẪU (dữ liệu giả, tên công ty và MST hư cấu) để luyện tập.

Mỗi hoá đơn có 3 thứ: file XML, file PDF hoặc ảnh PNG, và đáp án đúng (labels/*.json).
Bạn không cần chạy file này — dữ liệu mẫu đã có sẵn trong data/.
Chạy lại khi muốn sinh thêm: python tools/make_samples.py 20
Sinh vào thư mục khác (không ghi đè bộ cũ): python tools/make_samples.py 30 data/bo_v2
"""
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from schema import DongHang, HoaDon  # noqa: E402

GOC = Path(__file__).resolve().parents[1]
THU_MUC = Path(sys.argv[2]) if len(sys.argv) > 2 else GOC / "data"  # tuỳ chọn: thư mục đích khác
MAU, DAP_AN = THU_MUC / "samples", THU_MUC / "labels"

FONT_CANDIDATES = [  # cần font có dấu tiếng Việt
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]
FONT = next(f for f in FONT_CANDIDATES if Path(f).exists())
FONT_BOLD = FONT.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf").replace("arial.ttf", "arialbd.ttf").replace("Arial.ttf", "Arial Bold.ttf")
if not Path(FONT_BOLD).exists():
    FONT_BOLD = FONT

BEN = [  # công ty hư cấu
    ("CÔNG TY TNHH THƯƠNG MẠI MINH PHÁT", "Số 12 đường Lê Lợi, Phường Bến Thành, TP. Hồ Chí Minh"),
    ("CÔNG TY CỔ PHẦN DỊCH VỤ KỸ THUẬT AN KHANG", "Số 45 phố Trần Duy Hưng, Phường Trung Hòa, Hà Nội"),
    ("CÔNG TY TNHH VẬN TẢI HẢI ĐĂNG", "Lô B3 KCN Tân Tạo, Phường Tân Tạo, TP. Hồ Chí Minh"),
    ("CÔNG TY TNHH NỘI THẤT GỖ VIỆT TÂM", "Số 8 đường Nguyễn Văn Linh, Phường Hải Châu, Đà Nẵng"),
]
MUA = [
    "CÔNG TY TNHH GIẢI PHÁP PHẦN MỀM SAO MAI",
    "CÔNG TY CỔ PHẦN THỰC PHẨM XANH BÌNH AN",
    "CÔNG TY TNHH KẾ TOÁN THUẾ PHÚC LỘC",
]
HANG = [
    ("Giấy in A4 70gsm", "ram", 68000, 120000),
    ("Mực in laser đen", "hộp", 450000, 1200000),
    ("Dịch vụ bảo trì máy lạnh", "lần", 300000, 900000),
    ("Phí vận chuyển nội thành", "chuyến", 250000, 800000),
    ("Bàn làm việc gỗ 1m2", "cái", 1800000, 3500000),
    ("Ghế xoay văn phòng", "cái", 950000, 2200000),
    ("Dịch vụ tư vấn thuế tháng 10", "gói", 2000000, 6000000),
]


def mst_cua(ten_cong_ty: str) -> str:
    """Mỗi công ty có MỘT mã số thuế cố định, như ngoài đời thật.
    (Bản đầu sinh MST ngẫu nhiên cho mỗi hoá đơn -> cùng công ty mà mỗi tờ một MST,
    làm danh bạ đối tác theo MST không có tác dụng. Dữ liệu thử phải mô phỏng đúng thực tế.)"""
    r = random.Random(ten_cong_ty)
    return "0" + "".join(str(r.randint(0, 9)) for _ in range(9))


def tao_hoa_don(i: int, rng: random.Random) -> HoaDon:
    ten_ban, _ = BEN[i % len(BEN)]
    thue_suat = rng.choice(["10%", "8%"])
    dong = []
    for ten, dvt, gmin, gmax in rng.sample(HANG, rng.randint(1, 4)):
        sl = rng.randint(1, 20)
        gia = rng.randrange(gmin, gmax, 1000)
        dong.append(DongHang(ten_hang=ten, don_vi_tinh=dvt, so_luong=sl, don_gia=gia, thanh_tien=sl * gia, thue_suat=thue_suat))
    chua_thue = sum(d.thanh_tien for d in dong)
    thue = round(chua_thue * int(thue_suat[:-1]) / 100)
    return HoaDon(
        ky_hieu="C26T" + "".join(rng.choice("ABCDEGHK") for _ in range(2)),
        so_hoa_don=str(rng.randint(1, 9999)),
        ngay_lap=date(2026, 1, 1) + timedelta(days=rng.randint(0, 300)),
        ten_nguoi_ban=ten_ban, mst_nguoi_ban=mst_cua(ten_ban),
        ten_nguoi_mua=(ten_mua := rng.choice(MUA)), mst_nguoi_mua=mst_cua(ten_mua),
        tong_tien_chua_thue=chua_thue, tien_thue=thue, tong_thanh_toan=chua_thue + thue,
        dong_hang=dong,
    )


def dia_chi(hd: HoaDon) -> str:
    return next(d for t, d in BEN if t == hd.ten_nguoi_ban)


def ghi_xml(hd: HoaDon, path: Path):
    dong = "".join(
        f"<HHDVu><STT>{k}</STT><THHDVu>{d.ten_hang}</THHDVu><DVTinh>{d.don_vi_tinh}</DVTinh>"
        f"<SLuong>{d.so_luong:g}</SLuong><DGia>{d.don_gia}</DGia><ThTien>{d.thanh_tien}</ThTien><TSuat>{d.thue_suat}</TSuat></HHDVu>"
        for k, d in enumerate(hd.dong_hang, 1)
    )
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<HDon><DLHDon Id="DLHDon"><TTChung><PBan>2.0.0</PBan><THDon>Hóa đơn giá trị gia tăng</THDon><KHMSHDon>1</KHMSHDon>
<KHHDon>{hd.ky_hieu}</KHHDon><SHDon>{hd.so_hoa_don}</SHDon><NLap>{hd.ngay_lap.isoformat()}</NLap><DVTTe>VND</DVTTe></TTChung>
<NDHDon><NBan><Ten>{hd.ten_nguoi_ban}</Ten><MST>{hd.mst_nguoi_ban}</MST><DChi>{dia_chi(hd)}</DChi></NBan>
<NMua><Ten>{hd.ten_nguoi_mua}</Ten><MST>{hd.mst_nguoi_mua}</MST></NMua>
<DSHHDVu>{dong}</DSHHDVu>
<TToan><TgTCThue>{hd.tong_tien_chua_thue}</TgTCThue><TgTThue>{hd.tien_thue}</TgTThue><TgTTTBSo>{hd.tong_thanh_toan}</TgTTTBSo></TToan>
</NDHDon></DLHDon><MCCQT>00{hd.so_hoa_don.zfill(6)}MAU</MCCQT></HDon>
""",
        encoding="utf-8",
    )


def dong_van_ban(hd: HoaDon):
    """Nội dung in ra, dùng chung cho PDF và PNG. (kiểu chữ, x, y_tăng_dần, text)"""
    v = lambda n: f"{n:,}".replace(",", ".")  # 1250000 -> 1.250.000
    d = hd.ngay_lap
    out = [
        ("b16", 140, "HÓA ĐƠN GIÁ TRỊ GIA TĂNG"),
        ("r10", 170, f"Ngày {d.day:02d} tháng {d.month:02d} năm {d.year}"),
        ("r10", 380, f"Ký hiệu: {hd.ky_hieu}    Số: {hd.so_hoa_don.zfill(7)}"),
        ("b10", 40, f"Đơn vị bán hàng: {hd.ten_nguoi_ban}"),
        ("r10", 40, f"Mã số thuế: {hd.mst_nguoi_ban}"),
        ("r10", 40, f"Địa chỉ: {dia_chi(hd)}"),
        ("b10", 40, f"Đơn vị mua hàng: {hd.ten_nguoi_mua}"),
        ("r10", 40, f"Mã số thuế: {hd.mst_nguoi_mua}"),
        ("r10", 40, "Hình thức thanh toán: TM/CK"),
        ("b9", 40, "STT  Tên hàng hóa, dịch vụ                 ĐVT      SL      Đơn giá        Thành tiền"),
    ]
    for k, dh in enumerate(hd.dong_hang, 1):
        out.append(("m9", 40, f"{k:<4} {dh.ten_hang:<34} {dh.don_vi_tinh:<7} {dh.so_luong:>4g} {v(dh.don_gia):>12} {v(dh.thanh_tien):>16}"))
    out += [
        ("r10", 300, f"Cộng tiền hàng: {v(hd.tong_tien_chua_thue)}"),
        ("r10", 300, f"Thuế suất GTGT: {hd.dong_hang[0].thue_suat}   Tiền thuế GTGT: {v(hd.tien_thue)}"),
        ("b10", 300, f"Tổng tiền thanh toán: {v(hd.tong_thanh_toan)}"),
        ("r9", 40, "Người mua hàng                                                  Người bán hàng"),
        ("r9", 300, "(Ký điện tử)"),
    ]
    return out


def ghi_pdf(hd: HoaDon, path: Path):
    pdfmetrics.registerFont(TTFont("VN", FONT))
    pdfmetrics.registerFont(TTFont("VNB", FONT_BOLD))
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for kieu, x, text in dong_van_ban(hd):
        c.setFont("VNB" if kieu.startswith("b") else "VN", int(kieu[1:]))
        c.drawString(x, y, text)
        y -= 26 if kieu.startswith("b16") else 20
    c.save()


def ghi_png(hd: HoaDon, path: Path, rng: random.Random):
    """Giả lập ảnh chụp điện thoại: hơi nghiêng, hơi mờ, có nhiễu."""
    img = Image.new("RGB", (1240, 1000), (250, 248, 240))
    draw = ImageDraw.Draw(img)
    y = 40
    for kieu, x, text in dong_van_ban(hd):
        size = int(kieu[1:]) * 2
        font = ImageFont.truetype(FONT_BOLD if kieu.startswith("b") else FONT, size)
        draw.text((x * 2 - 40, y), text, fill=(30, 30, 40), font=font)
        y += 52 if kieu.startswith("b16") else 40
    img = img.rotate(rng.uniform(-2.5, 2.5), expand=True, fillcolor=(200, 200, 200))
    img = img.filter(ImageFilter.GaussianBlur(0.8))
    nhieu = Image.effect_noise(img.size, 18).convert("RGB")
    img = Image.blend(img, nhieu, 0.08)
    img.save(path)


def main(so_luong: int = 6):
    MAU.mkdir(parents=True, exist_ok=True)
    DAP_AN.mkdir(parents=True, exist_ok=True)
    rng = random.Random(2026)
    for i in range(1, so_luong + 1):
        hd = tao_hoa_don(i, rng)
        ten = f"hd_{i:03d}"
        ghi_xml(hd, MAU / f"{ten}.xml")
        if i % 3 == 0:
            ghi_png(hd, MAU / f"{ten}.png", rng)  # cứ 3 hoá đơn có 1 ảnh chụp
        else:
            ghi_pdf(hd, MAU / f"{ten}.pdf")
        (DAP_AN / f"{ten}.json").write_text(hd.model_dump_json(indent=2), encoding="utf-8")
    print(f"Đã sinh {so_luong} hoá đơn mẫu vào {MAU}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
