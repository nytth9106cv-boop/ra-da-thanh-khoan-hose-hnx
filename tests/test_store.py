from src.data import store

OHLC_ROWS = [
    {"symbol": "FPT", "tradingDate": "2026/11/16", "open": "50000", "high": "50900",
     "low": "49400", "close": "49400", "volume": "6152200", "value": "303918680000"},
    {"symbol": "FPT", "tradingDate": "2026/11/13", "open": "1", "high": "2",
     "low": "1", "close": "2", "volume": "", "value": "5"},
]


def test_save_ohlc_sorts_dates_and_handles_empty(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    assert store.save_ohlc(conn, OHLC_ROWS) == 2
    df = store.load_ohlc(conn, "FPT")
    assert list(df["trading_date"].dt.strftime("%Y-%m-%d")) == ["2026-11-13", "2026-11-16"]
    assert df["volume"].isna().iloc[0]          # chuỗi rỗng -> NULL
    conn.close()


def test_save_ohlc_is_idempotent(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    store.save_ohlc(conn, OHLC_ROWS)
    store.save_ohlc(conn, OHLC_ROWS)            # nạp lại không bị trùng dòng
    assert conn.execute("select count(*) from daily_ohlc").fetchone()[0] == 2
    conn.close()


def test_save_foreign(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    rows = [{"symbol": "FPT", "tradingDate": "2026/11/12", "totalForeignBuy": "1419143",
             "totalForeignSell": "10427447", "totalForeignBuyValue": "70647623200",
             "totalForeignSellValue": "520598023450", "remainForeignRoom": "424588552"}]
    assert store.save_foreign(conn, rows) == 1
    df = store.load_foreign(conn, "FPT")
    assert df["sell_val"].iloc[0] == 520598023450
    conn.close()


def test_save_limits_keeps_only_vn30(tmp_path):
    conn = store.connect(tmp_path / "t.db")
    rows = [
        {"board": "HOSE", "symbol": "FPT", "tradingDate": "2026/11/16",
         "ceiling": 53000, "floor": 46000, "refPrice": 49600},
        {"board": "UPCOM", "symbol": "AAV", "tradingDate": "2026/11/16",
         "ceiling": 6500, "floor": 4900, "refPrice": 5700},
    ]
    assert store.save_limits(conn, rows, {"FPT"}) == 1
    conn.close()