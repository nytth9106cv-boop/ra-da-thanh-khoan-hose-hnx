import sqlite3
from pathlib import Path

from src.data import store

SRC = Path("data/liquidity.db")
DST = Path("data_sample/liquidity_sample.db")
KEEP_DAYS = 200          # ngày lịch gần nhất, khoảng 140 phiên

DST.parent.mkdir(exist_ok=True)
DST.unlink(missing_ok=True)

con = sqlite3.connect(DST)
con.executescript(store.SCHEMA)
con.execute("ATTACH DATABASE ? AS src", (str(SRC),))

last = con.execute("SELECT MAX(trading_date) FROM src.daily_ohlc").fetchone()[0]
cut = con.execute("SELECT date(?, ?)", (last, f"-{KEEP_DAYS} days")).fetchone()[0]
print("Ngày mới nhất:", last, "| lấy từ:", cut)

for t in ("daily_ohlc", "foreign_flow", "price_limits"):
    con.execute(f"INSERT INTO {t} SELECT * FROM src.{t} WHERE trading_date >= ?", (cut,))

ddl = con.execute(
    "SELECT sql FROM src.sqlite_master WHERE type='table' AND name='corporate_actions'"
).fetchone()
if ddl:
    con.execute(ddl[0])
    con.execute("INSERT INTO corporate_actions SELECT * FROM src.corporate_actions")
con.commit()

for t in ("daily_ohlc", "foreign_flow", "price_limits", "corporate_actions"):
    try:
        print(t, con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
    except sqlite3.OperationalError:
        pass
con.close()
print("Kích thước:", round(DST.stat().st_size / 1024 / 1024, 1), "MB")