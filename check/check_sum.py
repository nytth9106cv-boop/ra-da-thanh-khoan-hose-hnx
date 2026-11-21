import pandas as pd
from src.data import store
from src.data.universe import load_universe

c = store.connect()
v30 = load_universe("vn30")
o, f = store.load_ohlc(c), store.load_foreign(c)
d = pd.Timestamp("2026-11-13")
o, f = o[o.symbol.isin(v30)], f[f.symbol.isin(v30)]
print("ohlc tong value:", o[o.trading_date == d]["value"].sum() / 1e12, "nghin ty")
x = f[f.trading_date == d]
print("khoi ngoai rong:", (x["buy_val"] - x["sell_val"]).sum() / 1e9, "ty")