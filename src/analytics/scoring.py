import numpy as np
import pandas as pd

from src.finance.foreign_flow import add_foreign_metrics
from src.finance.liquidity import amihud, avg_daily_value, days_to_liquidate, volume_zscore

# Trọng số bằng nhau: baseline theo Nardo et al. (2008); kiểm tra độ nhạy ở rank_stability
DEFAULT_WEIGHTS = {"amihud": 0.5, "dtl": 0.5}
ALERT_PCT = 0.10      # phân vị cảnh báo: người dùng chỉnh, không có nguồn
DTL_ALERT = 5.0       # mốc cảnh báo số phiên: người dùng chỉnh, không có nguồn
MIN_SESSIONS = 61     # volume_zscore cần 60 phiên trước + phiên hiện tại
MIN_TRADED = 10       # tối thiểu ngày có giao dịch trong cửa sổ: cùng tiêu chí với amihud (Duong et al. 2024)
def _fill_room(foreign, limit=10):
    """Khi SSI để trống room ngày nào thì giữ giá trị hợp lệ gần nhất (room chỉ đổi khi nước ngoài giao dịch).
    Số bất thường thật (âm, còn lại vượt tổng) giữ nguyên để còn báo."""
    f = foreign.sort_values(["symbol", "trading_date"]).copy()
    for c in ("remain_room", "total_room"):
        f[c] = pd.to_numeric(f[c], errors="coerce")
    miss = f["remain_room"].isna() | f["total_room"].isna() | (f["total_room"] <= 0)
    good = ~miss & (f["remain_room"] >= 0) & (f["remain_room"] <= f["total_room"])
    for c in ("remain_room", "total_room"):
        filled = f[c].where(good).groupby(f["symbol"]).ffill(limit=limit)
        f[c] = f[c].where(~miss, filled)
    return f
def _to_dong(x):
    """Giá có thể ở đơn vị nghìn đồng (22,5) hoặc đồng (22500); quy hết về đồng để so sánh."""
    return x.where(x >= 1000, x * 1000)

def _symbol_metrics(ohlc, position_value, participation, window):
    """Mỗi mã được gắn vào lịch phiên chung của thị trường, từ ngày mã đó có dữ liệu đầu tiên.
    SSI không trả dòng cho ngày không giao dịch, nên ngày thiếu = khối lượng, giá trị 0;
    giá đóng cửa giữ nguyên giá gần nhất."""
    calendar = np.sort(ohlc["trading_date"].unique())
    rows = []
    for sym, g in ohlc.groupby("symbol"):
        g = g.sort_values("trading_date").drop_duplicates("trading_date").set_index("trading_date")
        full = g.reindex(calendar[calendar >= g.index[0]])
        full["close"] = full["close"].ffill()
        full[["volume", "value"]] = full[["volume", "value"]].fillna(0)
        adv = avg_daily_value(full["value"], window)
        rows.append({
            "symbol": sym,
            "date": g.index[-1],                         # ngày dữ liệu thật gần nhất (để báo stale)
            "close": g["close"].iloc[-1],
            "n_sessions": len(full),
            "traded_days": int((full["value"].tail(window) > 0).sum()),
            "adv": adv.iloc[-1],
            "amihud": amihud(full["close"], full["value"], window).iloc[-1],
            "days_to_liq": days_to_liquidate(position_value, adv, participation).iloc[-1],
            "vol_z": volume_zscore(full["volume"]).iloc[-1],
        })
    return pd.DataFrame(rows)


def build_snapshot(ohlc, foreign, limits, universe=None, position_value=50e9,
                   participation=0.2, weights=None, window=20,
                   alert_pct=ALERT_PCT, dtl_alert=DTL_ALERT, exchange_of=None):
    """1 dòng/mã. Xếp hạng tính riêng trong từng sàn (nếu có exchange_of), sau đó mới lọc theo rổ."""
    weights = weights or DEFAULT_WEIGHTS
    snap = _symbol_metrics(ohlc, position_value, participation, window)
    snap["stale"] = snap["date"] < snap["date"].max()
    snap["thin"] = snap["traded_days"] < min(MIN_TRADED, window)
    ex_map = exchange_of or {}
    snap["exchange"] = snap["symbol"].map(lambda s: ex_map.get(s, "Khác"))
    snap["s_amihud"] = snap.groupby("exchange")["amihud"].rank(pct=True)
    snap["s_dtl"] = snap.groupby("exchange")["days_to_liq"].rank(pct=True)
    fcols = ["net_5d_ratio", "sell_streak", "room_used_pct",
             "foreign_date", "room_anomaly", "room_full"]
    if not foreign.empty:
        foreign = _fill_room(foreign)
        f = add_foreign_metrics(foreign, ohlc).groupby("symbol").tail(1)
        f = f.rename(columns={"trading_date": "foreign_date"})
        snap = snap.merge(f[["symbol"] + fcols], on="symbol", how="left")
        lastf = foreign.groupby("symbol").tail(1)
        miss_syms = lastf.loc[lastf["remain_room"].isna() | lastf["total_room"].isna() | (lastf["total_room"] <= 0), "symbol"]
        snap["room_missing"] = snap["symbol"].isin(miss_syms)
    else:
        for c in fcols:
            snap[c] = np.nan
        snap["room_missing"] = False
    for c in ("room_anomaly", "room_full"):
        snap[c] = snap[c].eq(True)
    snap["room_anomaly"] = snap["room_anomaly"] & ~snap["room_missing"]   # thiếu dữ liệu không phải bất thường

    snap["at_ceiling"] = False
    snap["at_floor"] = False
    if not limits.empty:
        lim = limits[["symbol", "trading_date", "ceiling", "floor"]].copy()
        lim["date"] = pd.to_datetime(lim["trading_date"], errors="coerce").dt.normalize()
        for c in ("ceiling", "floor"):
            lim[c] = _to_dong(pd.to_numeric(lim[c], errors="coerce"))
        cur = snap[["symbol", "date", "close"]].copy()          # giá phiên mới nhất của từng mã
        cur["date"] = pd.to_datetime(cur["date"], errors="coerce").dt.normalize()
        cur["close"] = _to_dong(pd.to_numeric(cur["close"], errors="coerce"))
        m = cur.merge(lim[["symbol", "date", "ceiling", "floor"]], on=["symbol", "date"], how="inner")  # đúng cùng ngày
        m["at_ceiling"] = m["close"] >= m["ceiling"] - 0.5
        m["at_floor"] = m["close"] <= m["floor"] + 0.5
        snap = snap.drop(columns=["at_ceiling", "at_floor"]).merge(
            m[["symbol", "at_ceiling", "at_floor"]], on="symbol", how="left")
        for c in ("at_ceiling", "at_floor"):
            snap[c] = snap[c].eq(True)
    # Điểm: trung bình có trọng số của xếp hạng phân vị (cao = kém thanh khoản)
    w = pd.Series({"s_amihud": weights["amihud"], "s_dtl": weights["dtl"]})
    comp = snap[list(w.index)]
    den = comp.notna().mul(w).sum(axis=1)
    snap["risk_score"] = (comp.mul(w).sum(axis=1) / den.replace(0, np.nan) * 100).round(1)

    r = snap.groupby("exchange")["risk_score"].rank(pct=True)
    snap["level"] = np.select([r > 2 / 3, r > 1 / 3], ["Cao", "Trung bình"], default="Thấp")
    snap.loc[snap["risk_score"].isna(), "level"] = "Thiếu dữ liệu"
    snap.loc[snap["thin"] & snap["risk_score"].notna(), "level"] = "Cao"
    # Cờ cảnh báo (không vào điểm)
    z = snap.groupby("exchange")["vol_z"].rank(pct=True)
    snap["vol_low"] = z <= alert_pct
    snap["vol_high"] = z >= 1 - alert_pct
    fr = snap["net_5d_ratio"].where(~snap["room_anomaly"]).groupby(snap["exchange"]).rank(pct=True)
    snap["foreign_out"] = fr <= alert_pct
    snap["dtl_alert"] = snap["days_to_liq"] > dtl_alert
    snap["alerts"] = snap.apply(_alerts, axis=1)

    if universe is not None:
        snap = snap[snap["symbol"].isin(universe)]
    return snap.sort_values("risk_score", ascending=False).reset_index(drop=True)


def _alerts(r):
    out = []
    if r["stale"]:
        out.append("Không có dữ liệu ngày mới nhất")
    if r["at_floor"]:
        out.append("Đóng cửa giá sàn")
    if r["at_ceiling"]:
        out.append("Đóng cửa giá trần")
    if r["dtl_alert"]:
        out.append("Số phiên thoát vị thế vượt mốc")
    if r["vol_low"]:
        out.append("Khối lượng thấp so với 60 phiên")
    if r["vol_high"]:
        out.append("Khối lượng cao so với 60 phiên")
    if r["foreign_out"]:
        out.append("Khối ngoại bán ròng mạnh so với thị trường")
    if r["room_anomaly"]:
        out.append("Dữ liệu room bất thường")
    elif r["room_full"]:
        out.append("Room ngoại đã hết")
    if r["thin"]:
        out.append(f"Ít hơn {MIN_TRADED} phiên có giao dịch trong cửa sổ gần nhất")    
    if r["n_sessions"] < MIN_SESSIONS:
        out.append(f"Chưa đủ {MIN_SESSIONS} phiên")
    return "; ".join(out)


def rank_stability(ohlc, foreign, limits, universe=None, exchange_of=None):
    def score(**kw):
        s = build_snapshot(ohlc, foreign, limits, universe=universe, exchange_of=exchange_of, **kw)
        return s.set_index("symbol")["risk_score"]
    base = score()
    configs = {
        "cửa sổ 60 phiên": score(window=60),
        "tỷ lệ tham gia 10%": score(participation=0.10),
        "chỉ Amihud": score(weights={"amihud": 1.0, "dtl": 0.0}),
        "chỉ ADV": score(weights={"amihud": 0.0, "dtl": 1.0}),
    }
    out = {}
    for name, s in configs.items():
        d = pd.concat([base, s], axis=1).dropna()
        out[name] = d.iloc[:, 0].rank().corr(d.iloc[:, 1].rank())
    return pd.Series(out, name="Spearman so với cấu hình gốc")
def build_basket_snapshot(ohlc, foreign, limits, symbols, label, **kw):
    """Xếp hạng chỉ trong nội bộ một rổ (VN30, VN100, HOSE hoặc HNX)."""
    syms = set(symbols)
    return build_snapshot(
        ohlc[ohlc["symbol"].isin(syms)],
        foreign[foreign["symbol"].isin(syms)] if not foreign.empty else foreign,
        limits[limits["symbol"].isin(syms)] if not limits.empty else limits,
        exchange_of={s: label for s in syms}, **kw)