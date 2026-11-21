import numpy as np
import pandas as pd


def amihud(close: pd.Series, value: pd.Series, window: int = 20,
           min_periods: int = 10) -> pd.Series:
    """Amihud (2002): trung bình |lợi suất ngày| / giá trị giao dịch (tỷ đồng).
    Cửa sổ trượt `window` phiên; cần tối thiểu `min_periods` ngày có giao dịch
    (theo tiền lệ Duong et al. 2024: loại quan sát dưới 10 ngày giao dịch/tháng).
    Nếu window nhỏ hơn min_periods thì dùng window."""
    ret = close.pct_change().abs()
    val_ty = (value / 1e9).replace(0, np.nan)
    return (ret / val_ty).rolling(window, min_periods=min(min_periods, window)).mean()


def avg_daily_value(value: pd.Series, window: int = 20) -> pd.Series:
    """Giá trị giao dịch bình quân ngày (ADV) trong cửa sổ gần nhất."""
    return value.rolling(window, min_periods=window).mean()


def days_to_liquidate(position_value: float, adv_value: pd.Series,
                      participation: float = 0.2) -> pd.Series:
    """Số phiên cần để bán hết vị thế, nếu mỗi phiên chỉ chiếm `participation`
    (mặc định 20%) giá trị giao dịch của thị trường."""
    return position_value / (participation * adv_value.replace(0, np.nan))


def volume_zscore(volume: pd.Series, window: int = 60) -> pd.Series:
    """Z-score khối lượng hôm nay so với `window` phiên trước đó (không gồm hôm nay)."""
    mean = volume.rolling(window, min_periods=window).mean().shift(1)
    std = volume.rolling(window, min_periods=window).std().shift(1)
    return (volume - mean) / std.replace(0, np.nan)