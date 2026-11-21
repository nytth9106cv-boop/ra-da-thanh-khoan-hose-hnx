from src.data import store
import pandas as pd

c = store.connect()
df = pd.read_sql_query(
    "select symbol, trading_date, close from daily_ohlc order by symbol, trading_date", c)
df["ret"] = df.groupby("symbol")["close"].pct_change()
df["abs"] = df["ret"].abs()
top = df.loc[df.groupby("symbol")["abs"].idxmax(), ["symbol", "trading_date", "abs"]]
print(top.sort_values("abs", ascending=False).round(4).to_string())