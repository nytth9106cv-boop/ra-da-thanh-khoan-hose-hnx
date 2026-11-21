from src.data.universe import load_universe
from src.ssi_api.client import SSIClient

rows = SSIClient().get("/api/v3/data/securitiesByBoard", {"board": "HOSE"})
none = [x for x in rows if x.get("stockType") is None]
print(len(none), "dong stockType rong")
for x in none:
    print(x["symbol"], "|", x.get("symbolNameVi"), "|", x.get("icbName"))

h, v100, v30 = (set(load_universe(n)) for n in ("hose", "vn100", "vn30"))
print("vn30 trong vn100:", v30 <= v100)
print("vn100 trong hose:", v100 <= h, "| thieu:", sorted(v100 - h))