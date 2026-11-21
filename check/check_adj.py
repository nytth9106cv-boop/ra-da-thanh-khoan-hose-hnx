from src.data import store
import pandas as pd

c = store.connect()
df = pd.read_sql_query(
    "select symbol, trading_date, close from daily_ohlc order by symbol, trading_date", c)
df["ret"] = df.groupby("symbol")["close"].pct_change()
bad = df[df["ret"].abs() > 0.075]
print(bad.round(3).to_string())
print(len(bad), "dong")