"""Ra-đa thanh khoản HOSE · HNX - giao diện dành cho nhà đầu tư (Streamlit).

Chạy từ thư mục gốc dự án:  streamlit run src/app/streamlit_app.py
Công cụ phân tích học thuật, không phải khuyến nghị đầu tư.
Phần giao diện (màu, nền, phông) chỉ đổi cách hiển thị, không đổi số liệu.
"""
import math
import os
import random
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.analytics.scoring import MIN_SESSIONS, build_snapshot, rank_stability
from src.data import store
from src.data.universe import exchange_map, load_universe
from src.finance import liquidity as liq

st.set_page_config(page_title="Ra-đa thanh khoản HOSE · HNX", page_icon="📡", layout="wide",
                   initial_sidebar_state="expanded")

DB_PATH = ROOT / "data" / "liquidity.db"
CFG = ROOT / "config"
TITLE = "Ra-đa rủi ro thanh khoản cổ phiếu niêm yết trên HOSE và HNX"
UNIVERSES = ["vn30", "vn100", "hose", "hnx"]
UNIVERSE_LABEL = {"vn30": "VN30", "vn100": "VN100", "hose": "Toàn bộ HOSE", "hnx": "Toàn bộ HNX"}
LEVEL_TXT = {"Cao": "Khó mua bán", "Trung bình": "Vừa phải", "Thấp": "Dễ mua bán"}
UP, DOWN, WARN = "#35B79A", "#E8506E", "#F0BD74"
PALETTE = ["#6C7EE1", "#F179B8", "#70C2B4", "#F0BD74", "#956AD6", "#92B9E3", "#FFC4A4", "#C688EB"]
LEVEL_COLOR = {"Khó mua bán": "#F179B8", "Vừa phải": "#F0BD74", "Dễ mua bán": "#70C2B4"}
VN_TZ = timezone(timedelta(hours=7))
SWATCHES = ["#6C7EE1", "#956AD6", "#E85DA8", "#E8A33D", "#4FB3A3", "#5B9BD5", "#B26BE0", "#E9906B"]
SWATCH_ICON = {c: "⬤" for c in SWATCHES}
FONT_STACKS = {"Times New Roman": "'Times New Roman',Times,serif", "Georgia": "Georgia,serif",
               "Arial": "Arial,Helvetica,sans-serif", "Verdana": "Verdana,sans-serif"}
MODES = {
    "Sáng": dict(text="#1B2A41", muted="#5B6B82", base="#FFFFFF", tints=(0.93, 0.985, 0.80), invert="none"),
    "Tối": dict(text="#EEF1F8", muted="#9FAAC0", base="#0B0F19", tints=(0.90, 0.84, 0.70),
                invert="invert(1) hue-rotate(180deg) contrast(1.12)"),
}
PAGES = ["Trang chủ", "Danh sách cổ phiếu", "Bản đồ thanh khoản", "Tra cứu cổ phiếu", "Cảnh báo",
         "Giải thích và giới hạn"]
PAGE_ICONS = {"Trang chủ": "home", "Danh sách cổ phiếu": "format_list_numbered", "Bản đồ thanh khoản": "bubble_chart",
              "Tra cứu cổ phiếu": "search", "Cảnh báo": "notifications_active", "Giải thích và giới hạn": "menu_book"}
PAGE_HINT = {"Trang chủ": "Tóm tắt nhanh và tra nhanh một mã.",
             "Danh sách cổ phiếu": "Mọi mã trong nhóm, có lọc, tìm kiếm, tải về.",
             "Bản đồ thanh khoản": "So sánh các mã bằng hình vẽ.",
             "Tra cứu cổ phiếu": "Thanh khoản, dòng tiền nước ngoài, giá và chỉ báo.",
             "Cảnh báo": "Những mã có dấu hiệu bất thường.",
             "Giải thích và giới hạn": "Cách tính, nguồn, tham số, giới hạn."}

# Tên cột hiển thị -> (giải thích ngắn, định dạng số)
COLS = {
    "Hạng trong nhóm": ("Thứ hạng trong nhóm đang chọn (1 = khó mua bán nhất).", "%d"),
    "Hạng trong sàn": ("Thứ hạng trong sàn của mã (HOSE hoặc HNX), 1 = khó mua bán nhất.", "%d"),
    "Điểm khó mua bán (0-100)": ("Càng cao càng khó mua bán. Là thứ hạng tương đối, không phải xác suất.", "%.1f"),
    "Giá đóng cửa (đồng)": ("Giá đóng cửa phiên mới nhất có dữ liệu.", "%d"),
    "Tiền giao dịch bình quân (tỷ đồng mỗi phiên)": ("Số tiền khớp lệnh trung bình mỗi phiên. Càng lớn càng dễ mua bán.", "%.1f"),
    "Độ trượt giá (trên mỗi tỷ đồng)": ("Giá xê dịch bao nhiêu khi có 1 tỷ đồng giao dịch. Càng cao càng khó mua bán.", "%.5f"),
    "Số phiên để bán hết": ("Khoản cần bán / (phần trăm tham gia x tiền giao dịch bình quân).", "%.2f"),
    "Nước ngoài mua bán ròng 5 phiên (so với giao dịch thường ngày)": ("Âm lớn nghĩa là nước ngoài đang bán ròng mạnh.", "%.3f"),
    "Số phiên nước ngoài bán liên tiếp": ("Số phiên liên tiếp nước ngoài bán nhiều hơn mua.", "%d"),
    "Số phiên có dữ liệu": ("Số phiên giá có trong cơ sở dữ liệu.", "%d"),
}
GLOSSARY = [
    ("Điểm khó mua bán (0-100)", "Cho biết mã này khó mua hay bán hơn bao nhiêu mã khác.",
     "Trung bình có trọng số của hai thứ hạng: độ trượt giá và tiền giao dịch bình quân.",
     "80 nghĩa là khó mua bán hơn khoảng 80% số mã cùng sàn. Không phải xác suất."),
    ("Mức: Dễ mua bán, Vừa phải, Khó mua bán", "Chia đều ba nhóm theo điểm.",
     "Tam phân vị của điểm trong sàn của mã. Mã giao dịch thưa (dưới 10 phiên có giao dịch trong cửa sổ) luôn xếp Khó mua bán.",
     "Nhóm VN30 có thể toàn mã Dễ mua bán vì được so với cả sàn HOSE."),
    ("Độ trượt giá (chỉ số Amihud)", "Giá nhúc nhích bao nhiêu khi có 1 tỷ đồng giao dịch.",
     "Trung bình trong cửa sổ của |lợi suất ngày| chia cho tiền giao dịch (tỷ đồng). Amihud (2002).",
     "Càng cao thì giá càng dễ bị đẩy đi, tức càng khó mua bán."),
    ("Tiền giao dịch bình quân", "Số tiền khớp lệnh bình thường mỗi phiên.",
     "Trung bình trong cửa sổ của giá trị khớp lệnh mỗi phiên.", "Càng lớn càng dễ vào ra."),
    ("Số phiên để bán hết", "Cần bao nhiêu phiên để bán hết khoản của bạn.",
     "Khoản cần bán / (phần trăm tham gia x tiền giao dịch bình quân).",
     "Khoản và phần trăm tham gia do bạn chọn ở thanh bên; chỉ đổi con số này, không đổi thứ hạng."),
    ("Nước ngoài mua bán ròng 5 phiên", "Dòng tiền nước ngoài gần đây so với giao dịch thường ngày.",
     "(Mua - bán của nước ngoài trong 5 phiên) / tiền giao dịch bình quân.",
     "Âm lớn là nước ngoài bán ròng mạnh. Chỉ là cảnh báo, không vào điểm."),
    ("Khối lượng so với thường lệ", "Hôm nay giao dịch nhiều hay ít bất thường.",
     "So khối lượng hôm nay với mức trung bình và độ dao động của chính mã đó.",
     "Cảnh báo khi nằm ở mức rất thấp hoặc rất cao theo phân vị bạn chọn."),
    ("Độ ổn định của thứ hạng", "Đổi cách tính một chút thì thứ hạng có đổi nhiều không.",
     "Hệ số tương quan hạng Spearman giữa hai bảng xếp hạng.", "Gần 1 là thứ hạng gần như không đổi."),
    ("Đường trung bình động", "Giá trung bình n phiên gần nhất, làm mượt giá.",
     "Trung bình giá đóng cửa n phiên.", "Giá nằm trên đường dài thường được coi là xu hướng tăng. Chỉ để tham khảo."),
    ("Sức mạnh giá (RSI)", "Lực tăng so với lực giảm gần đây, từ 0 đến 100.",
     "100 - 100/(1+RS); làm mượt kiểu Wilder, 14 phiên.", "Trên 70 gọi là quá mua, dưới 30 là quá bán (mốc quy ước)."),
    ("Động lượng giá (MACD)", "Đà tăng giảm của giá.",
     "Đường trung bình mũ 12 trừ 26; đường tín hiệu là trung bình mũ 9 của hiệu đó.",
     "Đường MACD cắt lên đường tín hiệu là đà tăng. Chỉ để tham khảo."),
]


# ------------------------------------------------------------------ định dạng, chỉ báo
def vn(x, d: int = 0) -> str:
    """Số kiểu Việt Nam: 22.805; 8,10."""
    if x is None or pd.isna(x):
        return "–"
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")

def money(ty: float) -> str:
    """Số tiền theo tỷ đồng -> chữ dễ đọc: 250 nghìn đồng, 100 triệu đồng, 2,5 tỷ đồng."""
    sign, d = ("-" if ty < 0 else ""), abs(ty) * 1e9

    def short(x: float) -> str:
        t = vn(x, 1)
        return t[:-2] if t.endswith(",0") else t      # 1,0 -> 1 ; 2,5 giữ nguyên
    if d >= 1e9:
        return f"{sign}{short(d / 1e9)} tỷ đồng"
    if d >= 1e6:
        return f"{sign}{short(d / 1e6)} triệu đồng"
    if d >= 1e3:
        return f"{sign}{vn(d / 1e3, 0)} nghìn đồng"
    return f"{sign}{vn(d, 0)} đồng"


def unit_of(series_ty) -> tuple:
    """Chọn đơn vị trục theo độ lớn điển hình: (hệ số nhân so với tỷ, tên đơn vị)."""
    m = pd.Series(series_ty).abs().replace(0, float("nan")).median()
    if pd.isna(m) or m >= 1:
        return 1.0, "tỷ đồng"
    return (1e3, "triệu đồng") if m >= 0.001 else (1e6, "nghìn đồng")


def money_hover(series_ty) -> list:
    return [money(v) if pd.notna(v) else "–" for v in series_ty]
def lv(x) -> str:
    return LEVEL_TXT.get(x, "Chưa đủ dữ liệu")


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def rsi_wilder(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    au = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    ad = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + au / ad)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, sig: int = 9):
    line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    signal = line.ewm(span=sig, adjust=False).mean()
    return line, signal, line - signal


def num(x):
    try:
        return float(str(x).replace(",", "."))
    except (TypeError, ValueError):
        return float("nan")


# ------------------------------------------------------------------ giao diện (màu, nền, kiểu chữ)
def _mix(a: str, b: str, w: float) -> str:
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x * (1 - w) + y * w):02x}" for x, y in zip(ca, cb))


def _rgba(h: str, a: float) -> str:
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{a})"


def bg_svg(animated: bool, strength: float, seed: int = 7):
    """Ô nền lặp được: nến và đường giá tự vẽ (không lấy từ nguồn ngoài). Trả về (svg, rộng, cao)."""
    rnd = random.Random(seed)
    n, step, h = 30, 40, 600
    w = n * step
    p = [300.0]
    for _ in range(n):
        p.append(p[-1] * 0.92 + 300 * 0.08 + rnd.uniform(-38, 38))
    p = [v - (p[-1] - p[0]) * i / n for i, v in enumerate(p)]
    k = min(1.0, 150 / max(abs(v - 300) for v in p))
    p = [300 + (v - 300) * k for v in p]
    a = 0.30 * strength
    parts = [f'<line x1="0" y1="{y}" x2="{w}" y2="{y}" stroke="#92B9E3" stroke-opacity="{0.12 * strength:.2f}"/>'
             for y in range(100, h, 100)]
    for i in range(n):
        o, c, x = p[i], p[i + 1], step / 2 + i * step
        col = UP if c < o else DOWN
        hi, lo = min(o, c) - rnd.uniform(6, 26), max(o, c) + rnd.uniform(6, 26)
        st_ = (f' style="animation-duration:{rnd.uniform(2.5, 6):.1f}s;animation-delay:-{rnd.uniform(0, 6):.1f}s"'
               if animated else "")
        parts.append(f'<g class="k"{st_}><line x1="{x}" y1="{hi:.0f}" x2="{x}" y2="{lo:.0f}" stroke="{col}" '
                     f'stroke-opacity="{a:.2f}"/><rect x="{x - 9}" y="{min(o, c):.0f}" width="18" '
                     f'height="{max(abs(o - c), 3):.0f}" fill="{col}" fill-opacity="{a * 0.55:.2f}" '
                     f'stroke="{col}" stroke-opacity="{a:.2f}"/></g>')
    pts = " ".join(f"{step / 2 + i * step:.0f},{p[i + 1]:.0f}" for i in range(n))
    parts.append(f'<polyline points="{pts}" fill="none" stroke="#956AD6" stroke-opacity="{a:.2f}" stroke-width="2"/>')
    css = ('<style>.k{transform-box:fill-box;transform-origin:center bottom;animation:br 4s ease-in-out infinite alternate}'
           '@keyframes br{from{transform:scaleY(.8)}to{transform:scaleY(1.2)}}</style>') if animated else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'{css}{"".join(parts)}</svg>', w, h)


def theme_css(mode: str, accent: str, font: str, bg_mode: str, speed: str, strength: str) -> str:
    m = MODES[mode]
    dark = mode == "Tối"
    bg, surface, border = (_mix(accent, m["base"], w) for w in m["tints"])
    text, muted = m["text"], m["muted"]
    accent2 = _mix(accent, "#ff7ac8", 0.35)
    soft, glass = _rgba(surface, 0.62 if dark else 0.80), _rgba(surface, 0.94)
    svg, w, h = bg_svg(bg_mode == "Động", {"Nhạt": 0.6, "Vừa": 1.0, "Đậm": 1.6}[strength])
    bw, bh = int(w * 1.3), int(h * 1.3)
    secs = {"Chậm": 160, "Vừa": 90, "Nhanh": 45}[speed]
    layer = ""
    if bg_mode != "Tắt":
        anim = f"animation:mkt-drift {secs}s linear infinite;" if bg_mode == "Động" else ""
        layer = (f'.mkt-bg{{position:fixed;inset:0;z-index:-1;pointer-events:none;background-repeat:repeat-x;'
                 f'background-position:0 55%;background-size:{bw}px {bh}px;'
                 f'background-image:url("data:image/svg+xml;utf8,{quote(svg)}");{anim}}}'
                 f'@keyframes mkt-drift{{from{{background-position:0 55%}}to{{background-position:-{bw}px 55%}}}}'
                 f'@media (prefers-reduced-motion:reduce){{.mkt-bg{{animation:none}}}}')
    swatch_css = "".join(f'.st-key-swatch label:nth-of-type({i}) p{{color:{c}!important}}' for i, c in enumerate(SWATCHES, 1))
    css = """
.stApp{background:radial-gradient(900px 520px at 4% -8%,__G1__,transparent 70%),__BG__;background-attachment:fixed;color:__TEXT__}
[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stHeader"]{background:transparent}
[data-testid="stMain"] .block-container{position:relative;z-index:1;padding-top:1.2rem!important;max-width:1280px}
html,body,[data-testid="stAppViewContainer"],[data-testid="stSidebar"],button,input,select,textarea,
.stApp p,.stApp label,.stApp li,.stApp h1,.stApp h2,.stApp h3,.stApp h4,.stApp td,.stApp th,
.stApp [data-testid="stMetricValue"],.stApp [data-testid="stMarkdownContainer"] span{font-family:__FONT__!important}
.stApp [data-testid="stMarkdownContainer"] span[role="img"],[data-testid="stIconMaterial"]{font-family:"Material Symbols Rounded"!important}
.stApp h2,.stApp h3,.stApp h4,.stApp label,.stApp p,.stApp li,.stApp [data-testid="stAlert"] *{color:__TEXT__}
.stApp h3{font-weight:700;margin:1.2rem 0 .3rem;padding:0 0 4px!important;border-bottom:2px solid __ACCENT__;display:inline-block}
.stApp h4{font-size:1.05rem;font-weight:700;margin:.8rem 0 .2rem}
.stApp [data-testid="stCaptionContainer"]{color:__MUTED__}
[data-testid="stSidebar"]{background:__SIDE__;backdrop-filter:blur(16px);border-right:1px solid __BORDER__}
.sb-brand{font-weight:800;font-size:1.1rem;margin:0 0 12px;color:__TEXT__}
.sb-brand small{display:block;font-weight:500;font-size:.74rem;color:__MUTED__}
.st-key-navbox [role="radiogroup"]{gap:3px;width:100%}
.st-key-navbox [role="radiogroup"] label{width:100%;padding:9px 12px;border-radius:10px;margin:0}
.st-key-navbox [role="radiogroup"] label:hover{background:__HOVER__}
.st-key-navbox [role="radiogroup"] label:has(input:checked){background:__ACCENT__}
.st-key-navbox [role="radiogroup"] label:has(input:checked) *{color:#fff!important;font-weight:600}
__SWATCH__
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{background:__SURFACE__!important;border-radius:10px}
[data-baseweb="input"] input,[data-baseweb="select"] *{color:__TEXT__!important}
[data-baseweb="popover"] [role="listbox"],[data-baseweb="popover"] li{background:__SURFACE__!important;color:__TEXT__!important}
[data-testid="stExpander"] summary,[data-testid="stExpander"] summary *{background:transparent!important;color:__TEXT__!important}
[data-testid="stExpander"] details{background:__GLASS__;border:1px solid __BORDER__!important;border-radius:14px}
[data-testid="stDataFrame"]{filter:__INVERT__;border:1px solid __BORDER__;border-radius:12px}
[data-testid="stPlotlyChart"]{background:__GLASS__;border:1px solid __BORDER__;border-radius:14px;padding:6px}
.stDownloadButton button,.stButton button,.stLinkButton a{background:__ACCENT__;border:0;border-radius:8px}
.stDownloadButton button p,.stButton button p,.stLinkButton a p{color:#fff!important}
.mast{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between;padding:0 0 10px;margin-bottom:14px;border-bottom:1px solid __BORDER__}
.mast .name{font-weight:800;letter-spacing:.02em;color:__TEXT__}
.chip{display:inline-block;padding:3px 11px;border-radius:99px;border:1px solid __BORDER__;background:__SOFT__;font-size:.8rem;color:__MUTED__;margin-left:6px}
.hero{padding:6px 0 14px}
.hero .kick{font-size:.78rem;letter-spacing:.14em;text-transform:uppercase;color:__ACCENT__;font-weight:700}
.hero h1{font-size:clamp(1.7rem,3.4vw,2.7rem);font-weight:800;line-height:1.18;margin:6px 0 8px;padding:0!important;color:__TEXT__}
.hero .sub{color:__MUTED__;line-height:1.6;max-width:72ch;font-size:1.05rem}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:14px;margin:8px 0 14px}
.stat{background:__SOFT__;border:1px solid __BORDER__;border-top:4px solid __ACCENT__;border-radius:12px;padding:14px 18px}
.stat .k{font-size:.92rem;color:__MUTED__}
.stat .v{font-size:2.2rem;font-weight:800;line-height:1.1;margin:4px 0;color:__TEXT__;font-variant-numeric:tabular-nums}
.stat .v.bad{color:__BAD__}
.stat .n{font-size:.9rem;line-height:1.45;color:__TEXT__}
.say{background:__SOFT__;border:1px solid __BORDER__;border-left:5px solid __ACCENT__;border-radius:10px;padding:12px 16px;margin:8px 0 14px;line-height:1.6;color:__TEXT__}
.say b.t{display:block;margin-bottom:4px}
.say ul{margin:4px 0 0 1.1rem;padding:0}
.meter{margin:10px 0 4px;max-width:560px}
.meter .bar{position:relative;height:12px;border-radius:99px;background:linear-gradient(90deg,#70C2B4,#F0BD74,#F179B8)}
.meter .bar i{position:absolute;top:-5px;width:5px;height:22px;border-radius:3px;background:__TEXT__;transform:translateX(-2px);box-shadow:0 0 0 2px __SURFACE__}
.meter .ends{display:flex;justify-content:space-between;font-size:.8rem;color:__MUTED__;margin-top:6px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin:6px 0 12px}
.tile{background:__SOFT__;border:1px solid __BORDER__;border-radius:10px;padding:10px 14px}
.tile .k{font-size:.82rem;color:__MUTED__}.tile .v{font-size:1.25rem;font-weight:700;color:__TEXT__}
:root{--tb:__TB__;--tg:__TG__;--ts:__TS__;--tt:__TT__;--ta:__TA__}
.gloss{width:100%;border-collapse:collapse;font-size:.92rem}
.gloss th{text-align:left;color:__MUTED__;font-size:.8rem;padding:8px;border-bottom:1px solid __BORDER__}
.gloss td{padding:9px 8px;vertical-align:top;border-top:1px solid __BORDER__;color:__TEXT__;line-height:1.5}
.gloss td:first-child{font-weight:700}
__LAYER__
"""
    rep = {"__FONT__": FONT_STACKS[font], "__BG__": bg, "__SURFACE__": surface, "__TEXT__": text, "__MUTED__": muted,
           "__BORDER__": _rgba(border, .9), "__INVERT__": m["invert"], "__ACCENT__": accent, "__GLASS__": glass,
           "__SOFT__": soft, "__SIDE__": _rgba(surface, .66 if dark else .80), "__HOVER__": _rgba(accent, .14),
            "__G1__": _rgba(accent2, .30 if dark else .14), "__BAD__": DOWN, "__SWATCH__": swatch_css, "__LAYER__": layer,
           "__TB__": _rgba(border, .9), "__TG__": _rgba(surface, .94), "__TS__": surface, "__TT__": text, "__TA__": accent}
    for k, v in rep.items():
        css = css.replace(k, v)
    return f"<style>{css}</style>"


def masthead() -> None:
    st.markdown(f"<div class='mast'><span class='name'>📡 {escape(TITLE)}</span><span>"
                f"<span class='chip'>Dữ liệu giá đến {last_date:%d/%m/%Y}</span>"
                f"<span class='chip'>Cập nhật {updated}</span>"
                f"<span class='chip'>Dữ liệu cuối ngày, không phải thời gian thực</span></span></div>",
                unsafe_allow_html=True)


def hero(kick: str, title: str, sub: str = "") -> None:
    st.markdown(f"<div class='hero'><div class='kick'>{escape(kick)}</div><h1>{escape(title)}</h1>"
                + (f"<div class='sub'>{escape(sub)}</div>" if sub else "") + "</div>", unsafe_allow_html=True)


def stats(items: list) -> None:
    out = "".join(f"<div class='stat'><div class='k'>{escape(c['k'])}</div>"
                  f"<div class='v{' bad' if c.get('bad') else ''}'>{escape(c['v'])}</div>"
                  f"<div class='n'>{escape(c['n'])}</div></div>" for c in items)
    st.markdown(f"<div class='stats'>{out}</div>", unsafe_allow_html=True)


def say(title: str, lines: list, take: str = "") -> None:
    li = "".join(f"<li>{s}</li>" for s in lines)
    tk = f"<div style='margin-top:8px'>{take}</div>" if take else ""
    st.markdown(f"<div class='say'><b class='t'>{escape(title)}</b><ul>{li}</ul>{tk}</div>", unsafe_allow_html=True)


def tiles(items: list) -> None:
    out = "".join(f"<div class='tile'><div class='k'>{escape(k)}</div><div class='v'>{escape(v)}</div></div>"
                  for k, v in items)
    st.markdown(f"<div class='tiles'>{out}</div>", unsafe_allow_html=True)


def meter(score) -> None:
    pos = 50 if score is None or pd.isna(score) else max(0, min(100, float(score)))
    st.markdown(f"<div class='meter'><div class='bar'><i style='left:{pos}%'></i></div>"
                "<div class='ends'><span>Dễ mua bán</span><span>Khó mua bán</span></div></div>", unsafe_allow_html=True)


def stretch(fn, *args, **kwargs):
    try:
        return fn(*args, width="stretch", **kwargs)
    except TypeError:
        return fn(*args, use_container_width=True, **kwargs)


# ------------------------------------------------------------------ biểu đồ (thu phóng, kéo, vẽ, xóa hình vẽ)
CONFIG = dict(scrollZoom=True, displaylogo=False, displayModeBar=True, doubleClick="reset+autosize",
              modeBarButtonsToAdd=["drawline", "drawopenpath", "drawrect", "drawcircle", "eraseshape"],
              toImageButtonOptions=dict(format="png", scale=2, filename="ra_da_thanh_khoan"))
RANGESEL = dict(buttons=[dict(count=1, label="1 tháng", step="month", stepmode="backward"),
                         dict(count=3, label="3 tháng", step="month", stepmode="backward"),
                         dict(count=6, label="6 tháng", step="month", stepmode="backward"),
                         dict(count=1, label="1 năm", step="year", stepmode="backward"),
                         dict(step="all", label="Tất cả")], bgcolor="rgba(149,106,214,.16)")


def pro(fig: go.Figure, dark: bool, title: str, height: int = 520, dragmode: str = "zoom",
        hover: str = "closest") -> go.Figure:
    tx = "#EEF1F8" if dark else "#1B2A41"
    grid = "rgba(255,255,255,.14)" if dark else "rgba(27,42,65,.10)"
    fig.update_layout(title=dict(text=title, font=dict(color=tx)), template="plotly_dark" if dark else "plotly_white",
                      height=height, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", dragmode=dragmode,
                      hovermode=hover, font=dict(family="Times New Roman, Times, serif", size=14, color=tx),
                      margin=dict(l=50, r=24, t=70, b=40),
                      legend=dict(orientation="h", y=1.04, x=0, font=dict(color=tx)), newselection_mode="gradual",
                      hoverlabel=dict(namelength=-1, bgcolor="#1E2438" if dark else "#FFFFFF", font=dict(color=tx)))
    fig.update_xaxes(showspikes=True, spikemode="across", spikethickness=1, spikedash="dot",
                     gridcolor=grid, linecolor=grid, zerolinecolor=grid, tickfont=dict(color=tx), title_font=dict(color=tx))
    fig.update_yaxes(showspikes=True, spikethickness=1, spikedash="dot",
                     gridcolor=grid, linecolor=grid, zerolinecolor=grid, tickfont=dict(color=tx), title_font=dict(color=tx))
    for ax in fig.select_xaxes():
        if ax.rangeselector and ax.rangeselector.buttons:
            ax.rangeselector.font.color = tx
    return fig


def _clear_drawings() -> None:
    st.session_state["clear_n"] = st.session_state.get("clear_n", 0) + 1


def show(fig: go.Figure, key: str) -> None:
    """Khóa biểu đồ đổi mỗi lần bấm 'Xóa mọi hình đã vẽ' nên hình vẽ tay biến mất (trục về mặc định)."""
    stretch(st.plotly_chart, fig, config=CONFIG, theme=None, key=f"{key}_{st.session_state.get('clear_n', 0)}")


def chart_tools(k: str) -> str:
    c1, c2 = st.columns([3, 1])
    with c1:
        d = st.radio("Kéo chuột để", ["Phóng to vùng chọn", "Di chuyển biểu đồ"], horizontal=True, key=f"drag_{k}",
                     help="Cuộn chuột để phóng to hoặc thu nhỏ; nhấp đúp để về mặc định. Thanh công cụ ở góc trên bên phải "
                          "có vẽ đường, vẽ khung, vẽ hình tròn, cục tẩy xóa từng hình và tải ảnh.")
    with c2:
        st.button("Xóa mọi hình đã vẽ", key=f"clr_{k}", on_click=_clear_drawings,
                  help="Xóa hết đường và khung bạn đã vẽ trên các biểu đồ (biểu đồ cũng về lại mặc định).")
    return "zoom" if d.startswith("Phóng") else "pan"

# nhãn ngày tháng tiếng Việt trên trục thời gian (Plotly mặc định ghi tiếng Anh như "Jun 2025")
VN_DATE = dict(tickformatstops=[
    dict(dtickrange=[None, 172800000], value="%d/%m/%Y"),
    dict(dtickrange=[172800000, "M1"], value="%d/%m"),
    dict(dtickrange=["M1", "M12"], value="Th%m/%Y"),
    dict(dtickrange=["M12", None], value="%Y")], hoverformat="%d/%m/%Y")
def rangebreaks(idx: pd.DatetimeIndex) -> list:
    rb = [dict(bounds=["sat", "mon"])]
    miss = pd.bdate_range(idx.min(), idx.max()).difference(idx)
    if len(miss):
        rb.append(dict(values=[d.strftime("%Y-%m-%d") for d in miss]))
    return rb


# ------------------------------------------------------------------ dữ liệu
@st.cache_data(show_spinner="Đang tính điểm...")
def compute_full(db_key, position_ty, participation, window, alert_pct, dtl_alert, w_amihud):
    conn = store.connect(DB_PATH)
    try:
        o, f, l = store.load_ohlc(conn), store.load_foreign(conn), store.load_limits(conn)
    finally:
        if conn is not None:
            conn.close()
    if o.empty:
        raise ValueError("Bảng giá đang rỗng. Hãy chạy: python -m src.data.ingest")
    snap = build_snapshot(o, f, l, universe=None, position_value=position_ty * 1e9, participation=participation,
                          weights={"amihud": w_amihud, "dtl": 1 - w_amihud}, window=window,
                          alert_pct=alert_pct, dtl_alert=dtl_alert, exchange_of=exchange_map())
    snap["rank_all"] = (snap.groupby("exchange")["risk_score"]
                        .rank(ascending=False, method="min").astype("Int64"))
    return snap


@st.cache_data(show_spinner=False)
def normalize_history(o: pd.DataFrame) -> pd.DataFrame:
    """Đưa bảng giá về dạng có cột 'date' kiểu ngày, dù ngày đang là cột hay là chỉ mục, tên gì cũng được."""
    o = o.copy()
    if "date" not in o.columns:
        o = o.reset_index()
    if "date" not in o.columns:
        cand = next((c for c in ("trading_date", "tradingDate", "TradingDate", "Date", "time", "index") if c in o.columns), None)
        if cand is None:
            raise ValueError(f"Không tìm thấy cột ngày trong bảng giá. Các cột hiện có: {list(o.columns)}")
        o = o.rename(columns={cand: "date"})
    o["date"] = pd.to_datetime(o["date"])
    return o


@st.cache_data(show_spinner=False)
def load_history(db_key):
    conn = store.connect(DB_PATH)
    try:
        o = store.load_ohlc(conn)
    finally:
        if conn is not None:
            conn.close()
    return normalize_history(o)

@st.cache_data(show_spinner="Đang kiểm tra độ ổn định (vài chục giây)...")
def compute_sensitivity(db_key, universe_name):
    conn = store.connect(DB_PATH)
    try:
        o, f, l = store.load_ohlc(conn), store.load_foreign(conn), store.load_limits(conn)
    finally:
        if conn is not None:
            conn.close()
    return rank_stability(o, f, l, universe=load_universe(universe_name), exchange_of=exchange_map())


@st.cache_data(show_spinner=False)
def _csv(name: str, mtime: float) -> pd.DataFrame:
    p = CFG / name
    return pd.read_csv(p, dtype=str, encoding="utf-8-sig").fillna("") if p.exists() else pd.DataFrame()


def csv_opt(name: str) -> pd.DataFrame:
    p = CFG / name
    return _csv(name, p.stat().st_mtime if p.exists() else 0.0)

def _query(sql: str, params: tuple) -> pd.DataFrame:
    try:
        conn = sqlite3.connect(DB_PATH)
        try:
            return pd.read_sql_query(sql, conn, params=params)
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_actions(db_key, sym):
    return _query("select exright_date, record_date, issue_date, event_title, ratio from corporate_actions "
                  "where symbol=? order by exright_date desc", (sym,))


@st.cache_data(show_spinner=False)
def load_limit_rows(db_key, sym):
    d = _query("select trading_date, ceiling, floor, ref_price from price_limits where symbol=? "
               "order by trading_date", (sym,))
    if not d.empty:
        d["d"] = pd.to_datetime(d["trading_date"], errors="coerce").dt.normalize()
    return d


@st.cache_data(show_spinner=False)
def load_foreign_hist(db_key, sym):
    d = _query("select trading_date, buy_vol, sell_vol, buy_val, sell_val, remain_room, total_room from foreign_flow "
               "where symbol=? order by trading_date", (sym,))
    if d.empty:
        return d
    d["trading_date"] = pd.to_datetime(d["trading_date"])
    for c in d.columns[1:]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    return d.set_index("trading_date")
# ------------------------------------------------------------------ tự cập nhật giá khi mở web
VN_TZ = timezone(timedelta(hours=7))


def expected_last_session(now: datetime):
    """Phiên gần nhất đáng lẽ đã có giá cuối ngày (sau 15:30 giờ Việt Nam, bỏ thứ bảy và chủ nhật)."""
    d = now.date()
    if now.weekday() >= 5 or now.hour * 60 + now.minute < 15 * 60 + 30:
        d -= timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def latest_price_date():
    d = _query("select max(trading_date) as m from daily_ohlc", ())
    if d.empty or pd.isna(d["m"].iloc[0]):
        return None
    return pd.to_datetime(d["m"].iloc[0]).date()


@st.cache_resource(show_spinner=False)
def _update_log() -> dict:
    return {"last": None, "msg": ""}


def run_update(force: bool = False) -> str:
    """Nếu giá trong máy cũ hơn phiên gần nhất thì chạy bước nạp (một lần, chỉ gọi API dữ liệu). Trả về thông báo lỗi nếu có."""
    log = _update_log()
    now = datetime.now(VN_TZ)
    last = latest_price_date()
    if not force:
        if last is not None and last >= expected_last_session(now):
            return ""
        if log["last"] and (now - log["last"]).total_seconds() < 1800:     # vừa thử xong, đừng thử lại liền
            return log["msg"]
    log["last"] = now
    try:
        with st.spinner("Đang cập nhật giá mới nhất, vui lòng chờ vài phút..."):
            for u in ("hose", "hnx"):
                r = subprocess.run([sys.executable, "-m", "src.data.ingest", "--universe", u], cwd=ROOT,
                                   capture_output=True, text=True, timeout=1800)
                if r.returncode != 0:
                    break
        tail = (r.stderr.strip().splitlines() or ["lỗi không rõ"])[-1]
        log["msg"] = "" if r.returncode == 0 else f"Không cập nhật được giá mới: {tail}"
    except Exception as e:  # noqa: BLE001
        log["msg"] = f"Không cập nhật được giá mới: {e}"
    st.cache_data.clear()
    return log["msg"]

def members_of(name: str) -> list:
    try:
        return load_universe(name)
    except FileNotFoundError:
        return []
# ------------------------------------------------------------------ cảnh báo: loại, màu, chữ
ALERT_TYPES = [
    # (cột cờ, tên ngắn, biểu tượng, màu, ý nghĩa)
    ("foreign_out", "Nước ngoài bán ròng nổi bật", "🌐", "#1F7D6F",
     "Nước ngoài đang bán ròng nhiều so với giao dịch thường ngày của mã."),
    ("dtl_alert", "Bán hết rất lâu", "🐢", "#D3BFF0",
     "Khoản của bạn cần nhiều phiên hơn mức bạn đặt ở thanh bên mới bán hết."),
    ("vol_low", "Giao dịch cạn", "💤", "#6C7EE1", "Khối lượng hôm nay thấp bất thường so với thường lệ của mã."),
    ("vol_high", "Giao dịch đột biến", "🔥", "#F0BD74", "Khối lượng hôm nay cao bất thường so với thường lệ của mã."),
    ("at_ceiling", "Giá chạm trần", "🚀", "#C688EB", "Giá đang ở mức trần trong ngày."),
    ("at_floor", "Giá chạm sàn", "🔻", "#92B9E3", "Giá đang ở mức sàn trong ngày."),
    ("room_full", "Hết room nước ngoài", "⛔", "#70C2B4", "Nước ngoài đã nắm tối đa, không mua thêm được."),
    ("room_anomaly", "Số liệu room lạ", "❓", "#FFC4A4", "Số liệu hạn mức nước ngoài từ SSI không hợp lệ, cần kiểm tra thêm."),
]
LEVEL_TEXT_COLOR = {"Khó mua bán": "#C2185B", "Vừa phải": "#B7791F", "Dễ mua bán": "#0B7A4B"}   # chữ trong bảng
LEVEL_PILL = {"Cao": "#C2185B", "Trung bình": "#B7791F", "Thấp": "#0B7A4B"}                      # nhãn trong thẻ
ALERT_CSS = """<style>
.atiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:14px;margin:8px 0 18px}
.atile{background:linear-gradient(145deg,color-mix(in srgb,var(--c) 52%,#1d1733),color-mix(in srgb,var(--c) 30%,#1d1733));
  color:#fff;border-radius:18px;padding:14px 16px;box-shadow:0 10px 24px color-mix(in srgb,var(--c) 38%,transparent);
  text-shadow:0 1px 2px rgba(0,0,0,.28)}
.atile.off{opacity:.6;box-shadow:none}
.atile .ai{font-size:1.5rem}
.atile .an{font-size:2.4rem;font-weight:800;line-height:1.05;font-variant-numeric:tabular-nums}
.atile .at{font-weight:800;margin-top:2px}
.atile .aw{font-size:.84rem;line-height:1.4;margin-top:4px;color:rgba(255,255,255,.9)}
.acards{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:16px;margin:8px 0 18px}
.acard{border-radius:18px;padding:14px 18px;border:1px solid color-mix(in srgb,var(--c) 55%,transparent);border-left:8px solid var(--c);
  background:linear-gradient(160deg,color-mix(in srgb,var(--c) 22%,transparent),color-mix(in srgb,var(--c) 6%,transparent))}
.acard .ah{display:flex;justify-content:space-between;align-items:center;gap:8px}
.acard .sym{font-size:1.5rem;font-weight:800}
.acard .lvl{font-size:.82rem;font-weight:700;padding:3px 12px;border-radius:99px;color:#fff}
.acard .bar{position:relative;height:9px;border-radius:99px;margin:14px 0 10px;background:linear-gradient(90deg,#70C2B4,#F0BD74,#F179B8)}
.acard .bar i{position:absolute;top:-4px;width:5px;height:17px;border-radius:3px;background:currentColor;transform:translateX(-2px)}
.acard .chips span{display:inline-block;margin:2px 5px 2px 0;padding:3px 11px;border-radius:99px;font-size:.78rem;font-weight:700;color:#2b2342}
.acard .facts{font-size:.88rem;margin-top:8px;line-height:1.6}
</style>"""


def flag(x) -> bool:
    return bool(pd.notna(x) and x)


def alert_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Bảng đúng/sai: mỗi mã có kích hoạt từng loại cảnh báo hay không (đọc thẳng các cột cờ của bảng điểm)."""
    out = pd.DataFrame(index=df.index)
    for c, *_ in ALERT_TYPES:
        out[c] = df[c].astype("boolean").fillna(False).astype(bool) if c in df.columns else False
    return out


def alert_text(flags_row) -> str:
    return " · ".join(f"{icon} {name}" for c, name, icon, _, _ in ALERT_TYPES if flags_row.get(c, False))


def style_level(df: pd.DataFrame, col: str = "Mức"):
    """Tô màu chữ cột Mức: Dễ mua bán xanh lá đậm, Vừa phải vàng nâu, Khó mua bán hồng đậm."""
    def paint(v):
        c = LEVEL_TEXT_COLOR.get(v)
        return f"color:{c};font-weight:700" if c else ""
    sty = df.style
    return (sty.map if hasattr(sty, "map") else sty.applymap)(paint, subset=[col])


def alert_cards_html(al: pd.DataFrame, fl: pd.DataFrame, limit: int = 12) -> str:
    cards_ = []
    for idx, r in al.head(limit).iterrows():
        on = [t for t in ALERT_TYPES if fl.at[idx, t[0]]]
        col = on[0][3] if on else "#956AD6"
        chips = "".join(f"<span style='background:{t[3]}'>{t[2]} {escape(t[1])}</span>" for t in on)
        facts = []
        d = r["days_to_liq"]
        if pd.notna(d):
            facts.append(f"Khoản {money(position_ty)} bán hết được trong <b>1 phiên</b>." if d <= 1
                         else f"Cần khoảng <b>{math.ceil(d)} phiên</b> để bán hết khoản {money(position_ty)}.")
        if pd.notna(r.get("sell_streak")) and r["sell_streak"] >= 1:
            facts.append(f"Nước ngoài bán ròng <b>{int(r['sell_streak'])} phiên</b> liên tiếp.")
        if pd.notna(r.get("net_5d_ratio")) and fl.at[idx, "foreign_out"]:
            facts.append(f"5 phiên gần nhất, nước ngoài mua trừ bán bằng <b>{vn(r['net_5d_ratio'], 2)} lần</b> "
                         "tiền giao dịch bình quân một phiên.")
        if pd.notna(r.get("room_used_pct")) and not fl.at[idx, "room_anomaly"]:
            facts.append(f"Nước ngoài đã nắm khoảng <b>{vn(r['room_used_pct'] * 100, 0)}%</b> hạn mức được phép.")
        if (fl.at[idx, "vol_low"] or fl.at[idx, "vol_high"]) and pd.notna(r.get("vol_z")):
            facts.append(f"Chỉ số khối lượng so với thường lệ: <b>{vn(r['vol_z'], 1)}</b> (0 là bình thường).")
        pos = 50 if pd.isna(r["risk_score"]) else max(0, min(100, float(r["risk_score"])))
        pill = LEVEL_PILL.get(r["level"], "#956AD6")
        cards_.append(
            f"<div class='acard' style='--c:{col}'><div class='ah'><span class='sym'>{escape(str(r['symbol']))}</span>"
            f"<span class='lvl' style='background:{pill}'>{escape(lv(r['level']))} · {vn(r['risk_score'], 0)}/100</span></div>"
            f"<div class='bar'><i style='left:{pos}%'></i></div><div class='chips'>{chips}</div>"
            f"<div class='facts'>{'<br>'.join(facts)}</div></div>")
    return f"<div class='acards'>{''.join(cards_)}</div>"


def to_display(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "Hạng trong nhóm": df["rank_in_universe"], "Hạng trong sàn": df["rank_all"], "Mã": df["symbol"],
        "Điểm khó mua bán (0-100)": df["risk_score"], "Mức": df["level"].map(lv),
        "Giá đóng cửa (đồng)": df["close"], "Ngày dữ liệu giá": df["date"].dt.strftime("%Y-%m-%d"),
        "Tiền giao dịch bình quân (tỷ đồng mỗi phiên)": df["adv"] / 1e9,
        "Độ trượt giá (trên mỗi tỷ đồng)": df["amihud"], "Số phiên để bán hết": df["days_to_liq"],
        "Nước ngoài mua bán ròng 5 phiên (so với giao dịch thường ngày)": df["net_5d_ratio"],
        "Số phiên nước ngoài bán liên tiếp": df["sell_streak"],
        "Số phiên có dữ liệu": df["n_sessions"],
        "Cảnh báo": [alert_text(r) for _, r in alert_flags(df).iterrows()]})


def column_config() -> dict:
    cfg = {c: st.column_config.NumberColumn(c, format=f, help=h) for c, (h, f) in COLS.items()}
    for c in ("Mã", "Mức", "Cảnh báo"):
        cfg[c] = st.column_config.TextColumn(c)
    cfg["Điểm khó mua bán (0-100)"] = st.column_config.ProgressColumn(
        "Điểm khó mua bán (0-100)", help=COLS["Điểm khó mua bán (0-100)"][0], format="%.1f", min_value=0, max_value=100)
    return cfg

PILL = {"Dễ mua bán": ("#70C2B4", "#0B3B33"), "Vừa phải": ("#F0BD74", "#4A3000"), "Khó mua bán": ("#F179B8", "#4A0D2C")}
TABLE_CSS = """<style>
.tbl-wrap{max-height:560px;overflow:auto;border:1px solid var(--tb);border-radius:12px;background:var(--tg)}
.tbl{border-collapse:collapse;width:100%;font-size:.9rem}
.tbl th{position:sticky;top:0;z-index:1;background:var(--ts);color:var(--tt);text-align:left;padding:10px 12px;
  border-bottom:2px solid var(--ta);font-size:.8rem;white-space:nowrap;vertical-align:middle}
.tbl td.wrap{white-space:normal;min-width:240px;line-height:1.4}
.tbl td{padding:8px 12px;border-top:1px solid var(--tb);color:var(--tt);white-space:nowrap}
.tbl tr:nth-child(even) td{background:rgba(127,127,127,.08)}
.tbl td.num{text-align:right;font-variant-numeric:tabular-nums}
.tbl td.sym{font-weight:800;font-size:1rem}
.tbl tr.hot td:first-child{box-shadow:inset 4px 0 0 #F179B8}
.tbl .pill{display:inline-block;padding:2px 11px;border-radius:99px;font-weight:700;font-size:.8rem}
.tbl .sbar{position:relative;min-width:120px;height:20px;border-radius:99px;background:rgba(127,127,127,.20);overflow:hidden}
.tbl .sbar i{position:absolute;left:0;top:0;bottom:0;border-radius:99px}
.tbl .sbar b{position:relative;display:block;text-align:center;line-height:20px;font-size:.78rem;color:#1B1B2B}
</style>"""


def score_color(v: float) -> str:
    t = max(0.0, min(100.0, float(v))) / 100
    return _mix("#70C2B4", "#F0BD74", t / 0.5) if t < 0.5 else _mix("#F0BD74", "#F179B8", (t - 0.5) / 0.5)

SHORT_HEAD = {
    "Hạng trong nhóm": "Hạng nhóm", "Điểm khó mua bán (0-100)": "Điểm khó mua bán", "Giá đóng cửa (đồng)": "Giá đóng cửa",
    "Ngày dữ liệu giá": "Ngày giá", "Tiền giao dịch bình quân (tỷ đồng mỗi phiên)": "Giao dịch mỗi phiên",
    "Độ trượt giá (trên mỗi tỷ đồng)": "Độ trượt giá", "Số phiên để bán hết": "Phiên bán hết",
    "Nước ngoài mua bán ròng 5 phiên (so với giao dịch thường ngày)": "Nước ngoài ròng 5 phiên",
    "Số phiên nước ngoài bán liên tiếp": "Nước ngoài bán liên tiếp", "Số phiên có dữ liệu": "Số phiên dữ liệu",
    "Ngày giao dịch không hưởng quyền": "Ngày không hưởng quyền", "Tỷ lệ (nguyên văn từ SSI)": "Tỷ lệ (nguyên văn)"}
ADV_COL = "Tiền giao dịch bình quân (tỷ đồng mỗi phiên)"
def digits_of(f: str) -> int:
    return int(f.split(".")[1][0]) if "." in f else 0


def html_table(df: pd.DataFrame, bar_col: str = "", strong: tuple = ("Mã",), alert_col: str = "Cảnh báo") -> None:
    """Bảng tự vẽ: nền và chữ theo chế độ sáng hoặc tối, nhãn mức có màu, mã có cảnh báo in đậm."""
    fmt = {c: digits_of(f) for c, (_, f) in COLS.items()}
    head = "".join(f"<th title='{escape(str(c))}. {escape(COLS.get(c, ('', ''))[0])}'>{escape(SHORT_HEAD.get(c, str(c)))}</th>"
                   for c in df.columns)
    body = []
    for _, r in df.iterrows():
        hot = alert_col in df.columns and str(r[alert_col]).strip() not in ("", "nan")
        tds = []
        for c in df.columns:
            v = r[c]
            if c == "Mức" and v in PILL:
                bg, fg = PILL[v]
                tds.append(f"<td><span class='pill' style='background:{bg};color:{fg}'>{escape(v)}</span></td>")
            elif c == bar_col and pd.notna(v):
                tds.append(f"<td><div class='sbar'><i style='width:{max(0, min(100, float(v)))}%;background:{score_color(v)}'>"
                           f"</i><b>{vn(v, 1)}</b></div></td>")
            elif pd.isna(v):
                tds.append("<td class='num'>–</td>")
            elif c == ADV_COL:
                tds.append(f"<td class='num'>{money(float(v))}</td>")
            elif isinstance(v, (int, float)) or hasattr(v, "dtype") and getattr(v, "dtype").kind in "iuf":
                d_ = fmt.get(c, 0)
                x_ = float(v)
                tds.append(f"<td class='num'>{vn(0.0 if round(x_, d_) == 0 else x_, d_)}</td>")
            else:
                cls = ("sym " if c in strong else "") + ("wrap" if c in (alert_col, "Nội dung sự kiện") else "")
                tds.append(f"<td class='{cls.strip()}'>{escape(str(v))}</td>")
        body.append(f"<tr class='{'hot' if hot else ''}'>{''.join(tds)}</tr>")
    st.markdown(TABLE_CSS, unsafe_allow_html=True)
    st.markdown(f"<div class='tbl-wrap'><table class='tbl'><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>",
                unsafe_allow_html=True)
def csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8-sig")


_upd_msg = run_update() if os.getenv("AUTO_UPDATE", "1") != "0" else ""

# ------------------------------------------------------------------ thanh bên
st.sidebar.markdown("<div class='sb-brand'>📡 Ra-đa thanh khoản<small>HOSE · HNX · VN100 · VN30</small></div>",
                    unsafe_allow_html=True)
with st.sidebar.container(key="navbox"):
    page = st.radio("Điều hướng", PAGES, key="nav", label_visibility="collapsed")
st.sidebar.caption(PAGE_HINT[page])

box_overview = st.sidebar.expander("Tình trạng dữ liệu", expanded=False)
with box_overview:
    if _upd_msg:
        st.warning(_upd_msg)
    if st.button("Cập nhật giá mới ngay", key="upd_now", help="Lấy giá cuối ngày mới nhất từ SSI (mất vài phút)."):
        run_update(force=True)
        st.rerun()

with st.sidebar.expander("Nhóm cổ phiếu cần xem", expanded=True):
    available = [u for u in UNIVERSES if members_of(u)]
    if not available:
        universe_name = UNIVERSES[0]
        st.error("Chưa có danh sách mã trong `config/universes/`.")
    else:
        universe_name = st.radio("Nhóm", available, index=0,
                                 format_func=lambda u: f"{UNIVERSE_LABEL[u]} ({len(members_of(u))} mã)")
        st.caption("HOSE, VN100, VN30 xếp hạng chung trong sàn HOSE. HNX xếp hạng riêng trong sàn HNX.")

with st.sidebar.expander("Số tiền bạn đầu tư", expanded=True):
    position_dong = st.number_input("Số tiền (đồng)", min_value=100000.0, value=100000000.0, step=1000000.0, format="%.0f",
                                    help="Gõ số đồng, ví dụ 100000000 là 100 triệu. Dùng để tính cần bao nhiêu phiên để bán hết ở mọi mã.")
    st.caption(f"= {money(position_dong / 1e9)}")
    position_ty = position_dong / 1e9
    st.caption("Muốn nhập theo số cổ phiếu đang nắm? Dùng ô Tra nhanh ở Trang chủ. "
               "Số tiền chỉ đổi số phiên để bán hết, không đổi thứ hạng các mã.")

with st.sidebar.expander("Tùy chỉnh cách chấm điểm và cảnh báo", expanded=False):
    participation = st.slider("Mỗi phiên tôi chỉ bán tối đa bao nhiêu % tiền giao dịch của cả thị trường", 5, 50, 20, 5,
                              help="Bán quá nhiều so với tiền giao dịch chung sẽ làm giá xê dịch. 20% là mức do người dùng chọn, không có quy định.") / 100
    window = st.select_slider("Tính trung bình trong bao nhiêu phiên", options=[20, 40, 60], value=20)
    alert_pct = st.slider("Ngưỡng cảnh báo: nhóm bất thường nhất (%)", 5, 25, 10, 5) / 100
    dtl_alert = st.number_input("Cảnh báo khi cần bán quá (số phiên)", min_value=1.0, value=5.0, step=1.0)
    w_amihud = st.slider("Tỷ trọng của độ trượt giá (phần còn lại là tiền giao dịch)", 0, 100, 50, 10) / 100
    st.caption("Các mức này do người dùng chọn, không có nguồn học thuật quy định. Xem trang Giải thích và giới hạn.")

with st.sidebar.expander("Giao diện", expanded=False):
    mode = st.radio("Chế độ", list(MODES), horizontal=True, key="mode")
    st.caption("Chọn màu chủ đạo")
    if st.session_state.get("sw") not in SWATCHES:
        st.session_state["sw"] = SWATCHES[0]
    sw = st.session_state["sw"]
    sc = st.columns(4)
    for i, c in enumerate(SWATCHES):
        if sc[i % 4].button("\u00a0", key=f"swb{i}", help="Chọn màu này"):
            st.session_state["sw"] = c
            st.rerun()
    st.markdown("<style>" + "".join(
        f".st-key-swb{i} button{{background:{c}!important;border:3px solid #fff!important;border-radius:50%!important;"
        f"width:2.4rem;height:2.4rem;min-height:2.4rem;padding:0!important;"
        + (f"box-shadow:0 0 0 3px {c};" if c == sw else "box-shadow:0 1px 4px rgba(0,0,0,.25);") + "}"
        for i, c in enumerate(SWATCHES)) + "</style>", unsafe_allow_html=True)
    own = st.toggle("Dùng màu riêng", key="own")
    own_color = st.color_picker("Màu riêng", sw, key="ownc", disabled=not own)
    accent = own_color if own else sw
    font = st.selectbox("Kiểu chữ", list(FONT_STACKS), key="font")
    bg_mode = st.radio("Hình nền thị trường", ["Động", "Tĩnh", "Tắt"], horizontal=True, key="bgmode",
                       help="Động: nến co giãn và trôi chậm như thị trường chạy. Tĩnh: giữ nguyên hình. Tắt: nền trơn.")
    speed = st.select_slider("Tốc độ trôi", ["Chậm", "Vừa", "Nhanh"], value="Vừa", disabled=bg_mode != "Động")
    strength = st.select_slider("Độ đậm của nền", ["Nhạt", "Vừa", "Đậm"], value="Nhạt", disabled=bg_mode == "Tắt")
st.sidebar.caption("Công cụ phân tích học thuật, không phải khuyến nghị đầu tư.")

dark = mode == "Tối"
st.markdown(theme_css(mode, accent, font, bg_mode, speed, strength), unsafe_allow_html=True)
st.markdown("<div class='mkt-bg'></div>", unsafe_allow_html=True)

# ------------------------------------------------------------------ kiểm tra dữ liệu và tính toán
if not DB_PATH.exists():
    st.error("Chưa có cơ sở dữ liệu `data/liquidity.db`.")
    st.markdown("Hãy nạp dữ liệu trước bằng lệnh:\n\n`python -m src.data.ingest --universe hose`\n\n"
                "Cần có tệp `.env` chứa `SSI_API_KEY` và `SSI_API_SECRET` (xem `.env.example`).")
    st.stop()

try:
    db_key = DB_PATH.stat().st_mtime
    full = compute_full(db_key, float(position_ty), float(participation), int(window),
                        float(alert_pct), float(dtl_alert), float(w_amihud))
except Exception as e:  # noqa: BLE001
    st.error(f"Không tính được điểm: {e}")
    st.stop()

members = members_of(universe_name)
sub = full[full["symbol"].isin(members)].copy()
missing = sorted(set(members) - set(sub["symbol"]))
if sub.empty:
    st.warning(f"Nhóm đang chọn chưa có dữ liệu giá. Chạy: python -m src.data.ingest --universe {universe_name}")
    st.stop()
sub["rank_in_universe"] = sub["risk_score"].rank(ascending=False, method="min").astype("Int64")
sub["has_alert"] = sub["alerts"].fillna("") != ""

last_date = full["date"].max()
updated = datetime.fromtimestamp(db_key, VN_TZ).strftime("%d/%m/%Y %H:%M")
n_stale = int(full["stale"].sum())
ULABEL = UNIVERSE_LABEL[universe_name]
EX = str(sub["exchange"].iloc[0])
n_ex = int((full["exchange"] == EX).sum())
with box_overview:
    st.markdown(f"**Dữ liệu giá đến:** {last_date:%d/%m/%Y}  \n**Cập nhật lúc:** {updated} (giờ Việt Nam)  \n"
                f"**Số mã đã nạp:** {len(full)}  \n**Mã thiếu phiên mới nhất:** {n_stale}")
    st.caption("Nguồn: SSI. Dữ liệu cuối ngày, không phải thời gian thực.")
    if n_stale > 0.2 * len(full):
        st.warning("Nhiều mã chưa có phiên mới nhất. Chạy lại bước nạp dữ liệu sau 15:00.")


def price_dong(x) -> float:
    """Giá đóng cửa ra đồng (SSI đôi khi trả theo nghìn đồng)."""
    x = float(x)
    return x * 1000 if x < 1000 else x


def holding_lines(row, value_ty: float, shares=None) -> list:
    """Các câu giải thích bằng lời thường cho một khoản đầu tư."""
    sym, adv_ty = row["symbol"], float(row["adv"]) / 1e9
    out = []
    if shares:
        out.append(f"Bạn nắm <b>{vn(shares)}</b> cổ phiếu {sym}, giá đóng cửa {vn(price_dong(row['close']))} đồng, "
                   f"trị giá khoảng <b>{money(value_ty)}</b>.")
    else:
        out.append(f"Khoản của bạn là <b>{money(value_ty)}</b> ở mã {sym}.")
    if adv_ty > 0:
        days = value_ty / (participation * adv_ty)
        pct = value_ty / adv_ty * 100
        out.append(f"Trung bình mỗi phiên, {sym} có khoảng <b>{money(adv_ty)}</b> được mua bán. "
                   f"Khoản của bạn bằng {('dưới 0,01' if pct < 0.01 else vn(pct, 2))}% con số đó.")
        cap_ty = participation * adv_ty
        out.append(f"Mỗi phiên bạn có thể bán tối đa khoảng <b>{vn(cap_ty * 1e9 / price_dong(row['close']))} cổ phiếu</b> "
                   f"(khoảng {money(cap_ty)}) mà không chiếm quá {participation:.0%} giao dịch của thị trường.")
        if days <= 1:
            out.append("Khoản của bạn nhỏ hơn mức đó, nên có thể bán hết trong <b>1 phiên</b>.")
        else:
            out.append(f"Nếu mỗi phiên bạn chỉ chiếm {participation:.0%} giao dịch của thị trường, cần khoảng "
                       f"<b>{math.ceil(days)} phiên</b> để bán hết.")
    if row["level"] == "Cao" and adv_ty > 0 and value_ty / (participation * adv_ty) <= 1:
        out.append("Xếp nhóm khó mua bán là so với các mã khác. Với khoản nhỏ như của bạn, việc bán vẫn không khó.")
    return out


def verdict(row) -> str:
    return "<br>".join(holding_lines(row, position_ty))

# ------------------------------------------------------------------ các trang
def page_home():
    masthead()
    hero("Dành cho nhà đầu tư", "Cổ phiếu bạn giữ, khi cần bán có bán được ngay không?",
         f"Chọn mã và nhập số cổ phiếu bạn đang nắm. Ra-đa cho biết cần mấy phiên để bán hết và so với {len(sub)} mã "
         f"của nhóm {ULABEL} thì mã đó dễ hay khó mua bán.")
    syms = sub.sort_values("risk_score", ascending=False)["symbol"].tolist()
    c1, c2, c3 = st.columns([2, 1.6, 1.6])
    q = c1.selectbox("Mã cổ phiếu", [""] + syms, format_func=lambda s: s or "Chọn hoặc gõ mã...", key="quick")
    how = c2.radio("Tôi nhập theo", ["Số cổ phiếu", "Số tiền"], horizontal=True, key="how")
    if how == "Số cổ phiếu":
        qty = c3.number_input("Số cổ phiếu đang nắm", min_value=1, value=1000, step=100, key="qty")
    else:
        qty = c3.number_input("Số tiền (đồng)", min_value=1000.0, value=float(position_dong), step=100000.0, format="%.0f", key="qmoney")
        c3.caption(f"= {money(qty / 1e9)}")
    if q:
        row = sub[sub["symbol"] == q].iloc[0]
        if how == "Số cổ phiếu":
            lines = holding_lines(row, qty * price_dong(row["close"]) / 1e9, shares=int(qty))
        else:
            lines = holding_lines(row, qty / 1e9)
        say(f"Kết quả cho {q}", lines, "Ước tính theo dữ liệu cuối ngày, không phải khuyến nghị mua hay bán.")
        meter(row["risk_score"])
    else:
        st.caption("Chọn một mã ở trên để xem kết quả.")
    top = sub.sort_values("risk_score", ascending=False).iloc[0]
    kinds = sub.loc[sub["has_alert"], "alerts"].str.split("; ").explode().value_counts()
    stats([
        dict(k="Mã khó mua bán nhất trong nhóm", v=str(top["symbol"]), bad=True,
             n=f"Điểm {vn(top['risk_score'], 1)}/100, so với {n_ex} mã cùng sàn {EX}."),
        dict(k="Số phiên để bán hết khoản của bạn (trung vị cả nhóm)", v=f"{vn(sub['days_to_liq'].median(), 1)} phiên",
             n=f"Khoản {money(position_ty)}, mỗi phiên chiếm tối đa {participation:.0%} tiền giao dịch."),
        dict(k="Mã cần chú ý thêm", v=f"{int(sub['has_alert'].sum())} / {len(sub)}",
             n=(f"Phổ biến nhất: {kinds.index[0]} ({int(kinds.iloc[0])} mã)." if len(kinds) else "Hiện chưa có cảnh báo nào.")),
    ])
    if missing:
        st.info(f"{len(missing)} mã trong nhóm chưa có dữ liệu giá: {', '.join(missing[:15])}{'...' if len(missing) > 15 else ''}")
    left, right = st.columns([2, 3], gap="large")
    with left:
        say("Trang này giúp bạn làm gì?", [
            "<b>Trước khi mua:</b> kiểm tra mã đó có dễ bán lại khi bạn cần tiền không.",
            "<b>Khi đang giữ:</b> biết khoản của bạn cần mấy phiên để bán hết, và mã có dấu hiệu lạ không (nước ngoài bán mạnh, khối lượng bất thường).",
            "<b>Khi so sánh:</b> chọn mã dễ mua bán hơn trong các mã tương tự.",
            "<b>Điểm 0-100</b>: càng cao càng khó mua bán. Đây là thứ hạng so với các mã khác, không phải dự đoán giá.",
            "<b>Cảnh báo</b> là dấu hiệu cần xem thêm (khối lượng, nước ngoài, giá sát trần hoặc sàn), không nằm trong điểm."],
            "Công thức chi tiết ở trang <b>Giải thích và giới hạn</b>.")
    with right:
        t10 = sub.sort_values("risk_score", ascending=False).head(10).iloc[::-1]
        fig = go.Figure(go.Bar(x=t10["risk_score"], y=t10["symbol"], orientation="h",
                               marker_color=[LEVEL_COLOR.get(lv(l), "#888") for l in t10["level"]],
                               text=[vn(v, 1) for v in t10["risk_score"]], textposition="outside",
                               hovertemplate="%{y}<br>Điểm %{x:.1f}<extra></extra>"))
        fig.update_xaxes(title="Điểm khó mua bán (0-100)", range=[0, 108])
        show(pro(fig, dark, f"10 mã khó mua bán nhất, nhóm {ULABEL}", 420), "hm_top10")


def page_rank():
    masthead()
    hero("Danh sách", "Toàn bộ cổ phiếu trong nhóm", f"Nhóm {ULABEL}, xếp từ khó mua bán nhất đến dễ mua bán nhất.")
    f1, f2, f3 = st.columns([2, 2, 1])
    opts = ["Khó mua bán", "Vừa phải", "Dễ mua bán", "Chưa đủ dữ liệu"]
    levels = f1.multiselect("Lọc theo mức", opts, default=opts)
    query = f2.text_input("Tìm mã", "").strip().upper()
    only_alert = f3.checkbox("Chỉ mã có cảnh báo", value=False)
    view = sub[sub["level"].map(lv).isin(levels)]
    if query:
        view = view[view["symbol"].str.contains(query, regex=False)]
    if only_alert:
        view = view[view["has_alert"]]
    table = to_display(view.sort_values("risk_score", ascending=False))
    if table.empty:
        st.info("Không có mã nào khớp bộ lọc.")
    else:
        html_table(table, bar_col="Điểm khó mua bán (0-100)")
        st.download_button("Tải danh sách về máy (bảng tính .csv)", csv_bytes(table),
                           file_name=f"danh_sach_{universe_name}_{last_date:%Y%m%d}.csv", mime="text/csv")
    with st.expander("Giải thích từng cột"):
        st.markdown("\n".join(f"- **{c}**: {h}" for c, (h, _) in COLS.items()))
    st.caption("Rê chuột lên tiêu đề cột để xem giải thích ngắn.")


def page_charts():
    masthead()
    hero("Bản đồ", "So sánh các mã bằng hình vẽ", "Hai hình giúp thấy mã nào nằm xa số đông về thanh khoản.")
    dm = chart_tools("charts")
    names = ["hnx"] if universe_name == "hnx" else [n for n in available if n != "hnx"]
    fig1 = go.Figure()
    for i_, name in enumerate(names):
        scores = full[full["symbol"].isin(members_of(name))]["risk_score"].dropna()
        fig1.add_trace(go.Box(y=scores, name=UNIVERSE_LABEL[name], boxpoints="outliers", boxmean=True,
                              marker_color=PALETTE[i_ % len(PALETTE)], opacity=1 if name == universe_name else 0.65))
    fig1.update_yaxes(title="Điểm khó mua bán (0-100)")
    show(pro(fig1, dark, f"Điểm khó mua bán các nhóm trong sàn {EX}", 460, dm), "ch_box")
    med = {UNIVERSE_LABEL[n]: full[full["symbol"].isin(members_of(n))]["risk_score"].median() for n in names}
    say("Cách đọc hình này", [
        "Mỗi <b>hộp</b> là một nhóm cổ phiếu; hộp chứa một nửa số mã ở giữa, vạch trong hộp là mức giữa.",
        "Hộp nằm <b>thấp</b> nghĩa là nhóm đó nhìn chung dễ mua bán; chấm lẻ phía trên là những mã khác thường.",
        "Các nhóm trong hình cùng một sàn nên so sánh được; HOSE và HNX xếp hạng riêng nên không so điểm giữa hai sàn."],
        "Mức giữa của điểm: " + "; ".join(f"{k} {vn(v, 1)}" for k, v in med.items()) + ".")

    sc = full[full["exchange"] == EX].dropna(subset=["adv", "amihud"])
    sc = sc[(sc["adv"] > 0) & (sc["amihud"] > 0)].copy()
    sc["adv_ty"] = sc["adv"] / 1e9
    fig2 = go.Figure()
    rest = sc[~sc["symbol"].isin(members)]
    fig2.add_trace(go.Scatter(x=rest["adv_ty"], y=rest["amihud"], mode="markers", name="Mã ngoài nhóm", text=rest["symbol"],
                              marker=dict(size=5, color="#92B9E3", opacity=0.55),
                              hovertemplate="%{text}<br>Tiền giao dịch %{x:.1f} tỷ<br>Độ trượt giá %{y:.5f}<extra></extra>"))
    for l_raw, name in LEVEL_TXT.items():
        s = sc[sc["symbol"].isin(members) & (sc["level"] == l_raw)]
        if s.empty:
            continue
        fig2.add_trace(go.Scatter(x=s["adv_ty"], y=s["amihud"], mode="markers+text", name=f"{ULABEL}: {name}",
                                  text=s["symbol"], textposition="top center",
                                  marker=dict(size=9, color=LEVEL_COLOR[name]),
                                  hovertemplate="%{text}<br>Tiền giao dịch %{x:.1f} tỷ<br>Độ trượt giá %{y:.5f}<extra></extra>"))
    fig2.update_xaxes(type="log", title="Tiền giao dịch bình quân (tỷ đồng mỗi phiên, thang log)")
    fig2.update_yaxes(type="log", title="Độ trượt giá (thang log)")
    show(pro(fig2, dark, "Tiền giao dịch và độ trượt giá của từng mã", 540, dm), "ch_scatter")
    rho = float(sc["adv"].rank().corr(sc["amihud"].rank())) if len(sc) > 2 else float("nan")
    say("Cách đọc hình này", [
        "Mỗi chấm là một mã. Hai trục dùng thang log để thấy cả mã lớn lẫn mã nhỏ.",
        "<b>Góc trên bên trái</b> (giao dịch ít, giá trượt nhiều) là khó mua bán nhất; <b>góc dưới bên phải</b> là dễ nhất.",
        "Bấm tên trong chú giải để ẩn hoặc hiện từng nhóm màu."],
        f"Hệ số tương quan hạng giữa tiền giao dịch và độ trượt giá trên {len(sc)} mã là <b>{vn(rho, 2)}</b>: "
        "hai thước đo gần như xếp hạng giống nhau, đây là một giới hạn của điểm tổng hợp.")


def liquidity_series(h: pd.DataFrame) -> pd.DataFrame:
    am = pd.Series(liq.amihud(h["close"], h["value"], window=window), index=h.index)
    adv = h["value"].rolling(window, min_periods=min(10, window)).mean()
    return pd.DataFrame({"amihud": am, "adv_ty": adv / 1e9, "value_ty": h["value"] / 1e9,
                         "dtl": position_ty * 1e9 / (participation * adv)})


def fig_liquidity(h: pd.DataFrame, sym: str, dm: str) -> go.Figure:
    s = liquidity_series(h)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.34, 0.33, 0.33])
    fig.add_trace(go.Scatter(x=s.index, y=s["amihud"], name=f"Độ trượt giá (TB {window} phiên)", line=dict(color=accent)), 1, 1)
    up = (h["close"].diff() >= 0).fillna(True)
    k, un = unit_of(s["value_ty"])
    fig.add_trace(go.Bar(x=s.index, y=s["value_ty"] * k, name="Tiền giao dịch mỗi ngày", customdata=money_hover(s["value_ty"]),
                         hovertemplate="%{customdata}<extra></extra>",
                         marker_color=[UP if u else DOWN for u in up], opacity=0.55), 2, 1)
    fig.add_trace(go.Scatter(x=s.index, y=s["adv_ty"] * k, name=f"Tiền giao dịch bình quân {window} phiên",
                             customdata=money_hover(s["adv_ty"]), hovertemplate="%{customdata}<extra></extra>",
                             line=dict(color=WARN)), 2, 1)
    fig.add_trace(go.Scatter(x=s.index, y=s["dtl"], name="Số phiên để bán hết", line=dict(color=DOWN)), 3, 1)
    fig.add_hline(y=dtl_alert, row=3, col=1, line_dash="dash", line_color="#956AD6", annotation_text=f"Mốc cảnh báo {dtl_alert:g}")
    fig.update_yaxes(title_text="Độ trượt giá", row=1, col=1)
    fig.update_yaxes(title_text=un.capitalize(), row=2, col=1)
    fig.update_yaxes(title_text="Số phiên", row=3, col=1)
    fig.update_xaxes(rangebreaks=rangebreaks(h.index), **VN_DATE)
    fig.update_xaxes(rangeselector=RANGESEL, row=1, col=1)
    fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.05), row=3, col=1)
    return pro(fig, dark, f"{sym}: thanh khoản theo thời gian", 800, dm, "x unified")

# độ dày và màu từng đường trung bình: càng dài càng dày
MA_STYLE = {10: (0.8, "#70C2B4"), 20: (1.0, "#F0BD74"), 50: (2.2, "#6C7EE1"), 100: (2.9, "#E8AACA"), 200: (3.8, "#956AD6")}
def fig_technical(h: pd.DataFrame, sym: str, mas: list, rsi_n: int, mf: int, ms: int, msig: int, dm: str) -> go.Figure:
    close = h["close"]
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.5, 0.14, 0.18, 0.18])
    fig.add_trace(go.Candlestick(x=h.index, open=h["open"], high=h["high"], low=h["low"], close=close, name="Giá",
                                 increasing_line_color=UP, decreasing_line_color=DOWN), 1, 1)
    for n in sorted(mas, reverse=True):          # vẽ đường dày trước, đường mảnh phủ lên trên
        w_, col = MA_STYLE.get(n, (1.4, "#92B9E3"))
        fig.add_trace(go.Scatter(x=h.index, y=sma(close, n), name=f"Trung bình {n} phiên",
                                 line=dict(width=w_, color=col)), 1, 1)
    up = h["close"] >= h["open"]
    k, un = unit_of(h["value"] / 1e9)
    fig.add_trace(go.Bar(x=h.index, y=h["value"] / 1e9 * k, name="Tiền giao dịch", customdata=money_hover(h["value"] / 1e9),
                         hovertemplate="%{customdata}<extra></extra>",
                         marker_color=[UP if u else DOWN for u in up], opacity=0.6), 2, 1)
    fig.add_trace(go.Scatter(x=h.index, y=rsi_wilder(close, rsi_n), name=f"Sức mạnh giá {rsi_n} phiên", line=dict(color="#7C60CF")), 3, 1)
    for l_ in (30, 70):
        fig.add_hline(y=l_, row=3, col=1, line_dash="dot", line_color="#C688EB")
    line, sig, hist = macd(close, mf, ms, msig)
    fig.add_trace(go.Bar(x=h.index, y=hist, name="Chênh lệch hai đường",
                         marker_color=[UP if v >= 0 else DOWN for v in hist.fillna(0)], opacity=0.6), 4, 1)
    fig.add_trace(go.Scatter(x=h.index, y=line, name="Động lượng", line=dict(color="#3A6FD8", width=1.3)), 4, 1)
    fig.add_trace(go.Scatter(x=h.index, y=sig, name="Đường tín hiệu", line=dict(color=WARN, width=1.3)), 4, 1)
    fig.update_yaxes(title_text="Giá (đồng)", row=1, col=1)
    fig.update_yaxes(title_text=un.capitalize(), row=2, col=1)
    fig.update_yaxes(title_text="Sức mạnh giá", range=[0, 100], row=3, col=1)
    fig.update_yaxes(title_text="Động lượng", row=4, col=1)
    fig.update_xaxes(rangebreaks=rangebreaks(h.index), **VN_DATE)
    fig.update_xaxes(rangeselector=RANGESEL, row=1, col=1)
    fig.update_layout(xaxis_rangeslider_visible=False)
    fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.05), row=4, col=1)
    return pro(fig, dark, f"{sym}: nến, đường trung bình, sức mạnh giá, động lượng (tham khảo)", 900, dm, "x unified")


def fig_foreign(f: pd.DataFrame, sym: str, dm: str) -> go.Figure:
    net = (f["buy_val"] - f["sell_val"]) / 1e9
    ok = (f["total_room"] > 0) & (f["remain_room"] >= 0) & (f["remain_room"] <= f["total_room"])
    room = (f["remain_room"] / f["total_room"] * 100).where(ok)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06, row_heights=[0.62, 0.38])
    cum = net.rolling(5, min_periods=1).sum()
    k, un = unit_of(net)
    fig.add_trace(go.Bar(x=f.index, y=net * k, name="Nước ngoài mua trừ bán mỗi ngày", customdata=money_hover(net),
                         hovertemplate="%{customdata}<extra></extra>",
                         marker_color=[UP if v >= 0 else DOWN for v in net.fillna(0)], opacity=0.8), 1, 1)
    fig.add_trace(go.Scatter(x=f.index, y=cum * k, name="Cộng dồn 5 phiên", customdata=money_hover(cum),
                             hovertemplate="%{customdata}<extra></extra>",
                             line=dict(color="#956AD6", width=2.2)), 1, 1)
    fig.add_trace(go.Scatter(x=f.index, y=room, name="Room nước ngoài còn lại", line=dict(color="#6C7EE1", width=2.2),
                             hovertemplate="%{y:.1f}%<extra></extra>",
                             fill="tozeroy", fillcolor="rgba(108,126,225,0.18)"), 2, 1)
    fig.update_yaxes(title_text=un.capitalize(), row=1, col=1)
    fig.update_yaxes(title_text="Phần trăm", row=2, col=1)
    fig.update_xaxes(rangebreaks=rangebreaks(f.index), **VN_DATE)
    fig.update_xaxes(rangeselector=RANGESEL, row=1, col=1)
    fig.update_xaxes(rangeslider=dict(visible=True, thickness=0.05), row=2, col=1)
    return pro(fig, dark, f"{sym}: dòng tiền nước ngoài", 640, dm, "x unified")


def tab_foreign(sym: str, row) -> None:
    f = load_foreign_hist(db_key, sym)
    if f.empty or f[["buy_val", "sell_val"]].dropna(how="all").empty:
        st.info(f"SSI chưa trả dữ liệu giao dịch của nhà đầu tư nước ngoài cho {sym}.")
        return
    net = (f["buy_val"] - f["sell_val"]) / 1e9
    last5 = net.dropna().tail(5).sum()
    streak = row.get("sell_streak")
    used = row.get("room_used_pct")
    tiles([("Nước ngoài mua trừ bán, 5 phiên gần nhất", money(last5)),
           ("Số phiên nước ngoài bán liên tiếp", f"{int(streak)} phiên" if pd.notna(streak) else "–"),
           ("Đã nắm trong hạn mức được phép", "–" if flag(row.get("room_anomaly")) or pd.isna(used) else f"{vn(used * 100, 0)}%"),
           ("Dữ liệu nước ngoài đến ngày", f"{f.index.max():%d/%m/%Y}")])
    dm = chart_tools("fx")
    try:
        show(fig_foreign(f, sym, dm), "dt_fx")
    except Exception as e:  # noqa: BLE001
        st.error(f"Không vẽ được biểu đồ dòng tiền nước ngoài: {e}")
    say("Cách đọc hình này", [
        "<b>Hàng trên:</b> cột xanh là ngày nước ngoài mua nhiều hơn bán, cột đỏ là ngày bán nhiều hơn mua; đường tím là cộng dồn 5 phiên gần nhất.",
        "<b>Hàng dưới:</b> phần hạn mức nước ngoài còn được mua thêm. Đường đi xuống nghĩa là nước ngoài đang nắm thêm; về 0 là hết chỗ.",
        "Số liệu nước ngoài do SSI cung cấp theo ngày, có thể trễ hơn dữ liệu giá một phiên."],
        "Dòng tiền nước ngoài chỉ là cảnh báo bổ sung, <b>không nằm trong điểm khó mua bán</b>.")

NEWS_SITES = [("Tất cả báo", ""), ("CafeF", "cafef.vn"), ("Vietstock", "vietstock.vn"), ("VnExpress", "vnexpress.net"),
              ("Tin nhanh chứng khoán", "tinnhanhchungkhoan.vn")]


def news_url(sym: str, kw: str, site: str = "") -> str:
    q = f"{sym} {kw}".strip() + (f" site:{site}" if site else "")
    return f"https://news.google.com/search?q={quote(q)}&hl=vi&gl=VN&ceid=VN:vi"


def tab_events_news(sym: str, a: pd.DataFrame) -> None:
    st.markdown("#### Sự kiện quyền gần đây")
    if a.empty:
        st.caption(f"Chưa có sự kiện quyền nào của {sym} trong dữ liệu đã nạp (cổ tức, thưởng cổ phiếu, họp cổ đông...).")
    else:
        html_table(a.rename(columns={
            "exright_date": "Ngày giao dịch không hưởng quyền", "record_date": "Ngày chốt danh sách",
            "issue_date": "Ngày thực hiện", "event_title": "Nội dung sự kiện", "ratio": "Tỷ lệ (nguyên văn từ SSI)"}).fillna(""),
            strong=("Nội dung sự kiện",))
        st.caption("Nguồn: SSI (corporateActions). Cột tỷ lệ ghi nguyên văn; ý nghĩa tùy loại sự kiện, xem cột nội dung.")
    st.markdown("#### Tin tức liên quan")
    kw = st.text_input("Từ khóa tìm tin (thêm sau mã)", value="cổ phiếu", key=f"kw_{sym}",
                       help="Ví dụ: cổ tức, kết quả kinh doanh, phát hành thêm.")
    cols = st.columns(len(NEWS_SITES))
    for col, (label, site) in zip(cols, NEWS_SITES):
        col.link_button(label, news_url(sym, kw.strip(), site))
    st.caption("Bấm nút để mở trang tin về mã này trên Google Tin tức (mở tab mới). Ra-đa chỉ dẫn tới bài của báo, "
               "không sao chép nội dung bài.")

def page_detail():
    masthead()
    order = sub.sort_values("risk_score", ascending=False)["symbol"].tolist()
    sym = st.selectbox("Chọn cổ phiếu", order, key="sym", help="Sắp từ khó mua bán nhất đến dễ nhất.")
    row = sub[sub["symbol"] == sym].iloc[0]
    hero("Tra cứu cổ phiếu", sym, "")
    say(f"{sym} dễ hay khó mua bán?", [verdict(row)],
        f"Điểm khó mua bán <b>{vn(row['risk_score'], 1)}/100</b> · hạng "
        f"{'–' if pd.isna(row['rank_in_universe']) else int(row['rank_in_universe'])}/{len(sub)} trong nhóm · "
        f"hạng {'–' if pd.isna(row['rank_all']) else int(row['rank_all'])}/{n_ex} trong sàn {EX}."
        + (f"<br>Cảnh báo: {escape(alert_text(alert_flags(sub.loc[[row.name]]).iloc[0]))}"
           if alert_flags(sub.loc[[row.name]]).iloc[0].any() else "<br>Chưa có cảnh báo nào."))
    meter(row["risk_score"])
    
    try:
        hist = load_history(db_key)
    except Exception as e:  # noqa: BLE001
        st.error(f"Không đọc được lịch sử giá: {e}")
        hist = pd.DataFrame(columns=["symbol", "date"])
    h = hist[hist["symbol"] == sym].sort_values("date").drop_duplicates("date").set_index("date")
    acts = load_actions(db_key, sym)

    def px(v) -> str:
        v = pd.to_numeric(v, errors="coerce")
        return "–" if pd.isna(v) else f"{vn(price_dong(v))} đồng"
    day = pd.Timestamp(row["date"]).normalize()
    lims = load_limit_rows(db_key, sym)
    same = lims[lims["d"] == day] if not lims.empty else lims          # chỉ lấy đúng phiên của giá đóng cửa
    lim = same.iloc[-1] if len(same) else None
    ref = pd.to_numeric(lim["ref_price"], errors="coerce") if lim is not None else float("nan")
    ref_note = ""
    if pd.isna(ref) and len(h) >= 2:                                    # chưa có dữ liệu SSI cho phiên này
        ref, ref_note = price_dong(h["close"].iloc[-2]), " (ước tính: giá đóng cửa phiên trước)"
    elif pd.notna(ref):
        ref = price_dong(ref)
    chg = "–" if pd.isna(ref) or not ref else f"{row['close'] / ref * 100 - 100:+.2f}%".replace(".", ",")
    tiles([("Giá tham chiếu", px(ref)), ("Giá đóng cửa", f"{vn(row['close'])} đồng"),
           ("Trần / sàn", "–" if lim is None else f"{px(lim['ceiling'])} / {px(lim['floor'])}")])
    tiles([("Đóng cửa so với tham chiếu", chg), ("Tiền giao dịch bình quân", f"{money(row['adv'] / 1e9)} mỗi phiên"),
           ("Độ trượt giá", vn(row["amihud"], 5)), ("Số phiên để bán hết", vn(row["days_to_liq"], 2))])
    st.caption(f"Giá phiên {day:%d/%m/%Y}. Giá tham chiếu{ref_note or ' theo SSI'}. "
               "Dữ liệu cuối ngày từ SSI.")
    names = ["Thanh khoản theo thời gian", "Dòng tiền nước ngoài", "Giá và chỉ báo (tham khảo)", "Sự kiện quyền & Tin tức"]
    tabs = st.tabs(names)
    t_liq, t_fx, t_tech = tabs[0], tabs[1], tabs[2]
    with t_liq:
        if len(h) < 5:
            st.warning("Mã này có quá ít phiên để vẽ biểu đồ.")
        else:
            dm = chart_tools("liq")
            try:
                show(fig_liquidity(h, sym, dm), "dt_liq")
            except Exception as e:  # noqa: BLE001
                st.error(f"Không vẽ được biểu đồ thanh khoản: {e}")
            say("Cách đọc hình này", [
                "<b>Hàng trên, độ trượt giá:</b> đường đi lên là giá nhạy hơn với mỗi tỷ đồng giao dịch, thanh khoản xấu đi.",
                "<b>Hàng giữa, tiền giao dịch:</b> cột là từng phiên (xanh: giá không giảm so với hôm trước, đỏ: giảm); đường vàng là mức bình quân.",
                "<b>Hàng dưới, số phiên để bán hết:</b> vượt đường mốc là cần nhiều phiên hơn mức bạn đặt.",
                "Dùng nút <b>1 tháng, 3 tháng, 6 tháng, 1 năm</b> hoặc kéo thanh trượt phía dưới để chọn khoảng thời gian."])
    with t_fx:
        tab_foreign(sym, row)
    with t_tech:
        if len(h) < 5 or not {"open", "high", "low", "close"}.issubset(h.columns):
            st.info("Chưa đủ dữ liệu giá mở, cao, thấp, đóng để vẽ nến.")
        else:
            dm = chart_tools("tech")
            with st.expander("Tùy chỉnh chỉ báo (mức phổ biến, có thể đổi)"):
                c1, c2, c3 = st.columns(3)
                opts = [n for n in (10, 20, 50, 100, 200) if n <= len(h)]
                mas = c1.multiselect("Đường trung bình (số phiên)", opts, default=[n for n in (20, 50, 200) if n in opts])
                rsi_n = c1.number_input("Chu kỳ sức mạnh giá", 2, 60, 14)
                mf = c2.number_input("Động lượng: đường nhanh", 2, 60, 12)
                ms = c2.number_input("Động lượng: đường chậm", 3, 120, 26)
                msig = c3.number_input("Động lượng: đường tín hiệu", 2, 60, 9)
                if ms <= mf:
                    st.warning("Đường chậm nên lớn hơn đường nhanh.")
            try:
                show(fig_technical(h, sym, mas, int(rsi_n), int(mf), int(ms), int(msig), dm), "dt_tech")
            except Exception as e:  # noqa: BLE001
                st.error(f"Không vẽ được biểu đồ giá: {e}")
            say("Cách đọc hình này", [
                "<b>Nến:</b> xanh là giá đóng cửa cao hơn mở cửa, đỏ là thấp hơn; râu nến là giá cao nhất và thấp nhất phiên.",
                "<b>Đường trung bình:</b> đường càng dài càng dày; giá nằm trên đường dài thường được coi là xu hướng tăng.",
                "<b>Sức mạnh giá:</b> trên 70 gọi là quá mua, dưới 30 là quá bán (mốc quy ước).",
                "<b>Động lượng:</b> đường nhanh cắt lên đường tín hiệu là đà tăng."],
                "Các chỉ báo này chỉ giúp quan sát, <b>không nằm trong điểm khó mua bán</b> và không phải khuyến nghị mua bán.")
    with tabs[3]:
        tab_events_news(sym, acts)

def page_alerts():
    masthead()
    hero("Cảnh báo", "Những mã cần chú ý thêm", f"Nhóm {ULABEL}. Cảnh báo là dấu hiệu để xem xét, không nằm trong điểm.")
    st.markdown(ALERT_CSS, unsafe_allow_html=True)
    fl_all = alert_flags(sub)
    al = sub[sub["has_alert"] | fl_all.any(axis=1)].copy()
    fl = fl_all.loc[al.index]
    al["n_alert"] = fl.sum(axis=1)
    al = al.sort_values(["n_alert", "risk_score"], ascending=False)
    fl = fl.loc[al.index]
    counts = fl.sum()

    cells = "".join(
        f"<div class='atile{' off' if counts[c] == 0 else ''}' style='--c:{col}'><div class='ai'>{icon}</div>"
        f"<div class='an'>{int(counts[c])}</div><div class='at'>{escape(name)}</div><div class='aw'>{escape(why)}</div></div>"
        for c, name, icon, col, why in ALERT_TYPES)
    st.markdown(f"<div class='atiles'>{cells}</div>", unsafe_allow_html=True)
    if al.empty:
        st.success("Không có mã nào trong nhóm kích hoạt cảnh báo.")
    else:
        dm = chart_tools("alerts")
        left, right = st.columns([2, 3], gap="large")
        used = [t for t in ALERT_TYPES if counts[t[0]] > 0]
        with left:
            used_sorted = sorted(used, key=lambda t: counts[t[0]])
            fig = go.Figure(go.Bar(
                x=[int(counts[t[0]]) for t in used_sorted], y=[f"{t[2]} {t[1]}" for t in used_sorted], orientation="h",
                marker_color=[t[3] for t in used_sorted], text=[int(counts[t[0]]) for t in used_sorted],
                textposition="outside", hovertemplate="%{y}: %{x} mã<extra></extra>"))
            fig.update_xaxes(title="Số mã", range=[0, max(counts) * 1.2])
            show(pro(fig, dark, "Mỗi loại cảnh báo có bao nhiêu mã", 120 + 48 * len(used), dm), "al_bar")
        with right:
            top = al.head(30)
            order = list(top["symbol"])
            fig2 = go.Figure()
            for c, name, icon, col, _ in used:
                syms = [s for s, f in zip(top["symbol"], fl.loc[top.index, c]) if f]
                fig2.add_trace(go.Scatter(x=[f"{icon} {name}"] * len(syms), y=syms, mode="markers", name=name,
                                          marker=dict(symbol="square", size=17, color=col),
                                          hovertemplate="%{y}: " + name + "<extra></extra>"))
            fig2.update_yaxes(categoryorder="array", categoryarray=order[::-1], title="")
            fig2.update_xaxes(side="top", tickangle=-25, title="")
            fig2.update_layout(showlegend=False)
            show(pro(fig2, dark, "Mã nào dính loại cảnh báo nào (30 mã nổi bật nhất)", 160 + 24 * len(top), dm), "al_mx")
        st.markdown("### Những mã cần chú ý nhất")
        st.caption("Xếp theo số loại cảnh báo, rồi theo điểm khó mua bán. Thanh màu cho thấy mã nằm ở đâu giữa dễ và khó mua bán.")
        st.markdown(alert_cards_html(al, fl), unsafe_allow_html=True)
        with st.expander(f"Xem toàn bộ {len(al)} mã có cảnh báo"):
            detail = pd.DataFrame({
                "Mã": al["symbol"].values, "Điểm khó mua bán": al["risk_score"].values,
                "Mức": [lv(x) for x in al["level"]], "Số phiên để bán hết": al["days_to_liq"].values,
                "Số phiên nước ngoài bán liên tiếp": al["sell_streak"].values,
                "Cảnh báo": [alert_text(r) for _, r in fl.iterrows()]})
            html_table(detail, bar_col="Điểm khó mua bán")
            st.download_button("Tải chi tiết (bảng tính .csv)", csv_bytes(detail),
                               file_name=f"canh_bao_{universe_name}_{last_date:%Y%m%d}.csv", mime="text/csv")
    say("Cách đọc cảnh báo", [
        "Mỗi ô màu phía trên là một loại cảnh báo; ô mờ là loại chưa có mã nào dính.",
        "Cảnh báo khối lượng và nước ngoài so mã với phần còn lại của thị trường; mức nhạy chỉnh ở thanh bên.",
        f"Cảnh báo bán hết rất lâu bật khi cần hơn {dtl_alert:g} phiên.",
        "Mã có cảnh báo số liệu room lạ là do dữ liệu hạn mức nước ngoài của SSI không hợp lệ, cần kiểm tra thêm."],
        "Cảnh báo là tín hiệu để xem xét, không phải kết luận.")

def page_method():
    masthead()
    hero("Giải thích", "Cách tính và giới hạn của ra-đa", "Phần dành cho người muốn biết công thức, nguồn và những điều ra-đa chưa làm được.")
    st.markdown("### Bảng giải thích các chỉ số")
    rows = "".join(f"<tr><td>{escape(a)}</td><td>{escape(b)}</td><td>{escape(c)}</td><td>{escape(d)}</td></tr>"
                   for a, b, c, d in GLOSSARY)
    st.markdown("<table class='gloss'><thead><tr><th>Chỉ số</th><th>Nghĩa là gì</th><th>Cách tính</th><th>Cách đọc</th></tr></thead>"
                f"<tbody>{rows}</tbody></table>", unsafe_allow_html=True)
    st.markdown(f"""
### Cách chấm điểm
**Thành phần 1, độ trượt giá (Amihud).** Trung bình trong cửa sổ của |lợi suất ngày| chia cho tiền giao dịch (tỷ đồng).
Cần tối thiểu 10 ngày có giao dịch trong cửa sổ.

**Thành phần 2, số phiên để bán hết** = khoản cần bán / (phần trăm tham gia x tiền giao dịch bình quân).
Vì khoản và phần trăm tham gia giống nhau cho mọi mã, thứ hạng này bằng thứ hạng của nghịch đảo tiền giao dịch,
nên hai mức đó chỉ đổi con số hiển thị, không đổi thứ hạng.

**Điểm (0-100)** = trung bình có trọng số của hai thứ hạng phân vị (mặc định trọng số bằng nhau), tính riêng trong từng sàn: HOSE, VN100 và VN30 cùng so với toàn HOSE, HNX so với toàn HNX. Không so điểm giữa hai sàn; muốn so hai sàn thì dùng số phiên để bán hết và tiền giao dịch bình quân.
Nước ngoài, khối lượng bất thường và giá sát trần hoặc sàn chỉ là cảnh báo, không vào điểm.
Chỉ báo giá (đường trung bình, sức mạnh giá, động lượng) chỉ để quan sát, không vào điểm.

### Cơ sở tài liệu
- Amihud (2002), *Journal of Financial Markets* 5(1): công thức độ trượt giá.
- Dinh & Tran (2023), *Cogent Business & Management* 10(3); Duong et al. (2024), *SAGE Open*: áp dụng cho HOSE/HNX.
- Nardo et al. (2008), OECD/JRC: chuẩn hóa bằng thứ hạng, trọng số bằng nhau làm mốc, kiểm tra độ nhạy.
- Hoyos et al. (2020), IMF WP/20/141: chỉ số tổng hợp bằng trung bình đơn giản.

### Mức do người dùng chọn hoặc giả định (không có nguồn quy định)
Khoản cần bán, phần trăm tham gia, cửa sổ, ngưỡng cảnh báo, mốc {dtl_alert:g} phiên, tỷ trọng.

### Giới hạn
- Dữ liệu cuối ngày, chưa đo được độ sâu sổ lệnh và chênh lệch mua bán trong phiên.
- Giá trị giao dịch là giá trị khớp lệnh; đối chiếu với SSI cho VN30 ngày 16/11/2026 lệch khoảng 0,7%.
- Ngày giá chạm biên độ ±7% và ngày không giao dịch chưa được xử lý riêng.
- Độ trượt giá và tiền giao dịch tương quan rất mạnh, nên điểm tổng hợp ít thêm thông tin so với một thước đo.
- Dữ liệu nước ngoài có thể thiếu ngày hoặc sai hạn mức (ví dụ GVR); các mã này được gắn cảnh báo.
- SSI không trả dữ liệu giá cho một số mã (ví dụ ATP), nên các mã này không có trong bảng điểm.
- Mã không giao dịch phiên nào trong cửa sổ tính hiện "Chưa đủ dữ liệu"; thực chất đó là mã không giao dịch, không phải lỗi dữ liệu.
- Điểm là thứ hạng tương đối trong sàn. Mã giao dịch thưa nằm ở đáy xếp hạng nên các mã còn lại trông tốt hơn thực tế, rõ nhất ở HNX.
- Với mã giao dịch thưa (ví dụ AME), số phiên để bán hết có thể lên hàng nghìn; con số này chỉ có nghĩa là "gần như không thể thoát vị thế", không phải dự báo.
- Danh sách mã lấy từ SSI; ATP (HOSE), BCH và MDD (HNX) không có dữ liệu giá nên không được chấm điểm.
- Mã có ít hơn {MIN_SESSIONS} phiên không tính được mức khối lượng so với thường lệ.
- Đây là công cụ phân tích học thuật, không phải khuyến nghị đầu tư.
""")
    st.markdown("### Độ ổn định của thứ hạng khi đổi cách tính")
    st.caption("Chạy với mức mặc định, không phụ thuộc thanh bên. Mất vài chục giây.")
    if st.button("Chạy kiểm tra độ ổn định"):
        try:
            res = compute_sensitivity(db_key, universe_name).round(3).to_frame()
            st.table(res)
            st.download_button("Tải bảng kết quả (bảng tính .csv)", csv_bytes(res.reset_index()),
                               file_name="do_on_dinh_thu_hang.csv", mime="text/csv")
        except Exception as e:  # noqa: BLE001
            st.error(f"Không chạy được: {e}")


{"Trang chủ": page_home, "Danh sách cổ phiếu": page_rank, "Bản đồ thanh khoản": page_charts,
 "Tra cứu cổ phiếu": page_detail, "Cảnh báo": page_alerts, "Giải thích và giới hạn": page_method}[page]()