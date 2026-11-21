import numpy as np
import pandas as pd


def _sell_streak(net: pd.Series) -> pd.Series:
    """Số phiên bán ròng liên tiếp tính đến từng ngày (mua ròng thì về 0)."""
    neg = (net < 0).astype(int)
    group = (neg == 0).cumsum()
    return neg.groupby(group).cumsum()


def add_foreign_metrics(foreign: pd.DataFrame, ohlc: pd.DataFrame) -> pd.DataFrame:
    """Thêm chỉ số khối ngoại cho mỗi (mã, ngày).

    foreign: kết quả store.load_foreign; ohlc: kết quả store.load_ohlc. Đơn vị: đồng.
    """
    df = foreign.merge(
        ohlc[["symbol", "trading_date", "value"]],
        on=["symbol", "trading_date"], how="left",
    ).sort_values(["symbol", "trading_date"]).reset_index(drop=True)
    df["value"] = df["value"].fillna(0)
    
    df = df.dropna(subset=["buy_val", "sell_val"]).reset_index(drop=True)
  
    df["net_val"] = df["buy_val"] - df["sell_val"]
    df["net_vol"] = df["buy_vol"] - df["sell_vol"]

    g = df.groupby("symbol")
    df["net_val_5d"] = g["net_val"].transform(lambda s: s.rolling(5, min_periods=5).sum())
    df["net_val_20d"] = g["net_val"].transform(lambda s: s.rolling(20, min_periods=20).sum())
    df["adv20"] = g["value"].transform(lambda s: s.rolling(20, min_periods=20).mean())

    # Bán ròng 5 phiên so với giá trị giao dịch 5 phiên bình quân (âm = bán ròng)
    df["net_5d_ratio"] = df["net_val_5d"] / (5 * df["adv20"].replace(0, np.nan))
    df["sell_streak"] = g["net_val"].transform(_sell_streak)

    total = df["total_room"].replace(0, np.nan)
    # Room âm hoặc tổng room <= 0: dữ liệu bất thường, không diễn giải
    df["room_anomaly"] = (df["total_room"] <= 0) | (df["remain_room"] < 0) | (df["remain_room"] > df["total_room"])
    df["room_full"] = (df["remain_room"] == 0) & (df["total_room"] > 0) & ~df["room_anomaly"]
    df["room_used_pct"] = (1 - df["remain_room"] / total).where(~df["room_anomaly"])
    return df