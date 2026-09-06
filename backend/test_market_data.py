"""Fetch last 5 trading days of daily OHLCV for RELIANCE.NS and ^NSEI."""

from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from market_data import MarketDataService, OHLCV_COLUMNS, _configure_yfinance_cache

TICKERS = ["RELIANCE.NS", "^NSEI"]
PERIOD = "5d"


class MarketDataConfigTests(unittest.TestCase):
    def test_configure_yfinance_cache_uses_writable_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_dir = Path(temp_dir) / "cache"
            with patch("market_data.YFINANCE_CACHE_DIR", cache_dir):
                with patch("market_data.yf.set_tz_cache_location") as set_cache:
                    _configure_yfinance_cache()

            self.assertTrue(cache_dir.exists())
            self.assertTrue(cache_dir.is_dir())
            set_cache.assert_called_once_with(str(cache_dir))

    def test_normalize_drops_rows_without_close(self) -> None:
        raw = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [100.5, float("nan")],
                "Volume": [1000, 1100],
            },
            index=pd.to_datetime(["2026-09-03", "2026-09-04"]),
        )

        normalized = MarketDataService._normalize(raw)

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized.iloc[0]["date"].date().isoformat(), "2026-09-03")
        self.assertEqual(float(normalized.iloc[0]["close"]), 100.5)

    def test_normalize_intraday_formats_timestamps_and_dates(self) -> None:
        raw = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [100.5, 101.5],
                "Volume": [1000, 1100],
            },
            index=pd.to_datetime(["2026-09-04 09:15:00", "2026-09-04 09:20:00"]),
        )

        normalized = MarketDataService._normalize_intraday(raw)

        self.assertEqual(len(normalized), 2)
        self.assertIn("timestamp", normalized.columns)
        self.assertIn("date", normalized.columns)
        self.assertEqual(str(normalized.iloc[0]["date"]), "2026-09-04")

    def test_search_catalog_finds_matches_by_company_and_partial_name(self) -> None:
        service = MarketDataService()
        tata_results = service.search_catalog("Tata")
        self.assertTrue(any(r["symbol"] == "TCS.NS" for r in tata_results))
        self.assertTrue(any(r["symbol"] == "TATAMOTORS.NS" for r in tata_results))
        self.assertTrue(any(r["symbol"] == "TATASTEEL.NS" for r in tata_results))

        infosys_results = service.search_catalog("Infosys")
        self.assertTrue(any(r["symbol"] == "INFY.NS" for r in infosys_results))

        sun_results = service.search_catalog("Sun")
        self.assertTrue(any(r["symbol"] == "SUNPHARMA.NS" for r in sun_results))

    def test_search_catalog_finds_matches_by_ticker(self) -> None:
        service = MarketDataService()
        infy_results = service.search_catalog("INFY")
        self.assertTrue(any(r["symbol"] == "INFY.NS" for r in infy_results))

        sbin_results = service.search_catalog("SBIN.NS")
        self.assertTrue(any(r["symbol"] == "SBIN.NS" for r in sbin_results))

    def test_search_catalog_filters_by_sector_and_alias_terms(self) -> None:
        service = MarketDataService()
        # Test sector pill filters
        tech_results = service.search_catalog(sector="Technology")
        self.assertTrue(any(r["symbol"] == "TCS.NS" for r in tech_results))
        self.assertTrue(any(r["symbol"] == "INFY.NS" for r in tech_results))
        self.assertFalse(any(r["symbol"] == "HDFCBANK.NS" for r in tech_results))

        pharma_results = service.search_catalog(sector="Pharma")
        self.assertTrue(any(r["symbol"] == "SUNPHARMA.NS" for r in pharma_results))
        self.assertTrue(any(r["symbol"] == "CIPLA.NS" for r in pharma_results))

        # Test common sector alias search queries
        it_results = service.search_catalog("IT")
        self.assertTrue(any(r["symbol"] == "TCS.NS" for r in it_results))

        auto_results = service.search_catalog("Auto")
        self.assertTrue(any(r["symbol"] == "TATAMOTORS.NS" for r in auto_results))
        self.assertTrue(any(r["symbol"] == "MARUTI.NS" for r in auto_results))

        finance_results = service.search_catalog("Finance")
        self.assertTrue(any(r["symbol"] == "HDFCBANK.NS" for r in finance_results))
        self.assertTrue(any(r["symbol"] == "BAJFINANCE.NS" for r in finance_results))

    def test_search_catalog_returns_accurate_metadata(self) -> None:
        service = MarketDataService()
        results = service.search_catalog("Reliance")
        self.assertGreater(len(results), 0)
        item = results[0]
        self.assertEqual(item["symbol"], "RELIANCE.NS")
        self.assertEqual(item["display_name"], "Reliance Industries")
        self.assertEqual(item["sector"], "Energy")

    def test_fetch_sector_peers_returns_curated_peers(self) -> None:
        service = MarketDataService()
        peers = service.fetch_sector_peers("TCS.NS")
        peer_symbols = [p["symbol"] for p in peers]
        self.assertIn("INFY.NS", peer_symbols)
        self.assertNotIn("TCS.NS", peer_symbols)

    def test_fetch_sector_performance_returns_sector_metrics_and_takeaway(self) -> None:
        service = MarketDataService()
        perf = service.fetch_sector_performance("TCS.NS")
        self.assertEqual(perf["sector"], "Technology")
        self.assertIn("sector_change_percent", perf)
        self.assertIn("stock_change_percent", perf)
        self.assertIn("takeaway", perf)
        self.assertIsInstance(perf["peers"], list)
        if perf["takeaway"]:
            self.assertIn("TCS", perf["takeaway"])
            self.assertIn("Technology sector", perf["takeaway"])

    def test_fetch_sector_performance_unknown_symbol_returns_fallback(self) -> None:
        service = MarketDataService()
        perf = service.fetch_sector_performance("UNKNOWN.NS")
        self.assertEqual(perf["sector"], "Other")
        self.assertIsNone(perf["sector_change_percent"])
        self.assertIsNone(perf["takeaway"])

    def test_groww_sector_is_financial_services(self) -> None:
        from market_data import get_stock_sector
        self.assertEqual(get_stock_sector("GROWW.NS"), "Financial Services")
        self.assertEqual(get_stock_sector("GROWW"), "Financial Services")

        service = MarketDataService()
        groww_search = service.search_catalog("Groww")
        self.assertTrue(len(groww_search) > 0)
        self.assertEqual(groww_search[0]["sector"], "Financial Services")

        peers = service.fetch_sector_peers("GROWW.NS")
        self.assertTrue(len(peers) > 0)
        self.assertEqual(peers[0]["sector"], "Financial Services")

        perf = service.fetch_sector_performance("GROWW.NS")
        self.assertEqual(perf["sector"], "Financial Services")

    def test_all_catalog_stocks_have_non_other_sectors(self) -> None:
        from market_data import STOCK_CATALOG
        for item in STOCK_CATALOG:
            self.assertNotEqual(item["sector"], "Other", f"Stock {item['symbol']} has generic 'Other' sector")
            self.assertTrue(len(item["sector"].strip()) > 0, f"Stock {item['symbol']} has empty sector")




def print_result(symbol: str, data: pd.DataFrame) -> None:
    print("=" * 72)
    print(f"SYMBOL: {symbol}")
    print(f"ROWS:   {len(data)}")
    print(f"COLS:   {list(data.columns)}")
    print("-" * 72)
    with pd.option_context("display.max_columns", None, "display.width", 120):
        print(data)
    print()


def main() -> None:
    service = MarketDataService()
    results: dict[str, pd.DataFrame] = {}

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for symbol in TICKERS:
            if symbol == "^NSEI":
                results[symbol] = service.fetch_nifty50(period=PERIOD)
            else:
                results[symbol] = service.fetch_daily_ohlcv(symbol, period=PERIOD)
        captured_warnings = list(caught)

    for symbol in TICKERS:
        data = results[symbol]
        if data.empty or list(data.columns) != OHLCV_COLUMNS:
            print("=" * 72)
            print(f"SYMBOL: {symbol}")
            print("STATUS: FAILED (empty or unexpected columns)")
            print()
        else:
            print_result(symbol, data)

    print("=" * 72)
    print("SUMMARY")
    for symbol in TICKERS:
        data = results[symbol]
        ok = not data.empty and list(data.columns) == OHLCV_COLUMNS
        print(f"  {symbol}: {'OK' if ok else 'FAILED'}")

    if captured_warnings:
        print("-" * 72)
        print("WARNINGS")
        for warning in captured_warnings:
            print(f"  {warning.category.__name__}: {warning.message}")
    else:
        print("  No Python warnings captured.")
    print("=" * 72)


if __name__ == "__main__":
    main()
