"""API tests for Flask endpoints with mocked market data."""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from werkzeug.serving import make_server

from api import create_app
from change_detection import ChangeDetector
from database import connect
from market_data import MarketDataService, OHLCV_COLUMNS
from repository import WatchlistRepository


def _ohlcv(dates: list[date], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1_000_000] * len(closes),
        }
    )[OHLCV_COLUMNS]


class FakeMarketDataService(MarketDataService):
    def __init__(self, mapping: dict[str, pd.DataFrame]) -> None:
        self.mapping = mapping

    def fetch_daily_ohlcv(self, symbol: str, **_: object) -> pd.DataFrame:
        return self.mapping.get(symbol, pd.DataFrame(columns=OHLCV_COLUMNS)).copy()

    def fetch_nifty50(self, **_: object) -> pd.DataFrame:
        return self.fetch_daily_ohlcv("^NSEI")

    def fetch_intraday_ohlcv(self, symbol: str, **_: object) -> pd.DataFrame:
        df = self.mapping.get(symbol, pd.DataFrame(columns=OHLCV_COLUMNS)).copy()
        if not df.empty and "timestamp" not in df.columns:
            timestamps = pd.to_datetime(df["date"])
            df["timestamp"] = timestamps.dt.tz_localize("UTC")
        return df

    def fetch_nifty50_intraday(self, **_: object) -> pd.DataFrame:
        return self.fetch_intraday_ohlcv("^NSEI")

    def validate_symbol(self, symbol: str) -> bool:
        return symbol in self.mapping



class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = connect(":memory:")
        self.repo = WatchlistRepository(self.conn)
        self.t0 = datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)
        self.dates = [
            date(2026, 8, 29),
            date(2026, 9, 1),
            date(2026, 9, 2),
            date(2026, 9, 3),
            date(2026, 9, 4),
        ]
        self.market = FakeMarketDataService(
            {
                "RELIANCE.NS": _ohlcv(self.dates, [100.0, 101.0, 102.0, 103.0, 106.0]),
                "INFY.NS": _ohlcv(self.dates, [1500.0, 1498.0, 1501.0, 1504.0, 1505.0]),
                "TCS.NS": _ohlcv(self.dates, [3600.0, 3580.0, 3625.0, 3680.0, 3750.0]),
                "HDFCBANK.NS": _ohlcv(self.dates, [1600.0, 1604.0, 1610.0, 1600.0, 1588.0]),
                "^NSEI": _ohlcv(self.dates, [20000.0, 20020.0, 20040.0, 20060.0, 20070.0]),
            }
        )
        app = create_app(
            conn=self.conn,
            repository=self.repo,
            market_data_service=self.market,
            change_detector=ChangeDetector(),
        )
        app.config["TESTING"] = True
        self.client = app.test_client()

    def tearDown(self) -> None:
        self.conn.close()

    def test_create_user_and_watchlist(self) -> None:
        user_response = self.client.post("/api/users", json={"username": "alice"})
        self.assertEqual(user_response.status_code, 201)
        user = user_response.get_json()

        watchlist_response = self.client.post(
            "/api/watchlists",
            json={"user_id": user["id"], "name": "Core"},
        )
        self.assertEqual(watchlist_response.status_code, 201)
        watchlist = watchlist_response.get_json()
        self.assertEqual(watchlist["user_id"], user["id"])
        self.assertEqual(watchlist["name"], "Core")

    def test_get_watchlist_returns_latest_price_and_daily_change(self) -> None:
        user = self.repo.create_user("alice", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Core", now=self.t0)
        self.repo.add_stock(watchlist.id, "RELIANCE.NS", now=self.t0)

        response = self.client.get(f"/api/watchlists/{watchlist.id}")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        stock = payload["stocks"][0]
        self.assertEqual(stock["symbol"], "RELIANCE.NS")
        self.assertEqual(stock["sector"], "Energy")
        self.assertEqual(stock["latest_price"], 106.0)
        self.assertEqual(stock["latest_price_date"], "2026-09-04")
        self.assertEqual(stock["day_change"], 3.0)
        self.assertAlmostEqual(stock["day_change_percent"], 3.0 / 103.0, places=6)

    def test_stock_search_returns_catalog_results(self) -> None:
        response = self.client.get("/api/stocks/search?q=tata")
        self.assertEqual(response.status_code, 200)
        results = response.get_json()["results"]
        self.assertTrue(any(item["symbol"] == "TCS.NS" for item in results))

    def test_stock_search_by_sector(self) -> None:
        response = self.client.get("/api/stocks/search?sector=Banking")
        self.assertEqual(response.status_code, 200)
        results = response.get_json()["results"]
        self.assertTrue(any(item["symbol"] == "HDFCBANK.NS" for item in results))
        self.assertTrue(any(item["symbol"] == "SBIN.NS" for item in results))
        self.assertFalse(any(item["symbol"] == "TCS.NS" for item in results))

    def test_stock_search_by_alias_terms(self) -> None:
        response = self.client.get("/api/stocks/search?q=Pharma")
        self.assertEqual(response.status_code, 200)
        results = response.get_json()["results"]
        self.assertTrue(any(item["symbol"] == "SUNPHARMA.NS" for item in results))

    def test_groww_api_endpoints_return_financial_services(self) -> None:
        search_res = self.client.get("/api/stocks/search?q=groww")
        self.assertEqual(search_res.status_code, 200)
        results = search_res.get_json()["results"]
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["symbol"], "GROWW.NS")
        self.assertEqual(results[0]["sector"], "Financial Services")

        user = self.repo.create_user("groww_user", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Tech & Fin", now=self.t0)
        self.repo.add_stock(watchlist.id, "GROWW.NS", now=self.t0)

        wl_res = self.client.get(f"/api/watchlists/{watchlist.id}")
        self.assertEqual(wl_res.status_code, 200)
        stock_item = wl_res.get_json()["stocks"][0]
        self.assertEqual(stock_item["symbol"], "GROWW.NS")
        self.assertEqual(stock_item["sector"], "Financial Services")

        detail_res = self.client.get(f"/api/stocks/GROWW.NS/detail?watchlist_id={watchlist.id}")
        self.assertEqual(detail_res.status_code, 200)
        detail = detail_res.get_json()
        self.assertEqual(detail["sector"], "Financial Services")
        self.assertEqual(detail["sector_performance"]["sector"], "Financial Services")

    def test_stock_detail_endpoint(self) -> None:
        user = self.repo.create_user("alice", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Core", now=self.t0)
        self.repo.add_stock(watchlist.id, "RELIANCE.NS", now=self.t0)

        response = self.client.get(f"/api/stocks/RELIANCE.NS/detail?watchlist_id={watchlist.id}")
        self.assertEqual(response.status_code, 200)
        detail = response.get_json()
        self.assertEqual(detail["symbol"], "RELIANCE.NS")
        self.assertIn("volume_metrics", detail)
        self.assertIn("peers", detail)
        self.assertIn("sector_performance", detail)
        self.assertEqual(detail["sector_performance"]["sector"], "Energy")
        self.assertIn("news", detail)
        self.assertIn("why", detail)

    def test_header_and_detail_checkpoint_and_elapsed_matching(self) -> None:
        user = self.repo.create_user("alice", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Core", now=self.t0)
        self.repo.add_stock(watchlist.id, "RELIANCE.NS", now=self.t0)

        # Acknowledge watchlist to set user checkpoint
        self.repo.acknowledge_watchlist(watchlist.id)

        changes_res = self.client.get(f"/api/watchlists/{watchlist.id}/changes")
        detail_res = self.client.get(f"/api/stocks/RELIANCE.NS/detail?watchlist_id={watchlist.id}")

        self.assertEqual(changes_res.status_code, 200)
        self.assertEqual(detail_res.status_code, 200)

        changes_json = changes_res.get_json()
        detail_json = detail_res.get_json()

        self.assertEqual(changes_json["last_checked_at"], detail_json["checkpoint_at"])
        self.assertEqual(changes_json["elapsed_text"], detail_json["elapsed_text"])

    def test_header_and_detail_matching_with_simulated_preset(self) -> None:
        user = self.repo.create_user("alice", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Core", now=self.t0)
        self.repo.add_stock(watchlist.id, "RELIANCE.NS", now=self.t0)

        preset = "3d_ago"
        changes_res = self.client.get(f"/api/watchlists/{watchlist.id}/changes?simulated_checkpoint={preset}")
        detail_res = self.client.get(
            f"/api/stocks/RELIANCE.NS/detail?watchlist_id={watchlist.id}&simulated_checkpoint={preset}"
        )

        self.assertEqual(changes_res.status_code, 200)
        self.assertEqual(detail_res.status_code, 200)

        changes_json = changes_res.get_json()
        detail_json = detail_res.get_json()

        # Timestamps match to minute precision (accounting for microsecond execution gap)
        self.assertEqual(changes_json["last_checked_at"][:16], detail_json["checkpoint_at"][:16])
        self.assertEqual(changes_json["elapsed_text"], detail_json["elapsed_text"])
        self.assertEqual(changes_json["is_simulated"], True)
        self.assertEqual(detail_json["is_simulated"], True)


    def test_bootstrap_demo_creates_past_checkpoint_watchlist(self) -> None:
        response = self.client.post("/api/demo/bootstrap", json={})

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["user"]["username"], "demo-investor")
        self.assertEqual(payload["watchlist"]["name"], "What I Missed")
        self.assertGreaterEqual(len(payload["seeded_symbols"]), 4)
        first = self.repo.get_item_by_symbol(payload["watchlist"]["id"], "RELIANCE.NS")
        self.assertLess(first.checkpoint_at.date().isoformat(), "2026-09-04")

    def test_acknowledge_updates_checkpoints_only_on_request(self) -> None:
        user = self.repo.create_user("alice", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Core", now=self.t0)
        item = self.repo.add_stock(watchlist.id, "RELIANCE.NS", now=self.t0)

        before_get = self.client.get(f"/api/watchlists/{watchlist.id}/changes")
        self.assertEqual(before_get.status_code, 200)
        unchanged = self.repo.get_item(item.id)
        self.assertEqual(unchanged.checkpoint_at, self.t0)

        ack_response = self.client.post(
            f"/api/watchlists/{watchlist.id}/acknowledge",
            json={},
        )
        self.assertEqual(ack_response.status_code, 200)
        updated = self.repo.get_item(item.id)
        self.assertGreater(updated.checkpoint_at, self.t0)

    def test_validation_and_not_found_errors_are_json(self) -> None:
        bad_user = self.client.post("/api/users", json={})
        self.assertEqual(bad_user.status_code, 400)
        self.assertIn("error", bad_user.get_json())

        missing_watchlist = self.client.get("/api/watchlists/999")
        self.assertEqual(missing_watchlist.status_code, 404)
        self.assertIn("error", missing_watchlist.get_json())

    def test_cors_header_present(self) -> None:
        response = self.client.get("/api/watchlists/123")
        self.assertIn("Access-Control-Allow-Origin", response.headers)

    def test_threaded_http_request_uses_request_scoped_sqlite_connection(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as db_file:
            db_path = db_file.name

        app = create_app(
            db_path=db_path,
            market_data_service=self.market,
            change_detector=ChangeDetector(),
        )
        server = make_server("127.0.0.1", 0, app, threaded=True)
        host, port = server.server_address
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            payload = json.dumps({"username": "threaded-alice"}).encode("utf-8")
            request = urllib.request.Request(
                f"http://{host}:{port}/api/users",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertEqual(response.status, 201)
                body = json.loads(response.read().decode("utf-8"))
            self.assertEqual(body["username"], "threaded-alice")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
