import numpy as np
import pandas as pd
import pytest

from src.analytics.scoring import build_snapshot

DATES = pd.bdate_range("2026-08-03", periods=70)
EMPTY = pd.DataFrame()


def _rows(sym, idx, value):
    return [(sym, DATES[i], 20.0, 1e6, value) for i in idx]


def _df(rows):
    return pd.DataFrame(rows, columns=["symbol", "trading_date", "close", "volume", "value"])


def test_ngay_khong_giao_dich_tinh_bang_0():
    rows = _rows("A", range(70), 2e10) + _rows("B", [0] + list(range(50, 70, 4)), 2e10)
    s = build_snapshot(_df(rows), EMPTY, EMPTY).set_index("symbol")
    assert s.loc["B", "n_sessions"] == 70
    assert s.loc["B", "traded_days"] == 5
    assert s.loc["B", "adv"] == pytest.approx(5 * 2e10 / 20)     # 5 ngày có giao dịch / 20 phiên
    assert s.loc["A", "adv"] == pytest.approx(2e10)
    assert s.loc["B", "thin"] and not s.loc["A", "thin"]
    assert np.isnan(s.loc["B", "amihud"])                        # dưới 10 ngày có giao dịch


def test_xep_hang_rieng_tung_san():
    rows = []
    for i, v in enumerate([1e10, 2e10, 3e10], 1):
        rows += _rows(f"H{i}", range(70), v)
    for i, v in enumerate([1e8, 2e8, 3e8], 1):
        rows += _rows(f"N{i}", range(70), v)
    ex = {f"H{i}": "HOSE" for i in (1, 2, 3)} | {f"N{i}": "HNX" for i in (1, 2, 3)}
    ohlc = _df(rows)
    both = build_snapshot(ohlc, EMPTY, EMPTY, exchange_of=ex).set_index("symbol")
    only = build_snapshot(ohlc[ohlc.symbol.str.startswith("H")], EMPTY, EMPTY,
                          exchange_of=ex).set_index("symbol")
    for s in ("H1", "H2", "H3"):                                 # thêm HNX không đổi điểm HOSE
        assert both.loc[s, "risk_score"] == pytest.approx(only.loc[s, "risk_score"])