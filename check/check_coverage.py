import sqlite3

import pandas as pd

from src.data.universe import load_universe

conn = sqlite3.connect("data/liquidity.db")
df = pd.read_sql("select symbol, count(*) n, min(trading_date) first_day, "
                 "max(trading_date) last_day from daily_ohlc group by symbol", conn)
hnx = set(load_universe("hnx"))
print(df[df.symbol.isin(hnx)].sort_values("n").head(25).to_string(index=False))
print("Số phiên nhiều nhất:", df.n.max())
print("Mã HNX không có dữ liệu:", sorted(hnx - set(df.symbol)))