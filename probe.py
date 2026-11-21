from src.ssi_api.client import SSIClient

c = SSIClient()

# 1) Thành phần rổ VN30
r = c.get("/api/v3/data/securitiesByBoard", {"index": "VN30"})
rows = r if isinstance(r, list) else r.get("data", r)
print("VN30:", len(rows), "ma")
print(sorted(x["symbol"] for x in rows))
print(rows[0])

# 2) Tóm tắt chỉ số VN30 một ngày
r2 = c.get("/api/v3/data/indexSummary", {"index": "VN30", "tradingDate": "2026/11/16"})
print(r2)