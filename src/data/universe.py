from collections import Counter
from datetime import date
from pathlib import Path

from src.ssi_api.client import SSIClient

UNIVERSE_DIR = Path("config") / "universes"

# tên rổ -> (loại tham số, giá trị) gửi cho securitiesByBoard
SOURCES = {
    "vn30": ("index", "VN30"),
    "vn100": ("index", "VN100"),
    "hose": ("board", "HOSE"),
    "hnx": ("board", "HNX"),
}
EXTRA_SOURCES = {
    # securitiesByBoard HOSE không trả HPG; bổ sung từ rổ VN100 (cũng lấy từ SSI)
    "hose": [("index", "VN100")],
}

EXTRA_SYMBOLS = {
    # mã thuộc HOSE nhưng securitiesByBoard không trả về
    "hose": ["HAX"],
}

def list_universes() -> list[str]:
    return sorted(p.stem for p in UNIVERSE_DIR.glob("*.txt"))


def load_universe(name: str) -> list[str]:
    path = UNIVERSE_DIR / f"{name.lower()}.txt"
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    return [x.strip().upper() for x in lines if x.strip() and not x.startswith("#")]


def _is_stock(x: dict) -> bool:
    t = x.get("stockType")
    if t == "Stock":
        return True
    # thiếu nhãn: coi là cổ phiếu nếu có ngành ICB và không phải quỹ
    return t is None and bool(x.get("icbName")) and x.get("icbName") != "Quỹ đầu tư"


def sync_universe(name: str) -> list[str]:
    """Lấy danh sách mã từ SSI, ghi file, trả về các mã mới so với lần trước."""
    key = name.lower()
    sources = [SOURCES[key]] + EXTRA_SOURCES.get(key, [])
    client = SSIClient()
    rows: list[dict] = []
    for kind, value in sources:
        r = client.get("/api/v3/data/securitiesByBoard", {kind: value})
        part = r if isinstance(r, list) else r.get("data", r)
        print(f"{name} [{kind}={value}] - stockType:",
              dict(Counter(x.get("stockType") for x in part)))
        rows += part

    new = sorted({x["symbol"] for x in rows if x.get("symbol") and _is_stock(x)}
                 | set(EXTRA_SYMBOLS.get(key, [])))
    path = UNIVERSE_DIR / f"{key}.txt"
    old = set(load_universe(name)) if path.exists() else set()
    print(f"{name}: {len(new)} ma | them {sorted(set(new) - old)} | bo {sorted(old - set(new))}")
    src_text = "; ".join(f"{k}={v}" for k, v in sources)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# {name} - nguon: SSI securitiesByBoard {src_text}, "
                    f"lay ngay {date.today():%Y/%m/%d}\n" + "\n".join(new) + "\n",
                    encoding="utf-8")
    return sorted(set(new) - old)


def exchange_map() -> dict[str, str]:
    """Mã -> sàn (HOSE/HNX), suy ra từ file danh sách trong config/universes/."""
    m: dict[str, str] = {}
    for ex in ("hose", "hnx"):
        if (UNIVERSE_DIR / f"{ex}.txt").exists():
            for s in load_universe(ex):
                m.setdefault(s, ex.upper())
    return m