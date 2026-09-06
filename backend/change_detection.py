"""Change-detection engine for stock moves versus NIFTY 50 and recent vol."""

from __future__ import annotations

import pandas as pd
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from typing import Literal
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc


Classification = Literal["NORMAL", "WORTH_WATCHING", "SIGNIFICANT"]

NORMAL: Classification = "NORMAL"
WORTH_WATCHING: Classification = "WORTH_WATCHING"
SIGNIFICANT: Classification = "SIGNIFICANT"

DateLike = str | date | datetime



@dataclass(frozen=True)
class ChangeDetectionConfig:
    """Transparent, tunable thresholds for MVP classification."""

    volatility_lookback_days: int = 30
    min_volatility_observations: int = 10
    worth_watching_relative: float = 0.015
    significant_relative: float = 0.03
    worth_watching_z: float = 1.5
    significant_z: float = 2.0


@dataclass(frozen=True)
class ChangeAssessment:
    """Structured change result for later UI / API use. Not display copy."""

    symbol: str
    classification: Classification
    last_checked: date
    user_checkpoint_at: str | None
    latest_market_timestamp: str | None
    is_market_open: bool
    checkpoint_after_latest_data: bool
    baseline_date: date | None
    latest_date: date | None
    nifty_baseline_date: date | None
    nifty_latest_date: date | None
    trading_days: int
    stock_return: float | None
    nifty_return: float | None
    relative_performance: float | None
    daily_volatility: float | None
    period_volatility: float | None
    unusualness_z: float | None
    volatility_observations: int
    insufficient_data: bool
    flags: tuple[str, ...]
    thresholds: dict[str, float] = field(default_factory=dict)



class ChangeDetector:
    """Score how meaningful a name's move is since the last checked trading point."""

    def __init__(self, config: ChangeDetectionConfig | None = None) -> None:
        self.config = config or ChangeDetectionConfig()

    def assess(
        self,
        stock: pd.DataFrame,
        nifty: pd.DataFrame,
        last_checked: DateLike,
        symbol: str = "",
        *,
        stock_intraday: pd.DataFrame | None = None,
        nifty_intraday: pd.DataFrame | None = None,
    ) -> ChangeAssessment:
        checked = _as_date(last_checked)
        checked_ts = _as_timestamp(last_checked)

        thresholds = {
            "volatility_lookback_days": float(self.config.volatility_lookback_days),
            "min_volatility_observations": float(self.config.min_volatility_observations),
            "worth_watching_relative": self.config.worth_watching_relative,
            "significant_relative": self.config.significant_relative,
            "worth_watching_z": self.config.worth_watching_z,
            "significant_z": self.config.significant_z,
        }

        user_checkpoint_str = _as_timestamp(last_checked).isoformat()

        stock_bars = _prepare_ohlcv(stock)
        nifty_bars = _prepare_ohlcv(nifty)

        stock_intra = _prepare_intraday(stock_intraday)
        nifty_intra = _prepare_intraday(nifty_intraday)

        flags: list[str] = []

        if stock_bars.empty and stock_intra.empty:
            return self._empty(
                symbol=symbol,
                checked=checked,
                user_checkpoint_at=user_checkpoint_str,
                flags=("MISSING_STOCK_DATA",),
                thresholds=thresholds,
            )

        use_intraday = False
        baseline_stock = None
        latest_stock = None

        if not stock_intra.empty:
            eligible_stock = stock_intra[stock_intra["timestamp"] <= checked_ts]
            if not eligible_stock.empty:
                use_intraday = True
                baseline_stock = eligible_stock.iloc[-1]
                latest_stock = stock_intra.iloc[-1]

        if not use_intraday:
            baseline_stock = _asof(stock_bars, checked)
            latest_stock = stock_bars.iloc[-1] if not stock_bars.empty else None

        if baseline_stock is None or latest_stock is None:
            return self._empty(
                symbol=symbol,
                checked=checked,
                user_checkpoint_at=user_checkpoint_str,
                flags=("LAST_CHECKED_BEFORE_HISTORY",),
                thresholds=thresholds,
                latest_date=_as_date(latest_stock["date"]) if latest_stock is not None and "date" in latest_stock else None,
            )

        baseline_date = _as_date(baseline_stock["date"] if "date" in baseline_stock else baseline_stock["timestamp"])
        latest_date = _as_date(latest_stock["date"] if "date" in latest_stock else latest_stock["timestamp"])
        trading_days = int((stock_bars["date"] > pd.Timestamp(baseline_date)).sum()) if not stock_bars.empty else 0

        latest_market_ts_val = None
        if use_intraday and latest_stock is not None and "timestamp" in latest_stock:
            latest_market_ts_val = pd.Timestamp(latest_stock["timestamp"]).isoformat()
        elif latest_stock is not None and "date" in latest_stock:
            d = _as_date(latest_stock["date"])
            dt_close = datetime.combine(d, time(15, 30), tzinfo=IST)
            latest_market_ts_val = dt_close.isoformat()

        checkpoint_after_latest_data = False
        if latest_market_ts_val and user_checkpoint_str:
            try:
                cp_dt_val = datetime.fromisoformat(user_checkpoint_str)
                mkt_dt_val = datetime.fromisoformat(latest_market_ts_val)
                if cp_dt_val >= mkt_dt_val:
                    checkpoint_after_latest_data = True
                    flags.append("CHECKPOINT_AFTER_LATEST_DATA")
            except Exception:
                pass

        stock_return = _pct_return(baseline_stock["close"], latest_stock["close"])
        if stock_return is None:
            flags.append("MISSING_STOCK_DATA")

        baseline_nifty = None
        latest_nifty = None

        if use_intraday and not nifty_intra.empty:
            eligible_nifty = nifty_intra[nifty_intra["timestamp"] <= checked_ts]
            if not eligible_nifty.empty:
                baseline_nifty = eligible_nifty.iloc[-1]
                latest_nifty = nifty_intra.iloc[-1]

        if baseline_nifty is None:
            baseline_nifty = _asof(nifty_bars, baseline_date)
            latest_nifty = nifty_bars.iloc[-1] if not nifty_bars.empty else None

        nifty_baseline_date = (
            _as_date(baseline_nifty["date"] if "date" in baseline_nifty else baseline_nifty["timestamp"])
            if baseline_nifty is not None
            else None
        )
        nifty_latest_date = (
            _as_date(latest_nifty["date"] if "date" in latest_nifty else latest_nifty["timestamp"])
            if latest_nifty is not None
            else None
        )

        nifty_return = None
        if baseline_nifty is None or latest_nifty is None:
            flags.append("MISSING_NIFTY_DATA")
        else:
            nifty_return = _pct_return(baseline_nifty["close"], latest_nifty["close"])
            if nifty_return is None:
                flags.append("MISSING_NIFTY_DATA")

        relative = None
        if stock_return is not None and nifty_return is not None:
            relative = stock_return - nifty_return

        MAX_TIMESTAMP_MISMATCH_SECONDS = 1800  # 30 minutes tolerance for 5m intraday bars
        if use_intraday:
            if baseline_nifty is not None and "timestamp" in baseline_stock and "timestamp" in baseline_nifty and latest_nifty is not None and "timestamp" in latest_nifty:
                base_stock_ts = pd.Timestamp(baseline_stock["timestamp"])
                base_nifty_ts = pd.Timestamp(baseline_nifty["timestamp"])
                late_stock_ts = pd.Timestamp(latest_stock["timestamp"])
                late_nifty_ts = pd.Timestamp(latest_nifty["timestamp"])

                base_skew = abs((base_stock_ts - base_nifty_ts).total_seconds())
                late_skew = abs((late_stock_ts - late_nifty_ts).total_seconds())

                if base_skew > MAX_TIMESTAMP_MISMATCH_SECONDS or late_skew > MAX_TIMESTAMP_MISMATCH_SECONDS:
                    flags.append("NIFTY_TIMESTAMP_MISMATCH")
                    relative = None  # Do not report precise relative performance if timestamps are materially misaligned
            elif not nifty_intra.empty:
                flags.append("NIFTY_TIMESTAMP_MISMATCH")
                relative = None

        daily_vol, vol_obs = self._daily_volatility(stock_bars, baseline_date)
        period_vol = None
        unusualness_z = None
        if daily_vol is None:
            flags.append("INSUFFICIENT_VOLATILITY_HISTORY")
        else:
            eff_days = max(trading_days, 1 if use_intraday else 0)
            if eff_days > 0:
                period_vol = daily_vol * (eff_days**0.5)
                if period_vol > 0 and stock_return is not None:
                    unusualness_z = stock_return / period_vol

        if use_intraday:
            base_ts = pd.Timestamp(baseline_stock["timestamp"])
            late_ts = pd.Timestamp(latest_stock["timestamp"])
            if late_ts <= base_ts or (stock_return == 0.0 and (nifty_return == 0.0 or nifty_return is None)):
                flags.append("NO_NEW_TRADING_SESSION")
        elif trading_days == 0:
            flags.append("NO_NEW_TRADING_SESSION")

        insufficient = (
            stock_return is None
            or relative is None
            or "MISSING_STOCK_DATA" in flags
            or "MISSING_NIFTY_DATA" in flags
            or "LAST_CHECKED_BEFORE_HISTORY" in flags
        )
        classification = self._classify(
            relative_performance=relative,
            unusualness_z=unusualness_z,
            trading_days=trading_days if not use_intraday else 1,
            insufficient=insufficient,
            is_no_move="NO_NEW_TRADING_SESSION" in flags and stock_return == 0.0,
        )

        return ChangeAssessment(
            symbol=symbol,
            classification=classification,
            last_checked=checked,
            user_checkpoint_at=user_checkpoint_str,
            latest_market_timestamp=latest_market_ts_val,
            is_market_open=False,  # Updated by caller/API with live market status
            checkpoint_after_latest_data=checkpoint_after_latest_data,
            baseline_date=baseline_date,
            latest_date=latest_date,
            nifty_baseline_date=nifty_baseline_date,
            nifty_latest_date=nifty_latest_date,
            trading_days=trading_days,
            stock_return=stock_return,
            nifty_return=nifty_return,
            relative_performance=relative,
            daily_volatility=daily_vol,
            period_volatility=period_vol,
            unusualness_z=unusualness_z,
            volatility_observations=vol_obs,
            insufficient_data=insufficient,
            flags=tuple(flags),
            thresholds=thresholds,
        )

    def _daily_volatility(
        self,
        stock_bars: pd.DataFrame,
        baseline_date: date,
    ) -> tuple[float | None, int]:
        if stock_bars.empty:
            return None, 0
        window = stock_bars[stock_bars["date"] <= pd.Timestamp(baseline_date)]
        window = window.tail(self.config.volatility_lookback_days + 1)
        returns = window["close"].pct_change().replace([float("inf"), float("-inf")], pd.NA).dropna()
        n = int(len(returns))
        if n < self.config.min_volatility_observations:
            return None, n
        std = float(returns.std(ddof=1))
        if not pd.notna(std) or std <= 0:
            return None, n
        return std, n

    def _classify(
        self,
        *,
        relative_performance: float | None,
        unusualness_z: float | None,
        trading_days: int,
        insufficient: bool,
        is_no_move: bool = False,
    ) -> Classification:
        if insufficient or is_no_move or relative_performance is None:
            return NORMAL

        abs_rel = abs(relative_performance)
        abs_z = abs(unusualness_z) if unusualness_z is not None else None
        cfg = self.config

        if abs_rel >= cfg.significant_relative and abs_z is not None and abs_z >= cfg.significant_z:
            return SIGNIFICANT

        if abs_rel >= cfg.worth_watching_relative:
            return WORTH_WATCHING
        if (
            abs_z is not None
            and abs_z >= cfg.worth_watching_z
            and abs_rel >= cfg.worth_watching_relative / 2
        ):
            return WORTH_WATCHING
        return NORMAL

    def _empty(
        self,
        *,
        symbol: str,
        checked: date,
        user_checkpoint_at: str | None = None,
        flags: tuple[str, ...],
        thresholds: dict[str, float],
        latest_date: date | None = None,
    ) -> ChangeAssessment:
        return ChangeAssessment(
            symbol=symbol,
            classification=NORMAL,
            last_checked=checked,
            user_checkpoint_at=user_checkpoint_at,
            latest_market_timestamp=None,
            is_market_open=False,
            checkpoint_after_latest_data=False,
            baseline_date=None,
            latest_date=latest_date,
            nifty_baseline_date=None,
            nifty_latest_date=None,
            trading_days=0,
            stock_return=None,
            nifty_return=None,
            relative_performance=None,
            daily_volatility=None,
            period_volatility=None,
            unusualness_z=None,
            volatility_observations=0,
            insufficient_data=True,
            flags=flags,
            thresholds=thresholds,
        )



def _prepare_ohlcv(frame: pd.DataFrame | None) -> pd.DataFrame:
    empty = pd.DataFrame(columns=["date", "close"])
    if frame is None or frame.empty:
        return empty
    if "date" not in frame.columns or "close" not in frame.columns:
        return empty
    out = frame.loc[:, ["date", "close"]].copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.normalize()
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["date", "close"])
    out = out.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    return out.reset_index(drop=True)


def _prepare_intraday(frame: pd.DataFrame | None) -> pd.DataFrame:
    empty = pd.DataFrame(columns=["timestamp", "close"])
    if frame is None or frame.empty:
        return empty
    if "timestamp" not in frame.columns or "close" not in frame.columns:
        return empty
    out = frame.loc[:, ["timestamp", "close"]].copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="coerce")
    out["close"] = pd.to_numeric(out["close"], errors="coerce")
    out = out.dropna(subset=["timestamp", "close"])
    out = out.sort_values("timestamp")
    return out.reset_index(drop=True)


def _asof(bars: pd.DataFrame, on_or_before: DateLike) -> pd.Series | None:
    if bars.empty:
        return None
    cutoff = pd.Timestamp(_as_date(on_or_before))
    eligible = bars[bars["date"] <= cutoff]
    if eligible.empty:
        return None
    return eligible.iloc[-1]


def _pct_return(start_close: object, end_close: object) -> float | None:
    start = pd.to_numeric(start_close, errors="coerce")
    end = pd.to_numeric(end_close, errors="coerce")
    if pd.isna(start) or pd.isna(end) or start == 0:
        return None
    return float(end / start - 1.0)


def _as_date(value: DateLike | pd.Timestamp) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("Asia/Kolkata").tz_localize(None)
    return ts.date()


def _as_timestamp(value: DateLike | pd.Timestamp) -> pd.Timestamp:
    if isinstance(value, datetime):
        ts = pd.Timestamp(value)
        if ts.tzinfo is None:
            return ts.tz_localize("UTC")
        return ts.tz_convert("UTC")
    if isinstance(value, date) and not isinstance(value, datetime):
        dt = datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)
        return pd.Timestamp(dt)
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")
