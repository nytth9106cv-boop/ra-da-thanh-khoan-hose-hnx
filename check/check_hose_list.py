from src.ssi_api.client import SSIClient

r = SSIClient().get("/api/v3/data/securitiesByBoard", {"board": "HOSE"})
rows = r if isinstance(r, list) else r.get("data", r)
for x in rows:
    if x.get("symbol") in ("HPG", "HAX"):
        print(x)
print([(x.get("symbol"), x.get("icbName")) for x in rows if x.get("stockType") is None])