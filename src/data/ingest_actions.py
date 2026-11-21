"""Nạp sự kiện quyền doanh nghiệp (cổ tức, thưởng cổ phiếu...) từ SSI vào bảng corporate_actions.

Chạy từ thư mục gốc dự án (venv đang bật):
    python -m src.data.ingest_actions --days 365

Chỉ gọi API xác thực và API dữ liệu (data/corporateActions). Không có lệnh giao dịch nào.
SSI chỉ cho hỏi tối đa 5 ngày mỗi lần, nên chương trình chia khoảng thời gian thành các đoạn 5 ngày
và hỏi tất cả các mã cùng lúc (không truyền symbol), rồi lọc theo mã khi hiển thị.
"""
import argparse
import os
import sqlite3
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "data" / "liquidity.db"
SPAN_DAYS = 4        # to - from = 4 ngày, nằm trong giới hạn "không quá 5 ngày" của SSI
PAGE_SIZE = 100
PAUSE = 0.4          # giây nghỉ giữa hai lần gọi, để không vượt giới hạn tần suất
MAX_RETRY = 5


class AuthExpired(Exception):
    pass


def get_token(base: str, key: str, secret: str) -> str:
    r = requests.post(f"{base}/api/v3/auth/token", json={"apiKey": key, "apiSecret": secret}, timeout=30)
    r.raise_for_status()
    return r.json()["accessToken"]


def call(base: str, token: str, params: dict):
    """Gọi corporateActions. Trả None nếu không có dữ liệu (204)."""
    for attempt in range(MAX_RETRY):
        r = requests.get(f"{base}/api/v3/data/corporateActions", params=params, timeout=30,
                         headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"})
        if r.status_code == 204:
            return None
        if r.status_code == 401:
            raise AuthExpired()
        if r.status_code == 429 or r.status_code >= 500:
            wait = 2 * (attempt + 1)
            print(f"  máy chủ trả {r.status_code}, chờ {wait}s rồi thử lại", file=sys.stderr)
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"Gọi thất bại sau {MAX_RETRY} lần: {params}")


def windows(days: int):
    end_all = date.today()
    start = end_all - timedelta(days=days)
    while start <= end_all:
        end = min(start + timedelta(days=SPAN_DAYS), end_all)
        yield start, end
        start = end + timedelta(days=1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=365, help="Số ngày lùi lại từ hôm nay (mặc định 365)")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    base = os.getenv("SSI_API_URL", "https://api.ssi.com.vn").rstrip("/")
    key, secret = os.getenv("SSI_API_KEY"), os.getenv("SSI_API_SECRET")
    if not key or not secret:
        print("Thiếu SSI_API_KEY hoặc SSI_API_SECRET trong tệp .env", file=sys.stderr)
        return 1

    token = get_token(base, key, secret)
    rows = []
    wins = list(windows(args.days))
    for i, (a, b) in enumerate(wins, 1):
        page = 1
        while True:
            params = {"from": a.strftime("%Y/%m/%d"), "to": b.strftime("%Y/%m/%d"),
                      "pageIndex": page, "pageSize": PAGE_SIZE, "language": "vn"}
            try:
                js = call(base, token, params)
            except AuthExpired:
                token = get_token(base, key, secret)
                js = call(base, token, params)
            time.sleep(PAUSE)
            if not js or not js.get("data"):
                break
            for d in js["data"]:
                rows.append((d.get("symbol", ""), d.get("eventTitle", ""), d.get("exrightDate", ""),
                             d.get("recordDate", ""), d.get("issueDate", ""), d.get("exchange", ""), d.get("ratio", "")))
            if page >= int(js.get("pagesCount") or 1):
                break
            page += 1
        if i % 10 == 0 or i == len(wins):
            print(f"Đã xong {i}/{len(wins)} đoạn, {len(rows)} sự kiện")

    conn = sqlite3.connect(DB)
    try:
        conn.execute("create table if not exists corporate_actions(symbol text, event_title text, exright_date text, "
                     "record_date text, issue_date text, exchange text, ratio text, "
                     "primary key(symbol, event_title, exright_date, record_date))")
        conn.executemany("insert or replace into corporate_actions values(?,?,?,?,?,?,?)", rows)
        conn.commit()
        n = conn.execute("select count(*) from corporate_actions").fetchone()[0]
    finally:
        conn.close()
    print(f"Xong. Bảng corporate_actions hiện có {n} dòng.")
    return 0


if __name__ == "__main__":
    sys.exit(main())