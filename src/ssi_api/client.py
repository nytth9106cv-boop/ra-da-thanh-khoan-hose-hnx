from urllib.parse import urlencode
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()


class SSIClient:
    def __init__(self):
        self.base_url = os.getenv("SSI_API_URL", "https://api.ssi.com.vn").rstrip("/")
        self.api_key = os.getenv("SSI_API_KEY")
        self.api_secret = os.getenv("SSI_API_SECRET")
        if not self.api_key or not self.api_secret:
            raise RuntimeError("Thiếu SSI_API_KEY hoặc SSI_API_SECRET trong .env")
        self.session = requests.Session()
        self._token = None

    # ---------- xác thực ----------
    def _authenticate(self) -> None:
        resp = self.session.post(
            f"{self.base_url}/api/v3/auth/token",
            json={"apiKey": self.api_key, "apiSecret": self.api_secret},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        payload = body.get("data", body) if isinstance(body, dict) else body
        token = payload.get("accessToken") if isinstance(payload, dict) else None
        if not token:
            # In tên trường (không in giá trị) để chỉnh lại cho đúng
            keys = list(payload.keys()) if isinstance(payload, dict) else type(payload)
            raise RuntimeError(f"Không thấy accessToken. Các trường nhận được: {keys}")
        self._token = token

    # ---------- gọi dữ liệu ----------
    def get(self, path: str, params: dict | None = None, retries: int = 3) -> dict:
        if self._token is None:
            self._authenticate()
        for attempt in range(retries):
            resp = self.session.get(
                f"{self.base_url}{path}",
                params=urlencode(params, safe="/:") if params else None,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            if resp.status_code == 401:      # token hết hạn: xin lại rồi thử tiếp
                self._authenticate()
                continue
            if resp.status_code == 429:      # vượt giới hạn: chờ rồi thử lại
                time.sleep(2 * (attempt + 1))
                continue
            if resp.status_code == 204:      # không có dữ liệu trong khoảng này
                return {}
            if resp.status_code >= 400:
                raise RuntimeError(f"HTTP {resp.status_code} tại {path}: {resp.text[:500]}")
            return resp.json()
        raise RuntimeError(f"Gọi {path} thất bại sau {retries} lần thử")

    def get_paged(self, path: str, params: dict, page_size: int = 500,
                  max_pages: int = 500) -> list[dict]:
        """Lấy hết các trang. Thử pageSize lớn trước, bị từ chối thì hạ dần."""
        last_err = None
        for size in dict.fromkeys([page_size, 100, 10]):
            try:
                body = self.get(path, {**params, "pageIndex": 1, "pageSize": size})
            except RuntimeError as e:
                last_err = e
                continue
            break
        else:
            raise last_err

        rows: list[dict] = []
        page, prev_first = 1, None
        while True:
            data = body.get("data") or []
            if not data or (prev_first is not None and data[0] == prev_first):
                break                                  # hết dữ liệu hoặc server lặp trang
            rows.extend(data)
            prev_first = data[0]
            pages_count = body.get("pagesCount")
            if page >= max_pages or (pages_count is not None and page >= pages_count):
                break
            page += 1
            time.sleep(0.1)                            # nhẹ tay với giới hạn request
            body = self.get(path, {**params, "pageIndex": page, "pageSize": size})
        return rows

    # ---------- hai hàm dữ liệu chính (ngày: YYYY/MM/DD) ----------
    @staticmethod
    def _dt(d: str, end: bool = False) -> str:
        """'2026/11/01' -> '2026/11/01 00:00:00' (hoặc 23:59:59 nếu là ngày kết thúc)."""
        d = d.strip()
        return d if " " in d else f"{d} {'23:59:59' if end else '00:00:00'}"

    def ohlc_daily(self, symbol: str, date_from: str, date_to: str) -> list[dict]:
        return self.get_paged(
            "/api/v3/data/ohlc",
            {"symbol": symbol, "from": self._dt(date_from), "to": self._dt(date_to, True)},
        )

    def securities_summary(self, symbol: str, date_from: str, date_to: str) -> list[dict]:
        return self.get_paged(
            "/api/v3/data/securitiesSummary",
            {"symbol": symbol, "from": date_from, "to": date_to},
        )

    def master_data(self, date_from: str, date_to: str) -> list[dict]:
        return self.get_paged(
            "/api/v3/data/masterdata",
            {"from": date_from, "to": date_to},
        )

if __name__ == "__main__":
    # Chạy thử: python -m src.ssi_api.client
    c = SSIClient()
    rows = c.ohlc_daily("VNM", "2026/11/01", "2026/11/17")
    print("OHLC VNM:", len(rows), "dòng")
    print(rows[:2])
    rows2 = c.securities_summary("VNM", "2026/11/10", "2026/11/17")
    print("Summary VNM:", len(rows2), "dòng")
    print(rows2[:1])