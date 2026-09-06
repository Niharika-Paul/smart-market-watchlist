"""Deterministic unit tests for the change-detection engine."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

import pandas as pd

from change_detection import NORMAL, SIGNIFICANT, ChangeDetector
from market_data import OHLCV_COLUMNS


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


def _weekdays(start: date, count: int, holidays: set[date] | None = None) -> list[date]:
    skip = holidays or set()
    current = start
    out: list[date] = []
    while len(out) < count:
        if current.weekday() < 5 and current not in skip:
            out.append(current)
        current += timedelta(days=1)
    return out


def _flat_then_move(
    *,
    start: date,
    history_days: int,
    base_price: float,
    move: float,
    wobble: float,
) -> tuple[list[date], list[float]]:
    dates = _weekdays(start, history_days + 1)
    closes = []
    for i in range(history_days):
        bump = wobble if i % 2 == 0 else -wobble
        closes.append(base_price * (1.0 + bump))
    closes.append(closes[-1] * (1.0 + move))
    return dates, closes


class ChangeDetectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.detector = ChangeDetector()

    def test_normal_movement(self) -> None:
        dates, stock_closes = _flat_then_move(
            start=date(2026, 6, 1),
            history_days=35,
            base_price=100.0,
            move=0.004,
            wobble=0.01,
        )
        nifty_closes = [20_000.0 * (c / stock_closes[0]) for c in stock_closes]
        # Keep nifty nearly in lockstep with a tiny extra wiggle so relative stays small.
        nifty_closes = [close * 1.001 for close in nifty_closes]
        stock = _ohlcv(dates, stock_closes)
        nifty = _ohlcv(dates, nifty_closes)
        last_checked = dates[-2]

        result = self.detector.assess(stock, nifty, last_checked, symbol="RELIANCE.NS")

        self.assertEqual(result.classification, NORMAL)
        self.assertFalse(result.insufficient_data)
        self.assertEqual(result.trading_days, 1)
        self.assertIsNotNone(result.stock_return)
        self.assertLess(abs(result.stock_return or 0), 0.01)
        self.assertLess(abs(result.relative_performance or 0), 0.01)

    def test_significant_stock_move_nifty_flat(self) -> None:
        dates, stock_closes = _flat_then_move(
            start=date(2026, 6, 1),
            history_days=35,
            base_price=100.0,
            move=0.06,
            wobble=0.002,
        )
        nifty_closes = [20_000.0] * len(dates)
        stock = _ohlcv(dates, stock_closes)
        nifty = _ohlcv(dates, nifty_closes)
        last_checked = dates[-2]

        result = self.detector.assess(stock, nifty, last_checked, symbol="RELIANCE.NS")

        self.assertEqual(result.classification, SIGNIFICANT)
        self.assertAlmostEqual(result.stock_return or 0, 0.06, places=4)
        self.assertAlmostEqual(result.nifty_return or 0, 0.0, places=6)
        self.assertAlmostEqual(result.relative_performance or 0, 0.06, places=4)
        self.assertGreater(abs(result.unusualness_z or 0), 2.0)

    def test_stock_moving_with_the_market(self) -> None:
        dates, stock_closes = _flat_then_move(
            start=date(2026, 6, 1),
            history_days=35,
            base_price=100.0,
            move=0.06,
            wobble=0.002,
        )
        nifty_closes = [20_000.0] * 35 + [20_000.0 * 1.06]
        stock = _ohlcv(dates, stock_closes)
        nifty = _ohlcv(dates, nifty_closes)
        last_checked = dates[-2]

        result = self.detector.assess(stock, nifty, last_checked, symbol="RELIANCE.NS")

        self.assertEqual(result.classification, NORMAL)
        self.assertAlmostEqual(result.stock_return or 0, 0.06, places=4)
        self.assertAlmostEqual(result.nifty_return or 0, 0.06, places=4)
        self.assertAlmostEqual(result.relative_performance or 0, 0.0, places=4)

    def test_missing_data(self) -> None:
        dates, stock_closes = _flat_then_move(
            start=date(2026, 6, 1),
            history_days=35,
            base_price=100.0,
            move=0.06,
            wobble=0.002,
        )
        stock = _ohlcv(dates, stock_closes)
        last_checked = dates[-2]

        empty = _ohlcv([], [])
        no_stock = self.detector.assess(empty, stock, last_checked, symbol="RELIANCE.NS")
        self.assertEqual(no_stock.classification, NORMAL)
        self.assertTrue(no_stock.insufficient_data)
        self.assertIn("MISSING_STOCK_DATA", no_stock.flags)

        no_nifty = self.detector.assess(stock, empty, last_checked, symbol="RELIANCE.NS")
        self.assertEqual(no_nifty.classification, NORMAL)
        self.assertTrue(no_nifty.insufficient_data)
        self.assertIn("MISSING_NIFTY_DATA", no_nifty.flags)
        self.assertIsNone(no_nifty.relative_performance)

        broken = stock.copy()
        broken.loc[broken.index[-1], "close"] = float("nan")
        nan_close = self.detector.assess(broken, _ohlcv(dates, [20_000.0] * len(dates)), last_checked)
        self.assertEqual(nan_close.classification, NORMAL)
        self.assertIn("NO_NEW_TRADING_SESSION", nan_close.flags)

        too_early = self.detector.assess(
            stock,
            _ohlcv(dates, [20_000.0] * len(dates)),
            date(2020, 1, 1),
        )
        self.assertEqual(too_early.classification, NORMAL)
        self.assertIn("LAST_CHECKED_BEFORE_HISTORY", too_early.flags)

    def test_weekend_and_holiday_gap(self) -> None:
        holiday = date(2026, 8, 19)
        dates = _weekdays(date(2026, 6, 29), 40, holidays={holiday})
        self.assertNotIn(holiday, dates)
        self.assertNotIn(date(2026, 8, 15), dates)  # Saturday in this span; sanity on weekdays-only

        closes = []
        price = 100.0
        for i in range(len(dates) - 1):
            bump = 0.002 if i % 2 == 0 else -0.002
            price = 100.0 * (1.0 + bump)
            closes.append(price)
        closes.append(closes[-1] * 1.01)
        nifty_closes = [20_000.0] * len(dates)

        stock = _ohlcv(dates, closes)
        nifty = _ohlcv(dates, nifty_closes)

        friday = date(2026, 8, 14)
        saturday = date(2026, 8, 15)
        sunday = date(2026, 8, 16)
        self.assertIn(friday, dates)
        self.assertEqual(dates[dates.index(friday) + 1], date(2026, 8, 17))

        sat_result = self.detector.assess(stock, nifty, saturday, symbol="RELIANCE.NS")
        sun_result = self.detector.assess(stock, nifty, sunday, symbol="RELIANCE.NS")
        fri_result = self.detector.assess(stock, nifty, friday, symbol="RELIANCE.NS")

        self.assertEqual(sat_result.baseline_date, friday)
        self.assertEqual(sun_result.baseline_date, friday)
        self.assertEqual(fri_result.baseline_date, friday)
        self.assertGreater(sat_result.trading_days, 0)

        # Last-checked on a market holiday should snap to the prior session.
        self.assertIn(date(2026, 8, 18), dates)
        self.assertEqual(dates[dates.index(date(2026, 8, 18)) + 1], date(2026, 8, 20))
        holiday_result = self.detector.assess(stock, nifty, holiday, symbol="RELIANCE.NS")
        self.assertEqual(holiday_result.baseline_date, date(2026, 8, 18))
        self.assertNotEqual(holiday_result.baseline_date, holiday)

    def test_intraday_same_day_checkpoint(self) -> None:
        dates, stock_closes = _flat_then_move(
            start=date(2026, 6, 1),
            history_days=35,
            base_price=100.0,
            move=0.01,
            wobble=0.002,
        )
        stock_daily = _ohlcv(dates, stock_closes)
        nifty_daily = _ohlcv(dates, [20_000.0] * len(dates))

        timestamps = [
            pd.Timestamp("2026-09-04 09:15:00+00:00"),
            pd.Timestamp("2026-09-04 09:20:00+00:00"),
            pd.Timestamp("2026-09-04 09:25:00+00:00"),
            pd.Timestamp("2026-09-04 09:30:00+00:00"),
        ]
        stock_intra = pd.DataFrame(
            {
                "timestamp": timestamps,
                "close": [100.0, 100.0, 103.0, 105.0],
            }
        )
        nifty_intra = pd.DataFrame(
            {
                "timestamp": timestamps,
                "close": [20000.0, 20000.0, 20000.0, 20000.0],
            }
        )

        checkpoint_ts = pd.Timestamp("2026-09-04 09:20:00+00:00")
        result = self.detector.assess(
            stock_daily,
            nifty_daily,
            checkpoint_ts,
            symbol="RELIANCE.NS",
            stock_intraday=stock_intra,
            nifty_intraday=nifty_intra,
        )

        self.assertFalse(result.insufficient_data)
        self.assertAlmostEqual(result.stock_return or 0, 0.05, places=4)
        self.assertAlmostEqual(result.relative_performance or 0, 0.05, places=4)

    def test_nifty_timestamp_mismatch_flags_and_nullifies_relative(self) -> None:
        dates, stock_closes = _flat_then_move(
            start=date(2026, 6, 1),
            history_days=35,
            base_price=100.0,
            move=0.01,
            wobble=0.002,
        )
        stock_daily = _ohlcv(dates, stock_closes)
        nifty_daily = _ohlcv(dates, [20_000.0] * len(dates))

        stock_timestamps = [
            pd.Timestamp("2026-09-04 09:15:00+00:00"),
            pd.Timestamp("2026-09-04 09:20:00+00:00"),
        ]
        nifty_timestamps = [
            pd.Timestamp("2026-09-04 11:15:00+00:00"),
            pd.Timestamp("2026-09-04 11:20:00+00:00"),
        ]
        stock_intra = pd.DataFrame(
            {"timestamp": stock_timestamps, "close": [100.0, 105.0]}
        )
        nifty_intra = pd.DataFrame(
            {"timestamp": nifty_timestamps, "close": [20000.0, 20000.0]}
        )

        checkpoint_ts = pd.Timestamp("2026-09-04 09:15:00+00:00")
        result = self.detector.assess(
            stock_daily,
            nifty_daily,
            checkpoint_ts,
            symbol="RELIANCE.NS",
            stock_intraday=stock_intra,
            nifty_intraday=nifty_intra,
        )

        self.assertIn("NIFTY_TIMESTAMP_MISMATCH", result.flags)
        self.assertIsNone(result.relative_performance)
        self.assertAlmostEqual(result.stock_return or 0, 0.05, places=4)



if __name__ == "__main__":
    unittest.main()
