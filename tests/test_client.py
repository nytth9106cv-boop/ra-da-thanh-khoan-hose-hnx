import pytest

from src.ssi_api.client import SSIClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("SSI_API_KEY", "fake")
    monkeypatch.setenv("SSI_API_SECRET", "fake")
    return SSIClient()


def test_dt_adds_time(client):
    assert client._dt("2026/11/01") == "2026/11/01 00:00:00"
    assert client._dt("2026/11/01", end=True) == "2026/11/01 23:59:59"
    assert client._dt("2026/11/01 08:00:00") == "2026/11/01 08:00:00"


def test_ohlc_daily_sends_datetime(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(
        client, "get_paged", lambda path, params, **kw: seen.update(params=params) or []
    )
    client.ohlc_daily("FPT", "2026/11/01", "2026/11/16")
    assert seen["params"]["from"] == "2026/11/01 00:00:00"
    assert seen["params"]["to"] == "2026/11/16 23:59:59"


def test_get_paged_collects_all_pages(client, monkeypatch):
    pages = {1: [{"id": 1}, {"id": 2}], 2: [{"id": 3}, {"id": 4}], 3: [{"id": 5}]}

    def fake_get(path, params=None, retries=3):
        return {"pagesCount": 3, "data": pages.get(params["pageIndex"], [])}

    monkeypatch.setattr(client, "get", fake_get)
    rows = client.get_paged("/x", {}, page_size=2)
    assert [r["id"] for r in rows] == [1, 2, 3, 4, 5]


def test_get_paged_falls_back_on_page_size(client, monkeypatch):
    def fake_get(path, params=None, retries=3):
        if params["pageSize"] > 10:
            raise RuntimeError("HTTP 400")
        return {"data": [{"id": 1}] if params["pageIndex"] == 1 else []}

    monkeypatch.setattr(client, "get", fake_get)
    rows = client.get_paged("/x", {})
    assert rows == [{"id": 1}]


def test_get_paged_stops_when_server_repeats_page(client, monkeypatch):
    monkeypatch.setattr(
        client, "get", lambda path, params=None, retries=3: {"data": [{"id": 1}, {"id": 2}]}
    )
    rows = client.get_paged("/x", {}, page_size=2)
    assert rows == [{"id": 1}, {"id": 2}]