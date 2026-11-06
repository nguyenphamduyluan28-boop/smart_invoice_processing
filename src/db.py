"""Lưu trữ bằng SQLite (có sẵn trong Python, không cần cài).

Khi lên production nhiều người dùng, đổi sang PostgreSQL — cấu trúc bảng giữ nguyên.

Hai kỹ thuật quan trọng ở đây:
  - Multi-tenant: mọi chứng từ thuộc về một khách hàng (khach_hang_id); mọi truy vấn đều lọc theo nó.
  - Idempotency: UNIQUE(khach_hang_id, sha256) — tải lên cùng một file 2 lần cũng chỉ lưu 1 lần.
"""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"


@contextmanager
def ket_noi():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def khoi_tao():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with ket_noi() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS khach_hang (
            id INTEGER PRIMARY KEY,
            ten TEXT NOT NULL,
            mst TEXT
        );
        CREATE TABLE IF NOT EXISTS chung_tu (
            id INTEGER PRIMARY KEY,
            khach_hang_id INTEGER NOT NULL REFERENCES khach_hang(id),
            ten_file TEXT NOT NULL,
            duong_dan TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            trang_thai TEXT NOT NULL DEFAULT 'DANG_XU_LY',  -- DANG_XU_LY | OK | CAN_DUYET | DA_DUYET | LOI
            du_lieu TEXT,        -- JSON HoaDon
            hach_toan TEXT,      -- JSON gợi ý tài khoản theo từng dòng
            canh_bao TEXT,       -- JSON danh sách cảnh báo
            loi TEXT,
            token_vao INTEGER DEFAULT 0,
            token_ra INTEGER DEFAULT 0,
            tao_luc TEXT NOT NULL,
            duyet_luc TEXT,
            UNIQUE (khach_hang_id, sha256)
        );
        """)
        # Bổ sung cột cho cơ sở dữ liệu tạo từ phiên bản cũ (migration đơn giản)
        cot = {r["name"] for r in c.execute("PRAGMA table_info(chung_tu)")}
        for ten, kieu in (("bat_dau_xu_ly", "TEXT"), ("so_giay_xu_ly", "REAL"), ("model", "TEXT"), ("ghi_chu", "TEXT"),
                          ("xac_nhan_ngoai_le", "TEXT"), ("du_lieu_ai", "TEXT")):
            if ten not in cot:
                c.execute(f"ALTER TABLE chung_tu ADD COLUMN {ten} {kieu}")
        c.execute("""CREATE TABLE IF NOT EXISTS doi_tac (
                         mst TEXT PRIMARY KEY,
                         ten TEXT NOT NULL,
                         nguon TEXT,            -- 'xml' | 'kế toán duyệt'
                         cap_nhat_luc TEXT)""")
        # Chứng từ đang xử lý dở khi server tắt sẽ kẹt mãi ở DANG_XU_LY -> đánh dấu để xử lý lại
        c.execute("""UPDATE chung_tu SET trang_thai = 'LOI',
                     loi = 'Bị gián đoạn vì server khởi động lại trong lúc xử lý — bấm Xử lý lại'
                     WHERE trang_thai = 'DANG_XU_LY'""")


def _row(r):
    if r is None:
        return None
    d = dict(r)
    for k in ("du_lieu", "hach_toan", "canh_bao", "ghi_chu", "du_lieu_ai"):
        d[k] = json.loads(d[k]) if d.get(k) else None
    return d


# ---- Khách hàng ----
def them_khach_hang(ten: str, mst: str | None) -> int:
    with ket_noi() as c:
        return c.execute("INSERT INTO khach_hang (ten, mst) VALUES (?, ?)", (ten.strip(), (mst or "").strip() or None)).lastrowid


def ds_khach_hang():
    with ket_noi() as c:
        return [dict(r) for r in c.execute("SELECT * FROM khach_hang ORDER BY ten")]


def lay_khach_hang(kh_id: int):
    with ket_noi() as c:
        r = c.execute("SELECT * FROM khach_hang WHERE id = ?", (kh_id,)).fetchone()
        return dict(r) if r else None


# ---- Chứng từ ----
def tim_theo_sha(kh_id: int, sha: str):
    with ket_noi() as c:
        r = c.execute("SELECT id FROM chung_tu WHERE khach_hang_id = ? AND sha256 = ?", (kh_id, sha)).fetchone()
        return r["id"] if r else None


def them_chung_tu(kh_id: int, ten_file: str, duong_dan: str, sha: str) -> int:
    with ket_noi() as c:
        return c.execute(
            "INSERT INTO chung_tu (khach_hang_id, ten_file, duong_dan, sha256, tao_luc) VALUES (?, ?, ?, ?, ?)",
            (kh_id, ten_file, duong_dan, sha, datetime.now().isoformat(timespec="seconds")),
        ).lastrowid


def lay_chung_tu(ct_id: int):
    with ket_noi() as c:
        return _row(c.execute("SELECT * FROM chung_tu WHERE id = ?", (ct_id,)).fetchone())


def ds_chung_tu(kh_id: int, trang_thai: str | None = None):
    sql = "SELECT * FROM chung_tu WHERE khach_hang_id = ?"
    args = [kh_id]
    if trang_thai:
        sql += " AND trang_thai = ?"
        args.append(trang_thai)
    with ket_noi() as c:
        return [_row(r) for r in c.execute(sql + " ORDER BY id DESC", args)]


def cap_nhat(ct_id: int, **truong):
    for k in ("du_lieu", "hach_toan", "canh_bao", "ghi_chu", "du_lieu_ai"):
        if k in truong and not isinstance(truong[k], str) and truong[k] is not None:
            truong[k] = json.dumps(truong[k], ensure_ascii=False, default=str)
    cot = ", ".join(f"{k} = ?" for k in truong)
    with ket_noi() as c:
        c.execute(f"UPDATE chung_tu SET {cot} WHERE id = ?", (*truong.values(), ct_id))


def tim_hoa_don_trung(kh_id: int, mst_ban: str, ky_hieu: str | None, so_hd: str, bo_qua_id: int):
    """Cùng người bán + ký hiệu + số hoá đơn = cùng một hoá đơn, dù file khác nhau
    (ví dụ khách gửi cả XML lẫn PDF của cùng hoá đơn)."""
    with ket_noi() as c:
        r = c.execute(
            """SELECT id FROM chung_tu
               WHERE khach_hang_id = ? AND id != ? AND trang_thai != 'LOI'
                 AND json_extract(du_lieu, '$.mst_nguoi_ban') = ?
                 AND IFNULL(json_extract(du_lieu, '$.ky_hieu'), '') = IFNULL(?, '')
                 AND ltrim(json_extract(du_lieu, '$.so_hoa_don'), '0') = ltrim(?, '0')
               ORDER BY id LIMIT 1""",
            (kh_id, bo_qua_id, mst_ban, ky_hieu, so_hd),
        ).fetchone()
        return r["id"] if r else None


# ---- Danh bạ đối tác (MST -> tên chuẩn) ----
def tra_doi_tac(mst: str) -> str | None:
    with ket_noi() as c:
        r = c.execute("SELECT ten FROM doi_tac WHERE mst = ?", (mst,)).fetchone()
        return r["ten"] if r else None


def luu_doi_tac(mst: str, ten: str, nguon: str):
    with ket_noi() as c:
        c.execute(
            """INSERT INTO doi_tac (mst, ten, nguon, cap_nhat_luc) VALUES (?, ?, ?, ?)
               ON CONFLICT(mst) DO UPDATE SET ten = excluded.ten, nguon = excluded.nguon,
                                              cap_nhat_luc = excluded.cap_nhat_luc""",
            (mst, ten, nguon, datetime.now().isoformat(timespec="seconds")),
        )


def so_doi_tac() -> int:
    with ket_noi() as c:
        return c.execute("SELECT COUNT(*) FROM doi_tac").fetchone()[0]
