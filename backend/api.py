"""Flask API layer for watchlist CRUD and change detection."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from sqlite3 import Connection
from typing import Any

import pandas as pd
from flask import Flask, g, jsonify, request
from flask_cors import CORS

from change_detection import ChangeAssessment, ChangeDetector
from database import connect
from market_data import STOCK_CATALOG, MarketDataService, get_market_status, get_stock_sector
from repository import DuplicateError, NotFoundError, WatchlistItem, WatchlistRepository


DEMO_USERNAME = "demo-investor"
DEMO_WATCHLIST_NAME = "What I Missed"
DEMO_SYMBOLS = ["RELIANCE.NS", "INFY.NS", "TCS.NS", "HDFCBANK.NS"]
HISTORY_PERIOD = "1mo"
DISPLAY_NAMES = {
    "RELIANCE.NS": "Reliance Industries",
    "INFY.NS": "Infosys",
    "TCS.NS": "TCS",
    "HDFCBANK.NS": "HDFC Bank",
    "SBIN.NS": "State Bank of India",
    "TATAMOTORS.NS": "Tata Motors",
    "TATASTEEL.NS": "Tata Steel",
    "ICICIBANK.NS": "ICICI Bank",
    "WIPRO.NS": "Wipro",
    "BHARTIARTL.NS": "Bharti Airtel",
    "MARUTI.NS": "Maruti Suzuki",
    "LT.NS": "Larsen & Toubro",
    "GROWW.NS": "Groww",
}



def create_app(
    *,
    db_path: str | Path = "watchlist.db",
    conn: Connection | None = None,
    repository: WatchlistRepository | None = None,
    market_data_service: MarketDataService | None = None,
    change_detector: ChangeDetector | None = None,
) -> Flask:
    app = Flask(__name__)
    CORS(app)

    market = market_data_service or MarketDataService()
    detector = change_detector or ChangeDetector()
    shared_repo = repository
    shared_conn = conn
    db_path_str = str(db_path)

    def get_repo() -> WatchlistRepository:
        if shared_repo is not None:
            return shared_repo
        if shared_conn is not None:
            return WatchlistRepository(shared_conn)
        repo = getattr(g, "_watchlist_repo", None)
        if repo is None:
            conn_for_request = connect(db_path_str)
            repo = WatchlistRepository(conn_for_request)
            g._watchlist_conn = conn_for_request
            g._watchlist_repo = repo
        return repo

    @app.teardown_appcontext
    def close_db(_error: BaseException | None) -> None:
        conn_for_request = g.pop("_watchlist_conn", None)
        g.pop("_watchlist_repo", None)
        if conn_for_request is not None:
            conn_for_request.close()

    @app.errorhandler(DuplicateError)
    def handle_duplicate(error: DuplicateError) -> tuple[Any, int]:
        return _json_error(str(error), 409)

    @app.errorhandler(NotFoundError)
    def handle_not_found(error: NotFoundError) -> tuple[Any, int]:
        return _json_error(str(error), 404)

    @app.errorhandler(ValueError)
    def handle_value(error: ValueError) -> tuple[Any, int]:
        return _json_error(str(error), 400)

    @app.errorhandler(400)
    def handle_bad_request(error: Any) -> tuple[Any, int]:
        description = getattr(error, "description", "bad request")
        return _json_error(str(description), 400)

    @app.post("/api/users")
    def create_user() -> tuple[Any, int]:
        payload = _require_json()
        username = payload.get("username", "")
        user = get_repo().create_user(username)
        return jsonify(_user_to_json(user)), 201

    @app.post("/api/watchlists")
    def create_watchlist() -> tuple[Any, int]:
        payload = _require_json()
        user_id = _require_int(payload, "user_id")
        name = payload.get("name", "")
        watchlist = get_repo().create_watchlist(user_id, name)
        return jsonify(_watchlist_to_json(watchlist)), 201

    @app.post("/api/demo/bootstrap")
    def bootstrap_demo() -> Any:
        repo = get_repo()
        payload = _require_json()
        username = str(payload.get("username") or DEMO_USERNAME)
        watchlist_name = str(payload.get("watchlist_name") or DEMO_WATCHLIST_NAME)
        symbols = payload.get("symbols") or DEMO_SYMBOLS
        if not isinstance(symbols, list) or not all(isinstance(symbol, str) for symbol in symbols):
            raise ValueError("symbols must be a list of strings")

        user = _get_or_create_user(repo, username)
        watchlist = _get_or_create_watchlist(repo, user.id, watchlist_name)
        demo_checkpoint = _pick_demo_checkpoint(market, symbols)

        seeded: list[dict[str, Any]] = []
        for symbol in symbols:
            try:
                item = repo.get_item_by_symbol(watchlist.id, symbol)
                if payload.get("reset"):
                    item = repo.set_stock_checkpoint(
                        watchlist.id,
                        symbol,
                        datetime.combine(demo_checkpoint, datetime.min.time(), tzinfo=UTC),
                    )
            except NotFoundError:
                item = repo.add_stock(
                    watchlist.id,
                    symbol,
                    now=datetime.combine(demo_checkpoint, datetime.min.time(), tzinfo=UTC),
                )
            seeded.append(_item_to_json(item))

        return jsonify(
            {
                "user": _user_to_json(user),
                "watchlist": _watchlist_to_json(watchlist),
                "seeded_symbols": seeded,
                "demo_checkpoint_date": demo_checkpoint.isoformat(),
            }
        )

    @app.get("/api/watchlists/<int:watchlist_id>")
    def get_watchlist(watchlist_id: int) -> Any:
        repo = get_repo()
        watchlist = repo.get_watchlist(watchlist_id)
        items = repo.list_items(watchlist_id)
        stocks = [_watchlist_item_summary(item, market) for item in items]
        return jsonify({"watchlist": _watchlist_to_json(watchlist), "stocks": stocks})

    @app.post("/api/watchlists/<int:watchlist_id>/stocks")
    def add_stock(watchlist_id: int) -> tuple[Any, int]:
        payload = _require_json()
        symbol = payload.get("symbol", "").strip()
        if not symbol:
            raise ValueError("symbol is required")
        try:
            if not market.validate_symbol(symbol):
                raise ValueError(f"Invalid symbol or no market data available for '{symbol}'")
        except RuntimeError as exc:
            return _json_error(str(exc), 503)
        item = get_repo().add_stock(watchlist_id, symbol)
        return jsonify(_item_to_json(item)), 201

    @app.delete("/api/watchlists/<int:watchlist_id>/stocks/<symbol>")
    def delete_stock(watchlist_id: int, symbol: str) -> tuple[Any, int]:
        repo = get_repo()
        item = repo.get_item_by_symbol(watchlist_id, symbol)
        repo.remove_stock(watchlist_id, symbol)
        return jsonify({"deleted": True, "symbol": item.symbol, "watchlist_id": watchlist_id})

    @app.get("/api/watchlists/<int:watchlist_id>/changes")
    def get_changes(watchlist_id: int) -> Any:
        repo = get_repo()
        watchlist = repo.get_watchlist(watchlist_id)
        items = repo.list_items(watchlist_id)
        nifty_daily = market.fetch_nifty50(period=HISTORY_PERIOD)
        nifty_intraday = market.fetch_nifty50_intraday(period="5d", interval="5m")

        simulated_cp = _resolve_simulated_checkpoint(request.args.get("simulated_checkpoint"), market)
        canonical_cp = _resolve_canonical_checkpoint(watchlist, items, simulated_cp)

        changes = []
        for item in items:
            stock_daily = market.fetch_daily_ohlcv(item.symbol, period=HISTORY_PERIOD)
            stock_intraday = market.fetch_intraday_ohlcv(item.symbol, period="5d", interval="5m")
            changes.append(
                _change_payload(
                    item,
                    market,
                    stock_daily,
                    stock_intraday,
                    nifty_daily,
                    nifty_intraday,
                    detector,
                    checkpoint=canonical_cp,
                )
            )

        groups = {
            "needs_attention": [change for change in changes if change["classification"] == "SIGNIFICANT"],
            "worth_watching": [change for change in changes if change["classification"] == "WORTH_WATCHING"],
            "all_quiet": [change for change in changes if change["classification"] == "NORMAL"],
        }
        elapsed_text = _elapsed_text(canonical_cp)
        market_info = get_market_status()
        return jsonify(
            {
                "watchlist": _watchlist_to_json(watchlist),
                "last_checked_at": _dt(canonical_cp),
                "is_simulated": simulated_cp is not None,
                "elapsed_text": elapsed_text,
                "changes": changes,
                "groups": groups,
                "market_status": market_info,
            }
        )

    @app.get("/api/watchlists/<int:watchlist_id>/changes/<symbol>/history")
    def get_change_history(watchlist_id: int, symbol: str) -> Any:
        repo = get_repo()
        watchlist = repo.get_watchlist(watchlist_id)
        items = repo.list_items(watchlist_id)
        simulated_cp = _resolve_simulated_checkpoint(request.args.get("simulated_checkpoint"), market)
        checkpoint = _resolve_canonical_checkpoint(watchlist, items, simulated_cp)
        stock_daily = market.fetch_daily_ohlcv(symbol, period=HISTORY_PERIOD)
        stock_intraday = market.fetch_intraday_ohlcv(symbol, period="5d", interval="5m")
        nifty_daily = market.fetch_nifty50(period=HISTORY_PERIOD)
        nifty_intraday = market.fetch_nifty50_intraday(period="5d", interval="5m")
        assessment = detector.assess(
            stock_daily,
            nifty_daily,
            checkpoint,
            symbol=symbol,
            stock_intraday=stock_intraday,
            nifty_intraday=nifty_intraday,
        )
        elapsed_text = _elapsed_text(checkpoint)
        market_info = get_market_status()
        return jsonify(
            {
                "symbol": symbol,
                "display_name": _display_name(symbol),
                "checkpoint_at": _dt(checkpoint),
                "is_simulated": simulated_cp is not None,
                "elapsed_text": elapsed_text,
                "series": _history_series(stock_daily, checkpoint),
                "nifty_series": _history_series(nifty_daily, checkpoint),
                "assessment": _assessment_to_json(assessment),
                "market_status": market_info,
            }
        )

    @app.get("/api/watchlists/<int:watchlist_id>/timeline")
    def get_timeline(watchlist_id: int) -> Any:
        repo = get_repo()
        watchlist = repo.get_watchlist(watchlist_id)
        items = repo.list_items(watchlist_id)
        simulated_cp = _resolve_simulated_checkpoint(request.args.get("simulated_checkpoint"), market)
        canonical_cp = _resolve_canonical_checkpoint(watchlist, items, simulated_cp)
        nifty = market.fetch_nifty50(period=HISTORY_PERIOD)
        events: list[dict[str, Any]] = []
        for item in items:
            stock = market.fetch_daily_ohlcv(item.symbol, period=HISTORY_PERIOD)
            events.extend(_timeline_events(item, stock, nifty, checkpoint=canonical_cp))
        events.sort(key=lambda event: (event["date"], event["magnitude"]), reverse=True)
        return jsonify({"events": events[:24]})

    @app.get("/api/stocks/search")
    def search_stocks() -> Any:
        query = request.args.get("q", "").strip()
        sector = request.args.get("sector", "").strip()
        results = market.search_catalog(query=query, sector=sector)
        if query and not results:
            formatted = query.upper() if query.endswith(".NS") else f"{query.upper()}.NS"
            try:
                if market.validate_symbol(formatted):
                    results.append(
                        {
                            "symbol": formatted,
                            "display_name": _display_name(formatted),
                            "sector": get_stock_sector(formatted),
                        }
                    )
            except Exception:
                pass
        return jsonify({"query": query, "sector": sector, "results": results})

    @app.get("/api/stocks/<symbol>/detail")
    def get_stock_detail(symbol: str) -> Any:
        target_symbol = symbol.strip().upper()
        if not target_symbol.endswith(".NS") and not target_symbol.startswith("^"):
            target_symbol = f"{target_symbol}.NS"

        watchlist_id = request.args.get("watchlist_id", type=int)
        simulated_cp = _resolve_simulated_checkpoint(request.args.get("simulated_checkpoint"), market)

        repo = get_repo()
        checkpoint = simulated_cp or (datetime.now(UTC) - timedelta(days=7))
        if watchlist_id:
            try:
                watchlist = repo.get_watchlist(watchlist_id)
                items = repo.list_items(watchlist_id)
                checkpoint = _resolve_canonical_checkpoint(watchlist, items, simulated_cp)
            except NotFoundError:
                if simulated_cp:
                    checkpoint = simulated_cp

        stock_daily = market.fetch_daily_ohlcv(target_symbol, period=HISTORY_PERIOD)
        stock_intraday = market.fetch_intraday_ohlcv(target_symbol, period="5d", interval="5m")
        nifty_daily = market.fetch_nifty50(period=HISTORY_PERIOD)
        nifty_intraday = market.fetch_nifty50_intraday(period="5d", interval="5m")

        assessment = detector.assess(
            stock_daily,
            nifty_daily,
            checkpoint,
            symbol=target_symbol,
            stock_intraday=stock_intraday,
            nifty_intraday=nifty_intraday,
        )

        elapsed_text = _elapsed_text(checkpoint)
        why = _why_summary(assessment, elapsed_text)
        series = _history_series(stock_daily, checkpoint)
        nifty_series = _history_series(nifty_daily, checkpoint)
        volume_metrics = market.fetch_volume_metrics(target_symbol)
        peers = market.fetch_sector_peers(target_symbol)
        sector_perf = market.fetch_sector_performance(target_symbol)
        news = market.fetch_stock_news(target_symbol)
        market_info = get_market_status()

        sector = get_stock_sector(target_symbol)

        latest_data = stock_intraday if not stock_intraday.empty else stock_daily
        latest = _latest_bar(latest_data)
        previous = _previous_bar(stock_daily)

        return jsonify(
            {
                "symbol": target_symbol,
                "display_name": _display_name(target_symbol),
                "sector": sector,
                "latest_price": _bar_value(latest, "close"),
                "day_change": _day_change(latest, previous),
                "day_change_percent": _day_change_percent(latest, previous),
                "checkpoint_at": _dt(checkpoint),
                "is_simulated": simulated_cp is not None,
                "elapsed_text": elapsed_text,
                "assessment": _assessment_to_json(assessment),
                "why": why,
                "series": series,
                "nifty_series": nifty_series,
                "volume_metrics": volume_metrics,
                "peers": peers,
                "sector_performance": sector_perf,
                "news": news,
                "market_status": market_info,
            }
        )


    @app.get("/api/stocks/<symbol>/preview")
    def preview_stock(symbol: str) -> Any:
        data = market.fetch_daily_ohlcv(symbol, period=HISTORY_PERIOD)
        latest = _latest_bar(data)
        previous = _previous_bar(data)
        trend = _recent_trend(data)
        return jsonify(
            {
                "symbol": symbol.strip(),
                "display_name": _display_name(symbol),
                "latest_price": _bar_value(latest, "close"),
                "latest_price_date": _date_value(latest["date"]) if latest is not None else None,
                "day_change": _day_change(latest, previous),
                "day_change_percent": _day_change_percent(latest, previous),
                "trend": trend,
                "has_data": latest is not None,
            }
        )

    @app.post("/api/watchlists/<int:watchlist_id>/acknowledge")
    def acknowledge_watchlist(watchlist_id: int) -> Any:

        repo = get_repo()
        updated_items = repo.acknowledge_watchlist(watchlist_id)
        watchlist = repo.get_watchlist(watchlist_id)
        return jsonify(
            {
                "watchlist": _watchlist_to_json(watchlist),
                "stocks": [_item_to_json(item) for item in updated_items],
            }
        )

    return app


def _require_json() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("request body must be a JSON object")
    return payload


def _require_int(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _json_error(message: str, status: int) -> tuple[Any, int]:
    return jsonify({"error": message}), status


def _get_or_create_user(repo: WatchlistRepository, username: str) -> Any:
    try:
        return repo.get_user_by_username(username)
    except NotFoundError:
        return repo.create_user(username)


def _get_or_create_watchlist(repo: WatchlistRepository, user_id: int, name: str) -> Any:
    try:
        return repo.get_watchlist_by_name(user_id, name)
    except NotFoundError:
        return repo.create_watchlist(user_id, name)


def _pick_demo_checkpoint(market: MarketDataService, symbols: list[str]) -> date:
    """Choose a recent real trading session with enough history for comparison."""
    common_dates: set[date] | None = None
    for symbol in [*symbols, "^NSEI"]:
        data = (
            market.fetch_nifty50(period=HISTORY_PERIOD)
            if symbol == "^NSEI"
            else market.fetch_daily_ohlcv(symbol, period=HISTORY_PERIOD)
        )
        dates = {pd.Timestamp(value).date() for value in data.get("date", pd.Series(dtype="datetime64[ns]"))}
        if dates:
            common_dates = dates if common_dates is None else common_dates & dates

    ordered = sorted(common_dates or [])
    if len(ordered) >= 12:
        return ordered[-6]
    if ordered:
        return ordered[max(0, len(ordered) - 2)]
    return datetime.now(UTC).date()


def _resolve_simulated_checkpoint(raw_value: str | None, market: MarketDataService) -> datetime | None:
    if not raw_value:
        return None
    val = raw_value.strip().lower()
    now = datetime.now(UTC)
    if val in ("just_now", "just now"):
        return now - timedelta(minutes=5)
    if val in ("1h_ago", "1h", "1 hour ago"):
        return now - timedelta(hours=1)
    if val in ("1d_ago", "1d", "1 day ago"):
        return now - timedelta(days=1)
    if val in ("3d_ago", "3d", "3 days ago"):
        return now - timedelta(days=3)
    if val in ("28aug_demo", "28aug", "28 aug demo"):
        demo_date = _pick_demo_checkpoint(market, DEMO_SYMBOLS)
        return datetime.combine(demo_date, datetime.min.time(), tzinfo=UTC)
    try:
        dt = datetime.fromisoformat(raw_value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return None


def _resolve_canonical_checkpoint(
    watchlist: Any,
    items: list[WatchlistItem],
    simulated_cp: datetime | None,
) -> datetime:
    """Single source of truth for the active watchlist checkpoint."""
    if simulated_cp is not None:
        return simulated_cp
    if watchlist.last_acknowledged_at is not None:
        return watchlist.last_acknowledged_at
    if items:
        return max(item.checkpoint_at for item in items)
    return watchlist.created_at


def _user_to_json(user: Any) -> dict[str, Any]:
    return {"id": user.id, "username": user.username, "created_at": _dt(user.created_at)}


def _watchlist_to_json(watchlist: Any) -> dict[str, Any]:
    return {
        "id": watchlist.id,
        "user_id": watchlist.user_id,
        "name": watchlist.name,
        "last_acknowledged_at": _dt(watchlist.last_acknowledged_at),
        "created_at": _dt(watchlist.created_at),
    }


def _item_to_json(item: WatchlistItem) -> dict[str, Any]:
    sector = get_stock_sector(item.symbol)
    return {
        "id": item.id,
        "watchlist_id": item.watchlist_id,
        "symbol": item.symbol,
        "display_name": _display_name(item.symbol),
        "sector": sector,
        "added_at": _dt(item.added_at),
        "checkpoint_at": _dt(item.checkpoint_at),
    }


def _watchlist_item_summary(item: WatchlistItem, market: MarketDataService) -> dict[str, Any]:
    data = market.fetch_daily_ohlcv(item.symbol)
    latest = _latest_bar(data)
    previous = _previous_bar(data)
    sector = get_stock_sector(item.symbol)
    return {
        **_item_to_json(item),
        "display_name": _display_name(item.symbol),
        "sector": sector,
        "latest_price": _bar_value(latest, "close"),
        "latest_price_date": _date_value(latest["date"]) if latest is not None else None,
        "day_change": _day_change(latest, previous),
        "day_change_percent": _day_change_percent(latest, previous),
    }


def _change_payload(
    item: WatchlistItem,
    market: MarketDataService,
    stock_daily: pd.DataFrame,
    stock_intraday: pd.DataFrame,
    nifty_daily: pd.DataFrame,
    nifty_intraday: pd.DataFrame,
    detector: ChangeDetector,
    *,
    checkpoint: datetime | None = None,
) -> dict[str, Any]:
    eff_checkpoint = checkpoint or item.checkpoint_at
    assessment = detector.assess(
        stock_daily,
        nifty_daily,
        eff_checkpoint,
        symbol=item.symbol,
        stock_intraday=stock_intraday,
        nifty_intraday=nifty_intraday,
    )
    latest_data = stock_intraday if not stock_intraday.empty else stock_daily
    latest = _latest_bar(latest_data)
    previous = _previous_bar(stock_daily)
    elapsed = _elapsed_text(eff_checkpoint)
    item_json = _item_to_json(item)
    item_json["checkpoint_at"] = _dt(eff_checkpoint)
    sector = get_stock_sector(item.symbol)
    return {
        **_assessment_to_json(assessment),
        "display_name": _display_name(item.symbol),
        "sector": sector,
        "item": item_json,
        "elapsed_text": elapsed,
        "latest_price": _bar_value(latest, "close"),
        "latest_price_date": _date_value(latest["date"]) if latest is not None and "date" in latest else None,
        "day_change": _day_change(latest, previous),
        "day_change_percent": _day_change_percent(latest, previous),
        "why": _why_summary(assessment, elapsed),
    }


def _assessment_to_json(assessment: ChangeAssessment) -> dict[str, Any]:
    return {
        "symbol": assessment.symbol,
        "classification": assessment.classification,
        "last_checked": _date_value(assessment.last_checked),
        "user_checkpoint_at": assessment.user_checkpoint_at,
        "latest_market_timestamp": assessment.latest_market_timestamp,
        "is_market_open": assessment.is_market_open,
        "checkpoint_after_latest_data": assessment.checkpoint_after_latest_data,
        "baseline_date": _date_value(assessment.baseline_date),
        "latest_date": _date_value(assessment.latest_date),
        "nifty_baseline_date": _date_value(assessment.nifty_baseline_date),
        "nifty_latest_date": _date_value(assessment.nifty_latest_date),
        "trading_days": assessment.trading_days,
        "stock_return": assessment.stock_return,
        "nifty_return": assessment.nifty_return,
        "relative_performance": assessment.relative_performance,
        "daily_volatility": assessment.daily_volatility,
        "period_volatility": assessment.period_volatility,
        "unusualness_z": assessment.unusualness_z,
        "volatility_observations": assessment.volatility_observations,
        "insufficient_data": assessment.insufficient_data,
        "flags": list(assessment.flags),
        "thresholds": assessment.thresholds,
    }


def _why_summary(assessment: ChangeAssessment, elapsed_text: str = "") -> dict[str, Any]:
    if assessment.stock_return is None:
        return {
            "summary": "We don't have enough historical market data to compare this with your last check yet.",
            "supporting_signals": [],
        }

    latest_dt_str = _date_value(assessment.latest_date) or ""
    date_part = f" Latest available market data: {latest_dt_str}." if latest_dt_str else ""
    time_part = f" ({elapsed_text})" if elapsed_text else ""

    if "CHECKPOINT_AFTER_LATEST_DATA" in assessment.flags:
        return {
            "summary": f"Your last check{time_part} was after the latest completed NSE trading session.{date_part}",
            "supporting_signals": [
                {"label": "Stock move", "value": 0.0},
                {"label": "NIFTY move", "value": 0.0},
                {"label": "Relative to NIFTY", "value": 0.0},
            ],
        }

    if "NO_NEW_TRADING_SESSION" in assessment.flags:
        return {
            "summary": f"No new trading session since your last check{time_part}.{date_part}",
            "supporting_signals": [
                {"label": "Stock move", "value": 0.0},
                {"label": "NIFTY move", "value": 0.0},
                {"label": "Relative to NIFTY", "value": 0.0},
            ],
        }

    if assessment.relative_performance is None:
        stock_move = assessment.stock_return * 100
        sign_stock = "+" if stock_move > 0 else ""
        if "NIFTY_TIMESTAMP_MISMATCH" in assessment.flags:
            msg = "Relative NIFTY comparison is unavailable due to price timestamp alignment."
        else:
            msg = "Relative NIFTY comparison is unavailable."
        return {
            "summary": f"Stock moved {sign_stock}{stock_move:.1f}%. {msg}",
            "supporting_signals": [{"label": "Stock move", "value": assessment.stock_return}],
        }

    stock_move = assessment.stock_return * 100
    nifty_move = (assessment.nifty_return or 0) * 100
    relative_pp = abs(assessment.relative_performance * 100)
    sign_stock = "+" if stock_move > 0 else ""
    sign_nifty = "+" if nifty_move > 0 else ""

    if assessment.relative_performance >= 0:
        perf_text = f"Outperformed NIFTY by {relative_pp:.2f} percentage points."
    else:
        perf_text = f"Underperformed NIFTY by {relative_pp:.2f} percentage points."

    summary = (
        f"Stock moved {sign_stock}{stock_move:.1f}% while NIFTY moved {sign_nifty}{nifty_move:.1f}%. "
        f"{perf_text}"
    )
    signals = [
        {"label": "Stock move", "value": assessment.stock_return},
        {"label": "NIFTY move", "value": assessment.nifty_return},
        {"label": "Relative to NIFTY", "value": assessment.relative_performance},
    ]
    if assessment.unusualness_z is not None:
        signals.append(
            {"label": "Move versus usual", "value": assessment.unusualness_z, "kind": "z_score"}
        )
    return {"summary": summary, "supporting_signals": signals}


def _elapsed_text(checkpoint_at: datetime | None, now: datetime | None = None) -> str:
    if checkpoint_at is None:
        return "just now"
    current = now or datetime.now(UTC)
    if checkpoint_at.tzinfo is None:
        checkpoint_at = checkpoint_at.replace(tzinfo=UTC)
    seconds = max(0.0, (current - checkpoint_at).total_seconds())
    if seconds < 3600:
        minutes = max(1, int(seconds // 60))
        return f"{minutes} minute ago" if minutes == 1 else f"{minutes} minutes ago"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        return f"{hours} hour ago" if hours == 1 else f"{hours} hours ago"
    else:
        days = int(seconds // 86400)
        return f"{days} day ago" if days == 1 else f"{days} days ago"


def _history_series(frame: pd.DataFrame, checkpoint_at: datetime) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    cp_date = checkpoint_at.date() if isinstance(checkpoint_at, datetime) else pd.Timestamp(checkpoint_at).date()
    cutoff = pd.Timestamp(cp_date)
    out = frame[frame["date"] >= cutoff].copy()
    if len(out.index) < 2:
        out = frame.tail(7).copy()
    series = []
    baseline = _float_or_none(out.iloc[0]["close"])
    for _, row in out.iterrows():
        close = _float_or_none(row["close"])
        rel = None
        if baseline not in (None, 0) and close is not None:
            rel = close / baseline - 1.0
        series.append(
            {
                "date": _date_value(row["date"]),
                "close": close,
                "relative_to_checkpoint": rel,
            }
        )
    return series



def _timeline_events(
    item: WatchlistItem,
    stock: pd.DataFrame,
    nifty: pd.DataFrame,
    *,
    checkpoint: datetime | None = None,
) -> list[dict[str, Any]]:
    if stock.empty:
        return []
    cp_dt = checkpoint or item.checkpoint_at
    cutoff = pd.Timestamp(cp_dt.date())
    stock_window = stock[stock["date"] >= cutoff].copy()
    if len(stock_window.index) < 2:
        return []

    nifty_lookup = nifty.set_index("date")["close"] if not nifty.empty else pd.Series(dtype=float)
    events = []
    stock_window["daily_return"] = stock_window["close"].pct_change()
    for idx in range(1, len(stock_window.index)):
        row = stock_window.iloc[idx]
        previous = stock_window.iloc[idx - 1]
        daily_return = _float_or_none(row["daily_return"])
        if daily_return is None:
            continue
        date_key = pd.Timestamp(row["date"])
        nifty_return = None
        if not nifty_lookup.empty and date_key in nifty_lookup.index:
            prev_nifty = nifty_lookup[nifty_lookup.index < date_key].tail(1)
            curr_nifty = _float_or_none(nifty_lookup.loc[date_key])
            prev_nifty_close = _float_or_none(prev_nifty.iloc[0]) if len(prev_nifty.index) else None
            if curr_nifty is not None and prev_nifty_close not in (None, 0):
                nifty_return = curr_nifty / prev_nifty_close - 1.0
        relative = daily_return - nifty_return if nifty_return is not None else daily_return
        if abs(relative) < 0.015 and abs(daily_return) < 0.02:
            continue
        events.append(
            {
                "symbol": item.symbol,
                "display_name": _display_name(item.symbol),
                "date": _date_value(row["date"]),
                "close": _float_or_none(row["close"]),
                "daily_return": daily_return,
                "relative_to_nifty": relative,
                "magnitude": abs(relative),
                "direction": "up" if relative >= 0 else "down",
                "label": _timeline_label(item.symbol, daily_return, relative),
            }
        )
    return events


def _timeline_label(symbol: str, daily_return: float, relative: float) -> str:
    name = _display_name(symbol)
    move = daily_return * 100
    rel_pp = abs(relative * 100)
    sign = "+" if move > 0 else ""
    if relative >= 0:
        perf = f"outperformed NIFTY by {rel_pp:.2f} percentage points"
    else:
        perf = f"underperformed NIFTY by {rel_pp:.2f} percentage points"
    return f"{name} moved {sign}{move:.1f}% on the day ({perf})."


def _display_name(symbol: str) -> str:
    target_symbol = symbol.upper().strip()
    catalog_item = next((item for item in STOCK_CATALOG if item["symbol"] == target_symbol), None)
    if catalog_item:
        return catalog_item["display_name"]
    return DISPLAY_NAMES.get(target_symbol, target_symbol.removesuffix(".NS"))


def _watchlist_last_checked(items: list[WatchlistItem], watchlist: Any) -> str | None:
    if items:
        latest_checkpoint = max(item.checkpoint_at for item in items)
        return _dt(latest_checkpoint)
    return _dt(watchlist.last_acknowledged_at)


def _latest_bar(data: pd.DataFrame) -> pd.Series | None:
    if data is None or data.empty:
        return None
    return data.iloc[-1]


def _previous_bar(data: pd.DataFrame) -> pd.Series | None:
    if data is None or len(data.index) < 2:
        return None
    return data.iloc[-2]


def _recent_trend(data: pd.DataFrame) -> list[dict[str, Any]]:
    if data is None or data.empty:
        return []
    subset = data.tail(7)
    return [
        {"date": _date_value(row["date"]), "close": _float_or_none(row["close"])}
        for _, row in subset.iterrows()
    ]


def _day_change(latest: pd.Series | None, previous: pd.Series | None) -> float | None:
    latest_close = _bar_value(latest, "close")
    prev_close = _bar_value(previous, "close")
    if latest_close is None or prev_close is None:
        return None
    return latest_close - prev_close


def _day_change_percent(latest: pd.Series | None, previous: pd.Series | None) -> float | None:
    change = _day_change(latest, previous)
    prev_close = _bar_value(previous, "close")
    if change is None or prev_close in (None, 0):
        return None
    return change / prev_close


def _bar_value(bar: pd.Series | None, field: str) -> float | None:
    if bar is None:
        return None
    return _float_or_none(bar[field])


def _dt(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _date_value(value: date | datetime | pd.Timestamp | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    return value.isoformat()


def _float_or_none(value: Any) -> float | None:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    return float(numeric)


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
