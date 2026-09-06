"""Unit tests for user checkpoint vs market data timestamp handling & market hours."""

from __future__ import annotations

import unittest
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from change_detection import ChangeDetector
from market_data import MarketDataService, get_market_status

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


def _make_daily_ohlcv(dates: list[date], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1_000_000] * len(closes),
        }
    )


def _make_intraday_ohlcv(timestamps: list[datetime], closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(timestamps),
            "date": [ts.date() for ts in timestamps],
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [100_000] * len(closes),
        }
    )


class MarketTimestampTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = ChangeDetector()
        self.dates = [
            date(2026, 8, 31),
            date(2026, 9, 1),
            date(2026, 9, 2),
            date(2026, 9, 3),
            date(2026, 9, 4),  # Friday
        ]
        self.stock_daily = _make_daily_ohlcv(self.dates, [100.0, 101.0, 102.0, 103.0, 105.0])
        self.nifty_daily = _make_daily_ohlcv(self.dates, [20000.0, 20050.0, 20100.0, 20150.0, 20200.0])

    def test_market_status_during_trading_hours(self) -> None:
        # Wednesday 2 Sept 2026 at 11:30 AM IST
        wed_1130 = datetime(2026, 9, 2, 11, 30, tzinfo=IST)
        status = get_market_status(wed_1130)
        self.assertTrue(status["is_open"])
        self.assertEqual(status["status_code"], "OPEN")
        self.assertEqual(status["latest_session_date"], date(2026, 9, 2))

    def test_market_status_after_hours(self) -> None:
        # Wednesday 2 Sept 2026 at 6:00 PM IST
        wed_1800 = datetime(2026, 9, 2, 18, 0, tzinfo=IST)
        status = get_market_status(wed_1800)
        self.assertFalse(status["is_open"])
        self.assertEqual(status["status_code"], "AFTER_HOURS")
        self.assertEqual(status["latest_session_date"], date(2026, 9, 2))

    def test_market_status_saturday(self) -> None:
        # Saturday 5 Sept 2026 at 5:30 PM IST
        sat_1730 = datetime(2026, 9, 5, 17, 30, tzinfo=IST)
        status = get_market_status(sat_1730)
        self.assertFalse(status["is_open"])
        self.assertEqual(status["status_code"], "CLOSED")
        self.assertEqual(status["latest_session_date"], date(2026, 9, 4))

    def test_market_status_sunday(self) -> None:
        # Sunday 6 Sept 2026 at 10:00 AM IST
        sun_1000 = datetime(2026, 9, 6, 10, 0, tzinfo=IST)
        status = get_market_status(sun_1000)
        self.assertFalse(status["is_open"])
        self.assertEqual(status["status_code"], "CLOSED")
        self.assertEqual(status["latest_session_date"], date(2026, 9, 4))

    def test_market_status_monday_before_open(self) -> None:
        # Monday 7 Sept 2026 at 8:00 AM IST
        mon_0800 = datetime(2026, 9, 7, 8, 0, tzinfo=IST)
        status = get_market_status(mon_0800)
        self.assertFalse(status["is_open"])
        self.assertEqual(status["status_code"], "CLOSED")
        self.assertEqual(status["latest_session_date"], date(2026, 9, 4))

    def test_checkpoint_on_saturday_after_friday_close(self) -> None:
        # User checked on Saturday 5 Sept at 17:30 IST. Latest market date is Friday 4 Sept.
        checkpoint = datetime(2026, 9, 5, 17, 30, tzinfo=IST)
        assessment = self.detector.assess(
            self.stock_daily,
            self.nifty_daily,
            checkpoint,
            symbol="RELIANCE.NS",
        )
        self.assertIn("CHECKPOINT_AFTER_LATEST_DATA", assessment.flags)
        self.assertTrue(assessment.checkpoint_after_latest_data)
        self.assertIsNotNone(assessment.user_checkpoint_at)
        self.assertIsNotNone(assessment.latest_market_timestamp)
        # Checkpoint ISO string must contain 2026-09-05
        self.assertIn("2026-09-05", assessment.user_checkpoint_at)

    def test_checkpoint_newer_than_latest_market_data(self) -> None:
        # User checkpoint is Sunday 6 Sept, latest market data is 4 Sept close
        checkpoint = datetime(2026, 9, 6, 12, 0, tzinfo=IST)
        assessment = self.detector.assess(
            self.stock_daily,
            self.nifty_daily,
            checkpoint,
            symbol="TCS.NS",
        )
        self.assertTrue(assessment.checkpoint_after_latest_data)
        self.assertIn("NO_NEW_TRADING_SESSION", assessment.flags)

    def test_checkpoint_older_than_latest_market_data(self) -> None:
        # User checkpoint is Tuesday 1 Sept, latest market data is Friday 4 Sept
        checkpoint = datetime(2026, 9, 1, 10, 0, tzinfo=IST)
        assessment = self.detector.assess(
            self.stock_daily,
            self.nifty_daily,
            checkpoint,
            symbol="INFY.NS",
        )
        self.assertFalse(assessment.checkpoint_after_latest_data)
        self.assertEqual(assessment.trading_days, 3)
        self.assertIsNotNone(assessment.stock_return)
        self.assertGreater(assessment.stock_return, 0.0)

    def test_intraday_data_during_market_hours(self) -> None:
        # Wednesday 2 Sept during market hours (09:30 IST to 14:00 IST)
        ts_list = [
            datetime(2026, 9, 2, 9, 30, tzinfo=IST),
            datetime(2026, 9, 2, 11, 0, tzinfo=IST),
            datetime(2026, 9, 2, 14, 0, tzinfo=IST),
        ]
        intra_stock = _make_intraday_ohlcv(ts_list, [100.0, 102.0, 105.0])
        intra_nifty = _make_intraday_ohlcv(ts_list, [20000.0, 20050.0, 20100.0])

        checkpoint = datetime(2026, 9, 2, 9, 30, tzinfo=IST)
        assessment = self.detector.assess(
            self.stock_daily,
            self.nifty_daily,
            checkpoint,
            symbol="RELIANCE.NS",
            stock_intraday=intra_stock,
            nifty_intraday=intra_nifty,
        )
        self.assertIsNotNone(assessment.stock_return)
        self.assertAlmostEqual(assessment.stock_return, 0.05, places=4)

    def test_last_checked_differs_from_latest_market_data_on_weekend(self) -> None:
        # Weekend checkpoint: Sunday 6 Sept 2026 at 10:00 AM IST
        sun_checkpoint = datetime(2026, 9, 6, 10, 0, tzinfo=IST)
        assessment = self.detector.assess(
            self.stock_daily,
            self.nifty_daily,
            sun_checkpoint,
            symbol="RELIANCE.NS",
        )
        self.assertIsNotNone(assessment.user_checkpoint_at)
        self.assertIsNotNone(assessment.latest_market_timestamp)
        # Checkpoint is 6 Sept, latest market data is 4 Sept close
        self.assertNotEqual(assessment.user_checkpoint_at[:10], assessment.latest_market_timestamp[:10])
        self.assertIn("2026-09-06", assessment.user_checkpoint_at)
        self.assertIn("2026-09-04", assessment.latest_market_timestamp)


if __name__ == "__main__":
    unittest.main()
