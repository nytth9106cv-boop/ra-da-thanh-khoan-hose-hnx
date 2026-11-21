import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path("data") / "liquidity.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_ohlc (
    symbol TEXT NOT NULL, trading_date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL, value REAL,
    PRIMARY KEY (symbol, trading_date)
);
CREATE TABLE IF NOT EXISTS foreign_flow (
    symbol TEXT NOT NULL, trading_date TEXT NOT NULL,
    buy_vol REAL, sell_vol REAL, buy_val REAL, sell_val REAL,
    remain_room REAL, total_room REAL,
    PRIMARY KEY (symbol, trading_date)
);
CREATE TABLE IF NOT EXISTS price_limits (
    symbol TEXT NOT NULL, trading_date TEXT NOT NULL,
    board TEXT, ceiling REAL, floor REAL, ref_price REAL,
    PRIMARY KEY (symbol, trading_date)
);
"""


def connect(db_path: Path | str = DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def _num(x):
    """Chuỗi -> số; rỗng hoặc lỗi -> None (NULL trong DB)."""
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _date(s) -> str:
    """'2026/11/16' hoặc '2026/11/16 00:00:00' -> '2026-11-16'."""
    return str(s).strip()[:10].replace("/", "-")


def save_ohlc(conn: sqlite3.Connection, rows: list[dict]) -> int:
    data = [
        (r["symbol"], _date(r["tradingDate"]), _num(r.get("open")), _num(r.get("high")),
         _num(r.get("low")), _num(r.get("close")), _num(r.get("volume")), _num(r.get("value")))
        for r in rows if r.get("symbol") and r.get("tradingDate")
    ]
    conn.executemany("INSERT OR REPLACE INTO daily_ohlc VALUES (?,?,?,?,?,?,?,?)", data)
    conn.commit()
    return len(data)


def save_foreign(conn: sqlite3.Connection, rows: list[dict]) -> int:
    data = [
        (r["symbol"], _date(r["tradingDate"]),
         _num(r.get("totalForeignBuy")), _num(r.get("totalForeignSell")),
         _num(r.get("totalForeignBuyValue")), _num(r.get("totalForeignSellValue")),
         _num(r.get("remainForeignRoom")), _num(r.get("totalForeignRoom")))
        for r in rows if r.get("symbol") and r.get("tradingDate")
    ]
    conn.executemany("INSERT OR REPLACE INTO foreign_flow VALUES (?,?,?,?,?,?,?,?)", data)
    conn.commit()
    return len(data)


def save_limits(conn: sqlite3.Connection, rows: list[dict], symbols: set[str]) -> int:
    data = [
        (r["symbol"], _date(r["tradingDate"]), r.get("board") or r.get("exchange"),
         _num(r.get("ceiling")), _num(r.get("floor")), _num(r.get("refPrice")))
        for r in rows if r.get("symbol") in symbols and r.get("tradingDate")
    ]
    conn.executemany("INSERT OR REPLACE INTO price_limits VALUES (?,?,?,?,?,?)", data)
    conn.commit()
    return len(data)


def _load(conn: sqlite3.Connection, table: str, symbol: str | None) -> pd.DataFrame:
    sql = f"SELECT * FROM {table}"
    params: tuple = ()
    if symbol:
        sql += " WHERE symbol = ?"
        params = (symbol,)
    df = pd.read_sql_query(sql, conn, params=params)
    df["trading_date"] = pd.to_datetime(df["trading_date"])
    return df.sort_values(["symbol", "trading_date"]).reset_index(drop=True)


def load_ohlc(conn, symbol: str | None = None) -> pd.DataFrame:
    return _load(conn, "daily_ohlc", symbol)


def load_foreign(conn, symbol: str | None = None) -> pd.DataFrame:
    return _load(conn, "foreign_flow", symbol)

def load_limits(conn, symbol: str | None = None) -> pd.DataFrame:
    return _load(conn, "price_limits", symbol)

def last_dates(conn: sqlite3.Connection, table: str) -> dict[str, str]:
    """Ngày cuối cùng đã có của từng mã, dạng 'YYYY-MM-DD'."""
    rows = conn.execute(f"SELECT symbol, MAX(trading_date) FROM {table} GROUP BY symbol")
    return dict(rows.fetchall())