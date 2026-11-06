"""Sinh bộ hoá đơn mẫu "KHÓ" — giống chứng từ thật hơn bộ make_samples.py.

Dữ liệu vẫn là GIẢ (công ty, MST hư cấu), nhưng mô phỏng những gì làm AI dễ sai ngoài đời:
  - 3 kiểu bố cục: hoá đơn GTGT kẻ bảng, hoá đơn khởi tạo từ máy tính tiền (khổ hẹp), hoá đơn bán hàng
  - nhiều thuế suất trên cùng một tờ (5%, 8%, 10%, KCT), tên hàng dài xuống dòng
  - người mua là cá nhân không có MST
  - số tiền viết bằng chữ, dấu đỏ, chữ ký số, đường kẻ
  - ảnh chụp điện thoại: nghiêng, phối cảnh, bóng tối, nhiễu, nén JPEG; PDF dạng scan (không có lớp chữ)

Chạy:  python tools/make_samples_kho.py 30 data/bo_kho
Kết quả: data/bo_kho/samples (*.pdf, *.jpg, *.xml) và data/bo_kho/labels (*.json = đáp án)
"""
import io
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_samples import mst_cua  # noqa: E402  dùng lại cách tạo MST cố định theo tên công ty
from schema import DongHang, HoaDon  # noqa: E402

GOC = Path(__file__).resolve().parents[1]

FONT_THUONG = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf",
               "/System/Library/Fonts/Supplemental/Arial.ttf"]
FONT_DAM = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "C:/Windows/Fonts/arialbd.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
FONT_SERIF = ["/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", "C:/Windows/Fonts/times.ttf",
              "/System/Library/Fonts/Supplemental/Times New Roman.ttf"]


def _font(ds, co):
    for f in ds:
        if Path(f).exists():
            return ImageFont.truetype(f, co)
    return ImageFont.truetype(FONT_THUONG[0], co)


BAN = [  # người bán hư cấu: (tên, địa chỉ)
    ("CÔNG TY TNHH THƯƠNG MẠI DỊCH VỤ ÁNH DƯƠNG XANH", "Số 27 Nguyễn Thị Minh Khai, Phường Sài Gòn, TP. Hồ Chí Minh"),
    ("CÔNG TY CỔ PHẦN THIẾT BỊ VĂN PHÒNG HƯNG THỊNH", "Tầng 3, số 115 Láng Hạ, Phường Láng, Hà Nội"),
    ("CÔNG TY TNHH NHÀ HÀNG PHỐ CỔ ĐÔNG KINH", "Số 9 Hàng Buồm, Phường Hoàn Kiếm, Hà Nội"),
    ("CÔNG TY TNHH XĂNG DẦU TÂN PHÚ THỊNH", "Quốc lộ 1A, Phường Linh Xuân, TP. Hồ Chí Minh"),
    ("CÔNG TY CỔ PHẦN VIỄN THÔNG SÔNG HỒNG", "Số 88 Trần Phú, Phường Hà Đông, Hà Nội"),
    ("CỬA HÀNG ĐIỆN MÁY QUANG MINH", "Số 241 Hùng Vương, Phường Hải Châu, Đà Nẵng"),
]
MUA_DN = [
    "CÔNG TY TNHH GIẢI PHÁP PHẦN MỀM SAO MAI",
    "CÔNG TY CỔ PHẦN THỰC PHẨM XANH BÌNH AN",
    "CÔNG TY TNHH KẾ TOÁN THUẾ PHÚC LỘC",
    "CÔNG TY TNHH ĐẦU TƯ XÂY DỰNG TRƯỜNG HẢI LONG",
]
MUA_CA_NHAN = ["Nguyễn Thị Thu Hương", "Trần Quốc Bảo", "Lê Hoàng Phúc", "Phạm Ngọc Ánh"]
HANG = [  # (tên, ĐVT, giá min, giá max, thuế suất thường gặp)
    ("Bàn phím cơ không dây kết nối Bluetooth 5.0 kèm đầu thu USB", "cái", 650000, 1900000, "10%"),
    ("Màn hình máy tính 27 inch độ phân giải 2K tấm nền IPS", "chiếc", 3900000, 7500000, "10%"),
    ("Giấy in A4 định lượng 70gsm (500 tờ/ram)", "ram", 62000, 95000, "8%"),
    ("Cước dịch vụ internet cáp quang tháng 10/2026", "tháng", 220000, 550000, "10%"),
    ("Xăng RON 95-V", "lít", 21000, 24500, "10%"),
    ("Dầu Diesel 0,05S-II", "lít", 18500, 21500, "10%"),
    ("Suất ăn trưa văn phòng", "suất", 45000, 85000, "8%"),
    ("Nước khoáng đóng chai 500ml (thùng 24 chai)", "thùng", 95000, 140000, "8%"),
    ("Sách nghiệp vụ kế toán thuế doanh nghiệp", "cuốn", 120000, 260000, "5%"),
    ("Dịch vụ bảo trì hệ thống điều hoà định kỳ quý IV", "gói", 1800000, 4500000, "10%"),
    ("Phí vận chuyển nội thành", "chuyến", 150000, 650000, "8%"),
    ("Phần mềm diệt virus bản quyền 1 năm", "license", 290000, 650000, "KCT"),
]


# ------------------------------------------------------------------ số tiền bằng chữ
CHU_SO = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def _ba_so(n: int, day_du: bool) -> str:
    tram, chuc, dv = n // 100, n // 10 % 10, n % 10
    t = []
    if day_du or tram:
        t += [CHU_SO[tram], "trăm"]
    if chuc > 1:
        t += [CHU_SO[chuc], "mươi"]
    elif chuc == 1:
        t += ["mười"]
    elif dv and (day_du or tram):
        t += ["lẻ"]
    if dv:
        if dv == 1 and chuc > 1:
            t += ["mốt"]
        elif dv == 5 and chuc >= 1:
            t += ["lăm"]
        elif dv == 4 and chuc > 1:
            t += ["tư"]
        else:
            t += [CHU_SO[dv]]
    return " ".join(t)


def doc_so(n: int) -> str:
    if n == 0:
        return "Không đồng"
    don_vi = ["", "nghìn", "triệu", "tỷ"]
    nhom = []
    while n:
        nhom.append(n % 1000)
        n //= 1000
    phan = []
    for i in range(len(nhom) - 1, -1, -1):
        if nhom[i] == 0:
            continue
        phan.append(_ba_so(nhom[i], day_du=i < len(nhom) - 1) + (" " + don_vi[i] if don_vi[i] else ""))
    s = " ".join(phan) + " đồng"
    return s[0].upper() + s[1:]


# ------------------------------------------------------------------ dữ liệu hoá đơn
def tao_hoa_don(rng: random.Random, kieu: str) -> tuple[HoaDon, dict]:
    ten_ban, dia_chi = rng.choice(BAN)
    ca_nhan = rng.random() < 0.3
    ten_mua = rng.choice(MUA_CA_NHAN) if ca_nhan else rng.choice(MUA_DN)
    ban_hang = kieu == "ban_hang"
    dong = []
    for ten, dvt, gmin, gmax, ts in rng.sample(HANG, rng.randint(2, 6)):
        sl = rng.choice([1, 1, 2, 3, 5, 10, 12, 45.5, 60.25]) if dvt == "lít" else rng.randint(1, 12)
        gia = rng.randrange(gmin, gmax, 500)
        dong.append(DongHang(ten_hang=ten, don_vi_tinh=dvt, so_luong=sl, don_gia=gia,
                             thanh_tien=round(sl * gia), thue_suat=None if ban_hang else ts))
    chua_thue = sum(d.thanh_tien for d in dong)
    thue = 0 if ban_hang else sum(
        round(d.thanh_tien * int(d.thue_suat[:-1]) / 100) for d in dong if d.thue_suat and d.thue_suat != "KCT")
    nam = 2026
    ky_hieu = {"gtgt": "1C26TAA", "mtt": "1C26MBA", "ban_hang": "2C26TAA"}[kieu]
    hd = HoaDon(
        loai_hoa_don="BAN_HANG" if ban_hang else "GTGT",
        ky_hieu=ky_hieu[:-2] + "".join(rng.choice("ABCDEGHK") for _ in range(2)),
        so_hoa_don=str(rng.randint(1, 99999)),
        ngay_lap=date(nam, 1, 1) + timedelta(days=rng.randint(0, 300)),
        ten_nguoi_ban=ten_ban, mst_nguoi_ban=mst_cua(ten_ban),
        ten_nguoi_mua=ten_mua, mst_nguoi_mua=None if ca_nhan else mst_cua(ten_mua),
        tong_tien_chua_thue=chua_thue, tien_thue=thue, tong_thanh_toan=chua_thue + thue,
        dong_hang=dong,
    )
    return hd, {"dia_chi": dia_chi, "ca_nhan": ca_nhan, "kieu": kieu}


def ghi_xml(hd: HoaDon, dia_chi: str, path: Path):
    """Bản XML của cùng hoá đơn (như hoá đơn điện tử gốc) — dùng để nạp danh bạ MST."""
    from xml.sax.saxutils import escape as e
    dong = "".join(
        f"<HHDVu><STT>{k}</STT><THHDVu>{e(d.ten_hang)}</THHDVu><DVTinh>{e(d.don_vi_tinh or '')}</DVTinh>"
        f"<SLuong>{d.so_luong:g}</SLuong><DGia>{d.don_gia}</DGia><ThTien>{d.thanh_tien}</ThTien>"
        + (f"<TSuat>{d.thue_suat}</TSuat>" if d.thue_suat else "") + "</HHDVu>"
        for k, d in enumerate(hd.dong_hang, 1))
    tieu_de = "Hóa đơn bán hàng" if hd.loai_hoa_don == "BAN_HANG" else "Hóa đơn giá trị gia tăng"
    mua_mst = f"<MST>{hd.mst_nguoi_mua}</MST>" if hd.mst_nguoi_mua else ""
    path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<HDon><DLHDon Id="DLHDon"><TTChung><PBan>2.1.0</PBan><THDon>{tieu_de}</THDon>
<KHHDon>{hd.ky_hieu}</KHHDon><SHDon>{hd.so_hoa_don}</SHDon><NLap>{hd.ngay_lap.isoformat()}</NLap><DVTTe>VND</DVTTe></TTChung>
<NDHDon><NBan><Ten>{e(hd.ten_nguoi_ban)}</Ten><MST>{hd.mst_nguoi_ban}</MST><DChi>{e(dia_chi)}</DChi></NBan>
<NMua><Ten>{e(hd.ten_nguoi_mua)}</Ten>{mua_mst}</NMua><DSHHDVu>{dong}</DSHHDVu>
<TToan><TgTCThue>{hd.tong_tien_chua_thue}</TgTCThue><TgTThue>{hd.tien_thue}</TgTThue><TgTTTBSo>{hd.tong_thanh_toan}</TgTTTBSo></TToan>
</NDHDon></DLHDon></HDon>
""", encoding="utf-8")


# ------------------------------------------------------------------ vẽ
def tien(n) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def sl(x) -> str:
    return f"{x:g}".replace(".", ",")


def _ngat_dong(draw, chu, font, rong):
    tu, dong, hien = chu.split(), [], ""
    for t in tu:
        thu = (hien + " " + t).strip()
        if draw.textlength(thu, font=font) <= rong:
            hien = thu
        else:
            dong.append(hien)
            hien = t
    return dong + [hien]


def ve_gtgt(hd: HoaDon, tt: dict, rng: random.Random) -> Image.Image:
    W, H = 1654, 2339  # A4 ở 200 dpi
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f = lambda c, dam=False: _font(FONT_DAM if dam else FONT_THUONG, c)  # noqa: E731
    do = (180, 30, 30)
    xanh = (25, 60, 120)
    d.rectangle([60, 60, W - 60, H - 60], outline=xanh, width=4)
    d.text((W // 2, 130), "HÓA ĐƠN GIÁ TRỊ GIA TĂNG", fill=do, font=f(52, True), anchor="mm")
    d.text((W // 2, 190), "(Bản thể hiện của hóa đơn điện tử)", fill="black", font=f(26), anchor="mm")
    dt = hd.ngay_lap
    d.text((W // 2, 240), f"Ngày {dt.day:02d} tháng {dt.month:02d} năm {dt.year}", fill="black", font=f(30), anchor="mm")
    d.text((W - 110, 120), f"Ký hiệu: {hd.ky_hieu}", fill="black", font=f(28), anchor="rm")
    d.text((W - 110, 165), f"Số: {hd.so_hoa_don.zfill(8)}", fill=do, font=f(32, True), anchor="rm")
    d.text((110, 290), f"Mã của CQT: 00{rng.randrange(10**15, 10**16)}A{rng.randint(10, 99)}", fill="black", font=f(24))
    y = 345
    d.line([80, y, W - 80, y], fill=xanh, width=2)
    y += 20
    for nhan, gt, dam in (("Đơn vị bán hàng:", hd.ten_nguoi_ban, True), ("Mã số thuế:", hd.mst_nguoi_ban, True),
                          ("Địa chỉ:", tt["dia_chi"], False), ("Điện thoại:", f"0{rng.randint(200000000, 999999999)}", False),
                          ("Số tài khoản:", f"{rng.randint(10**11, 10**12)} tại Ngân hàng TMCP Hưng Phát", False)):
        d.text((110, y), nhan, fill="black", font=f(28))
        d.text((380, y), gt, fill="black", font=f(28, dam))
        y += 46
    d.line([80, y + 5, W - 80, y + 5], fill=xanh, width=2)
    y += 25
    nguoi_mua = [("Họ tên người mua hàng:", hd.ten_nguoi_mua if tt["ca_nhan"] else "", False)]
    if not tt["ca_nhan"]:
        nguoi_mua += [("Tên đơn vị:", hd.ten_nguoi_mua, True), ("Mã số thuế:", hd.mst_nguoi_mua, True)]
    nguoi_mua += [("Địa chỉ:", "Số 12 đường số 7, Phường Tân Định, TP. Hồ Chí Minh", False),
                  ("Hình thức thanh toán:", rng.choice(["TM/CK", "Chuyển khoản", "Tiền mặt"]), False)]
    for nhan, gt, dam in nguoi_mua:
        d.text((110, y), nhan, fill="black", font=f(28))
        d.text((450, y), gt, fill="black", font=f(28, dam))
        y += 46
    # bảng
    y += 15
    cot = [80, 160, 760, 880, 1000, 1180, 1300, 1574]
    tieu_de = ["STT", "Tên hàng hóa, dịch vụ", "ĐVT", "SL", "Đơn giá", "TS", "Thành tiền"]
    d.rectangle([cot[0], y, cot[-1], y + 60], fill=(225, 233, 245))
    for i, t in enumerate(tieu_de):
        d.text(((cot[i] + cot[i + 1]) // 2, y + 30), t, fill="black", font=f(24, True), anchor="mm")
    y0 = y
    y += 60
    fh = f(25)
    for k, dh in enumerate(hd.dong_hang, 1):
        dong_ten = _ngat_dong(d, dh.ten_hang, fh, cot[2] - cot[1] - 20)
        cao = 40 * len(dong_ten) + 16
        d.text(((cot[0] + cot[1]) // 2, y + 28), str(k), fill="black", font=fh, anchor="mm")
        for j, dl in enumerate(dong_ten):
            d.text((cot[1] + 10, y + 10 + 40 * j), dl, fill="black", font=fh)
        for i, gt in ((2, dh.don_vi_tinh), (3, sl(dh.so_luong)), (4, tien(dh.don_gia)), (5, dh.thue_suat or ""),
                      (6, tien(dh.thanh_tien))):
            x = cot[i + 1] - 12 if i in (3, 4, 6) else (cot[i] + cot[i + 1]) // 2
            d.text((x, y + 28), gt, fill="black", font=fh, anchor="rm" if i in (3, 4, 6) else "mm")
        y += cao
        d.line([cot[0], y, cot[-1], y], fill=(150, 150, 150), width=1)
    for x in cot:
        d.line([x, y0, x, y], fill="black", width=2)
    d.rectangle([cot[0], y0, cot[-1], y], outline="black", width=2)
    # tổng hợp theo thuế suất
    y += 25
    theo_ts = {}
    for dh in hd.dong_hang:
        theo_ts.setdefault(dh.thue_suat, 0)
        theo_ts[dh.thue_suat] += dh.thanh_tien
    for ts, cong in sorted(theo_ts.items(), key=lambda x: str(x[0])):
        thue_ts = 0 if ts in (None, "KCT") else round(cong * int(ts[:-1]) / 100)
        d.text((700, y), f"Tổng tiền chịu thuế suất {ts}: {tien(cong)}   Tiền thuế: {tien(thue_ts)}", fill="black", font=f(24))
        y += 38
    y += 10
    for nhan, gt, dam in (("Cộng tiền hàng:", hd.tong_tien_chua_thue, False), ("Tiền thuế GTGT:", hd.tien_thue, False),
                          ("Tổng tiền thanh toán:", hd.tong_thanh_toan, True)):
        d.text((1000, y), nhan, fill="black", font=f(28, dam))
        d.text((W - 110, y), tien(gt), fill="black", font=f(30, dam), anchor="ra")
        y += 48
    d.text((110, y + 10), "Số tiền viết bằng chữ: " + doc_so(hd.tong_thanh_toan) + ".", fill="black", font=f(26))
    y += 110
    d.text((350, y), "NGƯỜI MUA HÀNG", fill="black", font=f(28, True), anchor="mm")
    d.text((1250, y), "NGƯỜI BÁN HÀNG", fill="black", font=f(28, True), anchor="mm")
    # chữ ký số + dấu đỏ đè lên chữ
    d.rectangle([1020, y + 40, 1500, y + 190], outline=(20, 140, 60), width=3)
    d.text((1260, y + 80), "Signature Valid", fill=(20, 140, 60), font=f(26, True), anchor="mm")
    d.text((1260, y + 120), f"Ký bởi: {hd.ten_nguoi_ban[:32]}", fill=(20, 140, 60), font=f(20), anchor="mm")
    d.text((1260, y + 155), f"Ký ngày: {dt:%d/%m/%Y}", fill=(20, 140, 60), font=f(20), anchor="mm")
    _dong_dau(img, (1180, y + 80), rng)
    d.text((W // 2, H - 110), "Tra cứu hóa đơn tại: https://tracuu.hoadon-mau.vn  · Mã tra cứu: "
           + "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(10)),
           fill=(90, 90, 90), font=f(22), anchor="mm")
    return img


def ve_mtt(hd: HoaDon, tt: dict, rng: random.Random) -> Image.Image:
    """Hoá đơn khởi tạo từ máy tính tiền: khổ hẹp như phiếu in nhiệt."""
    W = 720
    fh, fd = _font(FONT_THUONG, 24), _font(FONT_DAM, 26)
    tam = Image.new("RGB", (W, 4000), (250, 250, 246))
    d = ImageDraw.Draw(tam)
    y = 30
    for dl in _ngat_dong(d, hd.ten_nguoi_ban, fd, W - 60):
        d.text((W // 2, y), dl, fill="black", font=fd, anchor="ma")
        y += 34
    for dl in [f"MST: {hd.mst_nguoi_ban}"] + _ngat_dong(d, tt["dia_chi"], fh, W - 60):
        d.text((W // 2, y), dl, fill="black", font=fh, anchor="ma")
        y += 30
    y += 10
    d.text((W // 2, y), "HÓA ĐƠN GIÁ TRỊ GIA TĂNG", fill="black", font=fd, anchor="ma")
    y += 34
    d.text((W // 2, y), "(Khởi tạo từ máy tính tiền)", fill="black", font=fh, anchor="ma")
    y += 40
    dt = hd.ngay_lap
    for dl in (f"Ký hiệu: {hd.ky_hieu}   Số: {hd.so_hoa_don}", f"Ngày: {dt:%d/%m/%Y} {rng.randint(7, 21):02d}:{rng.randint(0, 59):02d}",
               f"Khách hàng: {hd.ten_nguoi_mua}"):
        for x in _ngat_dong(d, dl, fh, W - 60):
            d.text((30, y), x, fill="black", font=fh)
            y += 30
    if hd.mst_nguoi_mua:
        d.text((30, y), f"MST người mua: {hd.mst_nguoi_mua}", fill="black", font=fh)
        y += 30
    d.text((30, y), "-" * 52, fill="black", font=fh)
    y += 30
    for dh in hd.dong_hang:
        for x in _ngat_dong(d, dh.ten_hang, fh, W - 60):
            d.text((30, y), x, fill="black", font=fh)
            y += 28
        d.text((50, y), f"{sl(dh.so_luong)} {dh.don_vi_tinh} x {tien(dh.don_gia)}  ({dh.thue_suat})", fill="black", font=fh)
        d.text((W - 30, y), tien(dh.thanh_tien), fill="black", font=fh, anchor="ra")
        y += 36
    d.text((30, y), "-" * 52, fill="black", font=fh)
    y += 34
    for nhan, gt, f in (("Cộng tiền hàng", hd.tong_tien_chua_thue, fh), ("Tiền thuế GTGT", hd.tien_thue, fh),
                        ("TỔNG CỘNG", hd.tong_thanh_toan, fd)):
        d.text((30, y), nhan, fill="black", font=f)
        d.text((W - 30, y), tien(gt), fill="black", font=f, anchor="ra")
        y += 38
    y += 20
    d.rectangle([W // 2 - 90, y, W // 2 + 90, y + 180], outline="black", width=3)
    for _ in range(140):  # giả lập mã QR tra cứu
        x0, y0 = W // 2 - 80 + rng.randrange(0, 160, 10), y + 10 + rng.randrange(0, 160, 10)
        d.rectangle([x0, y0, x0 + 9, y0 + 9], fill="black")
    y += 200
    d.text((W // 2, y), "Quét mã để tra cứu hóa đơn điện tử", fill="black", font=fh, anchor="ma")
    return tam.crop((0, 0, W, y + 60))


def ve_ban_hang(hd: HoaDon, tt: dict, rng: random.Random) -> Image.Image:
    """Hoá đơn bán hàng (không có thuế GTGT), phông chữ có chân, khung viền kép."""
    W, H = 1654, 1900
    img = Image.new("RGB", (W, H), (255, 253, 245))
    d = ImageDraw.Draw(img)
    fs = lambda c: _font(FONT_SERIF, c)  # noqa: E731
    fd = _font(FONT_DAM, 46)
    d.rectangle([40, 40, W - 40, H - 40], outline=(120, 40, 40), width=3)
    d.rectangle([55, 55, W - 55, H - 55], outline=(120, 40, 40), width=1)
    d.text((W // 2, 120), "HÓA ĐƠN BÁN HÀNG", fill=(120, 40, 40), font=fd, anchor="mm")
    dt = hd.ngay_lap
    d.text((W // 2, 180), f"Ngày {dt.day} tháng {dt.month} năm {dt.year}", fill="black", font=fs(30), anchor="mm")
    d.text((W - 100, 240), f"Ký hiệu: {hd.ky_hieu}    Số: {hd.so_hoa_don.zfill(7)}", fill="black", font=fs(28), anchor="rm")
    y = 300
    for dl in (f"Người bán: {hd.ten_nguoi_ban}", f"MST: {hd.mst_nguoi_ban}", f"Địa chỉ: {tt['dia_chi']}",
               f"Người mua: {hd.ten_nguoi_mua}" + (f"    MST: {hd.mst_nguoi_mua}" if hd.mst_nguoi_mua else "")):
        d.text((100, y), dl, fill="black", font=fs(30))
        y += 50
    y += 20
    cot = [90, 170, 820, 960, 1110, 1330, 1564]
    for i, t in enumerate(["TT", "Tên hàng hóa, dịch vụ", "ĐVT", "Số lượng", "Đơn giá", "Thành tiền"]):
        d.text(((cot[i] + cot[i + 1]) // 2, y + 25), t, fill="black", font=fs(26), anchor="mm")
    d.line([cot[0], y + 55, cot[-1], y + 55], fill="black", width=2)
    y += 70
    for k, dh in enumerate(hd.dong_hang, 1):
        dong_ten = _ngat_dong(d, dh.ten_hang, fs(27), cot[2] - cot[1] - 20)
        d.text((cot[0] + 30, y), str(k), fill="black", font=fs(27))
        for j, dl in enumerate(dong_ten):
            d.text((cot[1] + 10, y + 38 * j), dl, fill="black", font=fs(27))
        for i, gt in ((2, dh.don_vi_tinh), (3, sl(dh.so_luong)), (4, tien(dh.don_gia)), (5, tien(dh.thanh_tien))):
            d.text((cot[i + 1] - 15, y), gt, fill="black", font=fs(27), anchor="ra")
        y += 38 * len(dong_ten) + 18
    d.line([cot[0], y, cot[-1], y], fill="black", width=2)
    y += 25
    d.text((cot[-1] - 15, y), f"Cộng tiền bán hàng hóa, dịch vụ: {tien(hd.tong_thanh_toan)}", fill="black",
           font=_font(FONT_DAM, 30), anchor="ra")
    y += 60
    d.text((100, y), "Số tiền viết bằng chữ: " + doc_so(hd.tong_thanh_toan) + ".", fill="black", font=fs(28))
    _dong_dau(img, (1250, y + 200), rng)
    return img


def _dong_dau(img: Image.Image, tam, rng):
    """Dấu tròn màu đỏ, hơi trong suốt, đè lên chữ — như dấu công ty thật."""
    lop = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lop)
    x, y = tam
    r = 120
    mau = (210, 30, 30, 150)
    d.ellipse([x - r, y - r, x + r, y + r], outline=mau, width=7)
    d.ellipse([x - r + 22, y - r + 22, x + r - 22, y + r - 22], outline=mau, width=3)
    d.text((x, y), "★ ĐÃ KÝ ★", fill=mau, font=_font(FONT_DAM, 30), anchor="mm")
    lop = lop.rotate(rng.uniform(-25, 25), center=tam)
    img.paste(lop, (0, 0), lop)


def anh_chup(img: Image.Image, rng: random.Random, muc: float) -> Image.Image:
    """Giả lập ảnh chụp điện thoại. muc: 0 (nhẹ) .. 1 (nặng)."""
    w, h = img.size
    nen = Image.new("RGB", (int(w * 1.15), int(h * 1.12)), (rng.randint(90, 140),) * 3)
    nen.paste(img, ((nen.width - w) // 2, (nen.height - h) // 2))
    img = nen
    w, h = img.size
    lech = muc * 0.06  # phối cảnh: giấy không song song với ống kính
    he_so = _he_so_phoi_canh(
        [(0, 0), (w, 0), (w, h), (0, h)],
        [(w * rng.uniform(0, lech), h * rng.uniform(0, lech)), (w * (1 - rng.uniform(0, lech)), h * rng.uniform(0, lech)),
         (w * (1 - rng.uniform(0, lech)), h * (1 - rng.uniform(0, lech))), (w * rng.uniform(0, lech), h * (1 - rng.uniform(0, lech)))])
    img = img.transform((w, h), Image.PERSPECTIVE, he_so, Image.BICUBIC, fillcolor=(80, 80, 80))
    img = img.rotate(rng.uniform(-4, 4) * muc, expand=False, fillcolor=(80, 80, 80))
    toi = Image.linear_gradient("L").resize((w, h)).rotate(rng.choice([0, 90, 180, 270]))
    img = Image.composite(img, Image.new("RGB", (w, h), (30, 30, 30)), toi.point(lambda v: 255 - int(v * 0.45 * muc)))
    img = img.filter(ImageFilter.GaussianBlur(0.6 + 1.0 * muc))
    img = Image.blend(img, Image.effect_noise((w, h), 30).convert("RGB"), 0.05 + 0.07 * muc)
    img = img.resize((int(w * 0.6), int(h * 0.6)))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=int(70 - 30 * muc))
    return Image.open(io.BytesIO(buf.getvalue())).convert("RGB")


def _he_so_phoi_canh(dich, nguon):
    """Hệ số cho Image.PERSPECTIVE (giải hệ 8 ẩn bằng khử Gauss, không cần numpy)."""
    a = []
    for (x, y), (u, v) in zip(dich, nguon):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y, u])
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y, v])
    n = 8
    for i in range(n):
        p = max(range(i, n), key=lambda r: abs(a[r][i]))
        a[i], a[p] = a[p], a[i]
        for r in range(n):
            if r != i:
                k = a[r][i] / a[i][i]
                a[r] = [x - k * y for x, y in zip(a[r], a[i])]
    return [a[i][n] / a[i][i] for i in range(n)]


def main(so_luong=30, thu_muc=None):
    thu_muc = Path(thu_muc) if thu_muc else GOC / "data" / "bo_kho"
    mau, dap_an = thu_muc / "samples", thu_muc / "labels"
    mau.mkdir(parents=True, exist_ok=True)
    dap_an.mkdir(parents=True, exist_ok=True)
    rng = random.Random(7)
    ve = {"gtgt": ve_gtgt, "mtt": ve_mtt, "ban_hang": ve_ban_hang}
    for i in range(1, so_luong + 1):
        kieu = rng.choice(["gtgt", "gtgt", "mtt", "ban_hang"])
        hd, tt = tao_hoa_don(rng, kieu)
        ten = f"kho_{i:03d}"
        img = ve[kieu](hd, tt, rng)
        if i % 3 == 0:  # PDF dạng scan: chỉ có hình, không có lớp chữ để trích
            scan = img.convert("L").filter(ImageFilter.GaussianBlur(0.7)).rotate(rng.uniform(-1.2, 1.2), fillcolor=255)
            scan.convert("RGB").save(mau / f"{ten}.pdf", "PDF", resolution=200)
        else:
            anh_chup(img, rng, muc=rng.choice([0.3, 0.6, 1.0])).save(mau / f"{ten}.jpg", quality=92)
        ghi_xml(hd, tt["dia_chi"], mau / f"{ten}.xml")
        (dap_an / f"{ten}.json").write_text(hd.model_dump_json(indent=2), encoding="utf-8")
    print(f"Đã sinh {so_luong} hoá đơn 'khó' vào {mau}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 30, sys.argv[2] if len(sys.argv) > 2 else None)
