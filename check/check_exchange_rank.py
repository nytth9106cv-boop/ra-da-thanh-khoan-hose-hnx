from src.analytics.scoring import build_snapshot
from src.data import store
from src.data.universe import exchange_map, load_universe

conn = store.connect()
o, f, l = store.load_ohlc(conn), store.load_foreign(conn), store.load_limits(conn)
ex = exchange_map()
hose = set(load_universe("hose"))

full = build_snapshot(o, f, l, exchange_of=ex)
print(full["exchange"].value_counts())          # có dòng "Khác" không?

a = build_snapshot(o, f, l, universe=hose, exchange_of=ex).set_index("symbol")["risk_score"]
sub = lambda d: d[d["symbol"].isin(hose)] if not d.empty else d
b = build_snapshot(sub(o), sub(f), sub(l), universe=hose, exchange_of=ex).set_index("symbol")["risk_score"]
print("lệch điểm HOSE lớn nhất:", (a - b.reindex(a.index)).abs().max())   # mong đợi 0

print(full.groupby("exchange")["level"].value_counts().unstack(fill_value=0))