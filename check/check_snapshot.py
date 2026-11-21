from src.analytics.scoring import build_basket_snapshot
from src.data import store
from src.data.universe import load_universe

conn = store.connect()
ohlc, foreign, limits = store.load_ohlc(conn), store.load_foreign(conn), store.load_limits(conn)
for b in ("vn30", "vn100", "hose", "hnx"):
    s = build_basket_snapshot(ohlc, foreign, limits, load_universe(b), b.upper())
    print(b.upper(), len(s), "mã |", s["level"].value_counts().to_dict())
    print(s[s.symbol.isin(["FPT", "HPG", "TET", "SRA"])][["symbol", "traded_days", "risk_score", "level"]].to_string(index=False))