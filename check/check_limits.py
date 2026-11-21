import sqlite3
import pandas as pd

c = sqlite3.connect("data/liquidity.db")
o = pd.read_sql_query("select symbol, trading_date, close from daily_ohlc", c)
l = pd.read_sql_query("select symbol, trading_date, ceiling, floor, ref_price from price_limits", c)
print("Ngày giá mới nhất:", o.trading_date.max(), "| các ngày trong price_limits:", sorted(l.trading_date.unique())[-5:])
m = o.merge(l, on=["symbol", "trading_date"])
for col in ["close", "ceiling", "floor", "ref_price"]:
    m[col] = pd.to_numeric(m[col], errors="coerce")
last = m[m.trading_date == m.trading_date.max()]
print("Số mã có cả giá và trần/sàn ở ngày mới nhất:", len(last))
print(last.head(5).to_string(index=False))
print("Chạm trần:", int((last.close >= last.ceiling).sum()), "| chạm sàn:", int((last.close <= last.floor).sum()))