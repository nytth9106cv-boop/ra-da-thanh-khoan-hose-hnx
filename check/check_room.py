import sqlite3
import pandas as pd

c = sqlite3.connect("data/liquidity.db")
f = pd.read_sql_query("select symbol, trading_date, remain_room, total_room from foreign_flow", c)
last = f["trading_date"].max()
now = f[f["trading_date"] == last]
bad = now[now["total_room"].isna() | (now["total_room"] <= 0)]
ever_ok = f[f["total_room"] > 0].groupby("symbol")["trading_date"].max()
has_hist = bad["symbol"].isin(ever_ok.index)
rem = bad["remain_room"].fillna(0)

print("Ngày mới nhất:", last, "| số mã thiếu hạn mức:", len(bad))
print("Từng có hạn mức hợp lệ ở ngày khác:", int(has_hist.sum()))
print("Chưa từng có hạn mức hợp lệ:", int((~has_hist).sum()))
print("Trong nhóm thiếu, remain_room bằng 0:", int((rem == 0).sum()), "| lớn hơn 0:", int((rem > 0).sum()))
print(bad.head(10).to_string(index=False))