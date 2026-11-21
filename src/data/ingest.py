import argparse
import time
from datetime import datetime, timedelta

from src.data import store
from src.data.universe import SOURCES, load_universe, sync_universe
from src.ssi_api.client import SSIClient

OVERLAP_DAYS = 7   # lấy lại vài ngày cuối để bù dữ liệu công bố muộn (như GVR)


def _start(last: str | None, default: str) -> str:
    """Ngày bắt đầu: mã mới thì lấy từ default, mã đã có thì lùi 7 ngày so với ngày cuối."""
    if not last:
        return default
    d = datetime.strptime(last, "%Y-%m-%d") - timedelta(days=OVERLAP_DAYS)
    return max(d.strftime("%Y/%m/%d"), default)


def ingest(symbols: list[str], date_from: str, date_to: str, limits_days: int) -> None:
    client = SSIClient()
    conn = store.connect()
    last_o = store.last_dates(conn, "daily_ohlc")
    last_f = store.last_dates(conn, "foreign_flow")
    failed: list[str] = []
    t0 = time.time()

    for i, sym in enumerate(symbols, 1):
        try:
            n1 = store.save_ohlc(conn, client.ohlc_daily(
                sym, _start(last_o.get(sym), date_from), date_to))
            n2 = store.save_foreign(conn, client.securities_summary(
                sym, _start(last_f.get(sym), date_from), date_to))
            print(f"[{i}/{len(symbols)}] {sym}: ohlc {n1}, khoi ngoai {n2} "
                  f"({time.time() - t0:.0f}s)")
        except Exception as e:                  # 1 mã lỗi không làm hỏng cả đợt
            failed.append(sym)
            print(f"[{i}/{len(symbols)}] {sym}: LOI {str(e)[:150]}")

    if limits_days > 0:
        start = datetime.strptime(date_to, "%Y/%m/%d") - timedelta(days=limits_days)
        try:
            rows = client.master_data(start.strftime("%Y/%m/%d"), date_to)
            n3 = store.save_limits(conn, rows, set(symbols))
            print(f"tran/san: doc {len(rows)} dong, luu {n3} dong")
        except Exception as e:
            print("tran/san: LOI", str(e)[:150])

    conn.close()
    if failed:
        print("Ma loi:", ",".join(failed))
        print("Chay lai: python -m src.data.ingest --symbols", ",".join(failed))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Nap du lieu SSI vao SQLite")
    ap.add_argument("--universe", default="vn30", choices=sorted(SOURCES))
    ap.add_argument("--sync", action="store_true", help="lay lai danh sach ma tu SSI truoc")
    ap.add_argument("--symbols", default="", help="vd FPT,VNM (ghi de --universe)")
    ap.add_argument("--limit", type=int, default=0, help="chi nap N ma dau (de thu)")
    ap.add_argument("--from", dest="date_from", default="2025/01/01")
    ap.add_argument("--to", dest="date_to", default=datetime.now().strftime("%Y/%m/%d"))
    ap.add_argument("--limits-days", type=int, default=5,
                    help="so ngay gan nhat lay tran/san (0 = bo qua)")
    a = ap.parse_args()

    if a.sync:
        sync_universe(a.universe)
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()] \
        or load_universe(a.universe)
    if a.limit:
        syms = syms[:a.limit]
    ingest(syms, a.date_from, a.date_to, a.limits_days)