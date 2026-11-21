import numpy as np
import pandas as pd

from src.analytics.scoring import _fill_room, build_snapshot

DATES = pd.bdate_range("2026-08-03", periods=70)


def _ohlc(symbols, last_close=None):
    rng = np.random.default_rng(0)
    rows = [(s, t, 20.0 + rng.random() * 0.01, 1e6 * rng.random() + 1e5, 1e10 * rng.random() + 1e9)
            for s in symbols for t in DATES]
    o = pd.DataFrame(rows, columns=["symbol", "trading_date", "close", "volume", "value"])
    for s, c in (last_close or {}).items():
        o.loc[(o.symbol == s) & (o.trading_date == DATES[-1]), "close"] = c
    return o


def _foreign(per_symbol):
    """per_symbol: {mã: (remain_room, total_room) của NGÀY CUỐI}; các ngày trước đều hợp lệ 500/1000."""
    rows = []
    for s, (rem, tot) in per_symbol.items():
        for i, t in enumerate(DATES):
            r, tt = (rem, tot) if i == len(DATES) - 1 else (500.0, 1000.0)
            rows.append((s, t, 1, 1, 1e9, 1e9, r, tt))
    return pd.DataFrame(rows, columns=["symbol", "trading_date", "buy_vol", "sell_vol",
                                       "buy_val", "sell_val", "remain_room", "total_room"])


def test_fill_room_giu_gia_tri_hop_le_gan_nhat():
    f = _fill_room(_foreign({"A": (np.nan, np.nan)}))
    last = f.iloc[-1]
    assert last["remain_room"] == 500 and last["total_room"] == 1000


def test_fill_room_khong_che_so_am():
    f = _fill_room(_foreign({"A": (-5.0, 1000.0)}))
    assert f.iloc[-1]["remain_room"] == -5.0


def test_room_thieu_khong_bi_coi_la_bat_thuong():
    snap = build_snapshot(_ohlc(["A", "B"]), _foreign({"A": (np.nan, np.nan), "B": (-5.0, 1000.0)}), pd.DataFrame())
    a, b = snap.set_index("symbol").loc["A"], snap.set_index("symbol").loc["B"]
    assert not a["room_anomaly"] and a["room_used_pct"] == 0.5     # điền từ ngày hợp lệ trước đó
    assert b["room_anomaly"]                                          # số âm vẫn là bất thường thật


def test_het_room_can_tong_room_hop_le():
    snap = build_snapshot(_ohlc(["A", "B"]), _foreign({"A": (0.0, 1000.0), "B": (0.0, np.nan)}), pd.DataFrame())
    s = snap.set_index("symbol")
    assert s.loc["A", "room_full"]
    assert not s.loc["B", "room_full"]       # tổng room trống thì không kết luận "hết room"


def test_tran_san_chi_so_voi_gia_cung_ngay():
    limits = pd.DataFrame(
        [(s, str(DATES[-1].date()), 21400.0, 18600.0) for s in "AB"] +
        [(s, str((DATES[-1] + pd.Timedelta(days=3)).date()), 22000.0, 19000.0) for s in "AB"],   # phiên kế tiếp, chưa có giá
        columns=["symbol", "trading_date", "ceiling", "floor"])
    snap = build_snapshot(_ohlc(["A", "B"], {"A": 21.4, "B": 18.6}),      # giá ở nghìn đồng, trần/sàn ở đồng
                          pd.DataFrame(), limits).set_index("symbol")
    assert snap.loc["A", "at_ceiling"] and not snap.loc["A", "at_floor"]
    assert snap.loc["B", "at_floor"] and not snap.loc["B", "at_ceiling"]