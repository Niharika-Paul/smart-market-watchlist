"""Market data service wrapping yfinance for NSE equities and NIFTY 50."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
UTC = timezone.utc

OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
INTRADAY_COLUMNS = ["timestamp", "date", "open", "high", "low", "close", "volume"]
NIFTY_50_SYMBOL = "^NSEI"
DEFAULT_PERIOD = "5d"
YFINANCE_CACHE_DIR = Path(__file__).resolve().parent / ".yfinance-cache"

DateLike = str | date | datetime


def get_market_status(dt: datetime | None = None) -> dict[str, Any]:
    """Check if NSE stock market is currently open or closed (IST: Mon-Fri 09:15-15:30)."""
    now_ist = (dt or datetime.now(UTC))
    if now_ist.tzinfo is None:
        now_ist = now_ist.replace(tzinfo=UTC)
    now_ist = now_ist.astimezone(IST)

    weekday = now_ist.weekday()  # 0 = Monday, 6 = Sunday
    current_time = now_ist.time()

    market_open = time(9, 15)
    market_close = time(15, 30)

    is_weekday = weekday < 5
    is_during_hours = market_open <= current_time <= market_close
    is_open = is_weekday and is_during_hours

    # Calculate latest expected completed trading session date
    latest_session = now_ist.date()
    if not is_weekday:
        # Weekend: latest session was Friday
        days_back = weekday - 4
        latest_session = now_ist.date() - timedelta(days=days_back)
    elif current_time < market_open:
        # Before market open: latest session was yesterday (or Friday if Monday)
        days_back = 3 if weekday == 0 else 1
        latest_session = now_ist.date() - timedelta(days=days_back)

    if is_open:
        status_code = "OPEN"
        status_text = "Market open — trading in progress"
    elif is_weekday and current_time > market_close:
        status_code = "AFTER_HOURS"
        status_text = "Market closed — after hours"
    else:
        status_code = "CLOSED"
        status_text = "Market closed"

    return {
        "is_open": is_open,
        "status_code": status_code,
        "status_text": status_text,
        "latest_session_date": latest_session,
        "current_time_ist": now_ist.isoformat(),
    }



def _configure_yfinance_cache() -> None:
    """Point yfinance's caches at a writable project-local directory."""
    YFINANCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    yf.set_tz_cache_location(str(YFINANCE_CACHE_DIR))



STOCK_CATALOG = [
    # Technology / IT
    {
        "symbol": "TCS.NS",
        "display_name": "TCS",
        "sector": "Technology",
        "keywords": ["tcs", "tata consultancy", "tata", "it", "tech", "technology", "software", "services"],
    },
    {
        "symbol": "INFY.NS",
        "display_name": "Infosys",
        "sector": "Technology",
        "keywords": ["infosys", "infy", "it", "tech", "technology", "software", "services"],
    },
    {
        "symbol": "WIPRO.NS",
        "display_name": "Wipro",
        "sector": "Technology",
        "keywords": ["wipro", "it", "tech", "technology", "software", "services"],
    },
    {
        "symbol": "HCLTECH.NS",
        "display_name": "HCL Technologies",
        "sector": "Technology",
        "keywords": ["hcl", "hcltech", "hcl technologies", "it", "tech", "technology", "software"],
    },
    {
        "symbol": "TECHM.NS",
        "display_name": "Tech Mahindra",
        "sector": "Technology",
        "keywords": ["techm", "tech mahindra", "mahindra", "it", "tech", "technology", "software"],
    },
    {
        "symbol": "LTIM.NS",
        "display_name": "LTIMindtree",
        "sector": "Technology",
        "keywords": ["ltim", "ltimindtree", "mindtree", "larsen", "it", "tech", "technology", "software"],
    },
    {
        "symbol": "PERSISTENT.NS",
        "display_name": "Persistent Systems",
        "sector": "Technology",
        "keywords": ["persistent", "persistent systems", "it", "tech", "technology", "software"],
    },
    {
        "symbol": "COFORGE.NS",
        "display_name": "Coforge",
        "sector": "Technology",
        "keywords": ["coforge", "it", "tech", "technology", "software"],
    },

    # Banking
    {
        "symbol": "HDFCBANK.NS",
        "display_name": "HDFC Bank",
        "sector": "Banking",
        "keywords": ["hdfc", "hdfc bank", "bank", "banking", "finance", "financial services", "private bank"],
    },
    {
        "symbol": "ICICIBANK.NS",
        "display_name": "ICICI Bank",
        "sector": "Banking",
        "keywords": ["icici", "icici bank", "bank", "banking", "finance", "financial services", "private bank"],
    },
    {
        "symbol": "SBIN.NS",
        "display_name": "State Bank of India",
        "sector": "Banking",
        "keywords": ["sbi", "state bank", "sbin", "bank", "banking", "finance", "financial services", "psu bank"],
    },
    {
        "symbol": "KOTAKBANK.NS",
        "display_name": "Kotak Mahindra Bank",
        "sector": "Banking",
        "keywords": ["kotak", "kotak bank", "kotak mahindra", "bank", "banking", "finance", "financial services"],
    },
    {
        "symbol": "AXISBANK.NS",
        "display_name": "Axis Bank",
        "sector": "Banking",
        "keywords": ["axis", "axis bank", "bank", "banking", "finance", "financial services"],
    },
    {
        "symbol": "BANKBARODA.NS",
        "display_name": "Bank of Baroda",
        "sector": "Banking",
        "keywords": ["bob", "bank of baroda", "baroda", "bank", "banking", "finance", "psu bank"],
    },
    {
        "symbol": "PNB.NS",
        "display_name": "Punjab National Bank",
        "sector": "Banking",
        "keywords": ["pnb", "punjab national bank", "bank", "banking", "finance", "psu bank"],
    },
    {
        "symbol": "INDUSINDBK.NS",
        "display_name": "IndusInd Bank",
        "sector": "Banking",
        "keywords": ["indusind", "indusind bank", "bank", "banking", "finance"],
    },

    # Financial Services
    {
        "symbol": "BAJFINANCE.NS",
        "display_name": "Bajaj Finance",
        "sector": "Financial Services",
        "keywords": ["bajaj finance", "bajfinance", "bajaj", "finance", "financial services", "nbfc"],
    },
    {
        "symbol": "BAJAJFINSV.NS",
        "display_name": "Bajaj Finserv",
        "sector": "Financial Services",
        "keywords": ["bajaj finserv", "bajajfinsv", "bajaj", "finance", "financial services", "insurance"],
    },
    {
        "symbol": "JIOFIN.NS",
        "display_name": "Jio Financial Services",
        "sector": "Financial Services",
        "keywords": ["jio", "jio financial", "jiofin", "ambani", "finance", "financial services"],
    },
    {
        "symbol": "GROWW.NS",
        "display_name": "Groww",
        "sector": "Financial Services",
        "keywords": ["groww", "billionbrains", "fintech", "brokerage", "investing", "mutual funds", "stocks", "finance", "financial services"],
    },
    {
        "symbol": "HDFCLIFE.NS",
        "display_name": "HDFC Life Insurance",
        "sector": "Financial Services",
        "keywords": ["hdfc life", "hdfc", "insurance", "finance", "financial services"],
    },
    {
        "symbol": "SBILIFE.NS",
        "display_name": "SBI Life Insurance",
        "sector": "Financial Services",
        "keywords": ["sbi life", "sbi", "insurance", "finance", "financial services"],
    },

    # Automotive
    {
        "symbol": "TATAMOTORS.NS",
        "display_name": "Tata Motors",
        "sector": "Automotive",
        "keywords": ["tata", "tata motors", "motors", "auto", "automotive", "ev", "vehicles", "cars"],
    },
    {
        "symbol": "MARUTI.NS",
        "display_name": "Maruti Suzuki",
        "sector": "Automotive",
        "keywords": ["maruti", "maruti suzuki", "suzuki", "auto", "automotive", "cars", "vehicles"],
    },
    {
        "symbol": "M&M.NS",
        "display_name": "Mahindra & Mahindra",
        "sector": "Automotive",
        "keywords": ["m&m", "mahindra", "mahindra & mahindra", "auto", "automotive", "suv", "tractors", "vehicles"],
    },
    {
        "symbol": "BAJAJ-AUTO.NS",
        "display_name": "Bajaj Auto",
        "sector": "Automotive",
        "keywords": ["bajaj auto", "bajaj", "auto", "automotive", "two wheeler", "bikes", "vehicles"],
    },
    {
        "symbol": "HEROMOTOCO.NS",
        "display_name": "Hero MotoCorp",
        "sector": "Automotive",
        "keywords": ["hero", "hero motocorp", "auto", "automotive", "two wheeler", "bikes", "vehicles"],
    },
    {
        "symbol": "EICHERMOT.NS",
        "display_name": "Eicher Motors",
        "sector": "Automotive",
        "keywords": ["eicher", "royal enfield", "auto", "automotive", "two wheeler", "bikes", "vehicles"],
    },
    {
        "symbol": "TVSMOTOR.NS",
        "display_name": "TVS Motor Company",
        "sector": "Automotive",
        "keywords": ["tvs", "tvs motor", "auto", "automotive", "two wheeler", "bikes", "vehicles"],
    },

    # Pharma & Healthcare
    {
        "symbol": "SUNPHARMA.NS",
        "display_name": "Sun Pharmaceutical",
        "sector": "Pharma",
        "keywords": ["sun", "sun pharma", "sun pharmaceutical", "pharma", "pharmaceuticals", "healthcare", "health", "medicine"],
    },
    {
        "symbol": "CIPLA.NS",
        "display_name": "Cipla",
        "sector": "Pharma",
        "keywords": ["cipla", "pharma", "pharmaceuticals", "healthcare", "health", "medicine"],
    },
    {
        "symbol": "DRREDDY.NS",
        "display_name": "Dr. Reddy's Laboratories",
        "sector": "Pharma",
        "keywords": ["dr reddy", "drreddy", "reddy", "pharma", "pharmaceuticals", "healthcare", "health", "medicine"],
    },
    {
        "symbol": "DIVISLAB.NS",
        "display_name": "Divi's Laboratories",
        "sector": "Pharma",
        "keywords": ["divis", "divi", "divislab", "pharma", "pharmaceuticals", "healthcare", "health"],
    },
    {
        "symbol": "MANKIND.NS",
        "display_name": "Mankind Pharma",
        "sector": "Pharma",
        "keywords": ["mankind", "mankind pharma", "pharma", "pharmaceuticals", "healthcare", "health"],
    },
    {
        "symbol": "LUPIN.NS",
        "display_name": "Lupin",
        "sector": "Pharma",
        "keywords": ["lupin", "pharma", "pharmaceuticals", "healthcare", "health"],
    },
    {
        "symbol": "APOLLOHOSP.NS",
        "display_name": "Apollo Hospitals",
        "sector": "Healthcare",
        "keywords": ["apollo", "apollo hospitals", "hospitals", "healthcare", "health", "pharma"],
    },

    # Energy
    {
        "symbol": "RELIANCE.NS",
        "display_name": "Reliance Industries",
        "sector": "Energy",
        "keywords": ["reliance", "ril", "ambani", "jio", "energy", "oil", "gas", "petroleum", "refining"],
    },
    {
        "symbol": "NTPC.NS",
        "display_name": "NTPC Limited",
        "sector": "Energy",
        "keywords": ["ntpc", "power", "energy", "electricity", "psu"],
    },
    {
        "symbol": "POWERGRID.NS",
        "display_name": "Power Grid Corporation",
        "sector": "Energy",
        "keywords": ["power grid", "powergrid", "power", "energy", "transmission", "psu"],
    },
    {
        "symbol": "ONGC.NS",
        "display_name": "Oil & Natural Gas Corp",
        "sector": "Energy",
        "keywords": ["ongc", "oil", "gas", "energy", "petroleum", "exploration", "psu"],
    },
    {
        "symbol": "BPCL.NS",
        "display_name": "Bharat Petroleum",
        "sector": "Energy",
        "keywords": ["bpcl", "bharat petroleum", "oil", "gas", "energy", "petroleum", "psu"],
    },
    {
        "symbol": "IOC.NS",
        "display_name": "Indian Oil Corporation",
        "sector": "Energy",
        "keywords": ["ioc", "indian oil", "oil", "gas", "energy", "petroleum", "psu"],
    },
    {
        "symbol": "GAIL.NS",
        "display_name": "GAIL (India)",
        "sector": "Energy",
        "keywords": ["gail", "gas", "energy", "pipeline", "psu"],
    },
    {
        "symbol": "ADANIGREEN.NS",
        "display_name": "Adani Green Energy",
        "sector": "Energy",
        "keywords": ["adani", "adani green", "green energy", "energy", "renewable", "solar"],
    },
    {
        "symbol": "TATAPOWER.NS",
        "display_name": "Tata Power",
        "sector": "Energy",
        "keywords": ["tata", "tata power", "power", "energy", "electricity", "renewable"],
    },

    # FMCG
    {
        "symbol": "HINDUNILVR.NS",
        "display_name": "Hindustan Unilever",
        "sector": "FMCG",
        "keywords": ["hul", "hindustan unilever", "unilever", "fmcg", "consumer goods", "consumer"],
    },
    {
        "symbol": "ITC.NS",
        "display_name": "ITC Limited",
        "sector": "FMCG",
        "keywords": ["itc", "fmcg", "consumer goods", "consumer", "tobacco", "hotels"],
    },
    {
        "symbol": "NESTLEIND.NS",
        "display_name": "Nestle India",
        "sector": "FMCG",
        "keywords": ["nestle", "nestle india", "fmcg", "consumer goods", "food"],
    },
    {
        "symbol": "BRITANNIA.NS",
        "display_name": "Britannia Industries",
        "sector": "FMCG",
        "keywords": ["britannia", "fmcg", "consumer goods", "food", "biscuits"],
    },
    {
        "symbol": "TATACONSUM.NS",
        "display_name": "Tata Consumer Products",
        "sector": "FMCG",
        "keywords": ["tata", "tata consumer", "fmcg", "consumer goods", "tea", "food"],
    },
    {
        "symbol": "DABUR.NS",
        "display_name": "Dabur India",
        "sector": "FMCG",
        "keywords": ["dabur", "fmcg", "consumer goods", "healthcare", "ayurveda"],
    },
    {
        "symbol": "GODREJCP.NS",
        "display_name": "Godrej Consumer Products",
        "sector": "FMCG",
        "keywords": ["godrej", "godrej consumer", "godrejcp", "fmcg", "consumer goods"],
    },

    # Metals & Mining
    {
        "symbol": "TATASTEEL.NS",
        "display_name": "Tata Steel",
        "sector": "Metals",
        "keywords": ["tata", "tata steel", "steel", "metals", "mining", "metal"],
    },
    {
        "symbol": "HINDALCO.NS",
        "display_name": "Hindalco Industries",
        "sector": "Metals",
        "keywords": ["hindalco", "aditya birla", "aluminum", "copper", "metals", "mining", "metal"],
    },
    {
        "symbol": "JSWSTEEL.NS",
        "display_name": "JSW Steel",
        "sector": "Metals",
        "keywords": ["jsw", "jsw steel", "steel", "metals", "mining", "metal"],
    },
    {
        "symbol": "COALINDIA.NS",
        "display_name": "Coal India",
        "sector": "Metals",
        "keywords": ["coal india", "coal", "mining", "metals", "metal", "psu"],
    },
    {
        "symbol": "VEDL.NS",
        "display_name": "Vedanta",
        "sector": "Metals",
        "keywords": ["vedanta", "vedl", "metals", "mining", "metal", "zinc", "aluminum"],
    },

    # Telecom
    {
        "symbol": "BHARTIARTL.NS",
        "display_name": "Bharti Airtel",
        "sector": "Telecom",
        "keywords": ["airtel", "bharti", "bharti airtel", "telecom", "telecommunications", "5g", "mobile"],
    },
    {
        "symbol": "IDEA.NS",
        "display_name": "Vodafone Idea",
        "sector": "Telecom",
        "keywords": ["idea", "vodafone", "vodafone idea", "vi", "telecom", "telecommunications", "mobile"],
    },

    # Construction & Infrastructure
    {
        "symbol": "LT.NS",
        "display_name": "Larsen & Toubro",
        "sector": "Construction",
        "keywords": ["l&t", "larsen", "toubro", "lt", "infrastructure", "construction", "engineering", "building materials"],
    },
    {
        "symbol": "ULTRACEMCO.NS",
        "display_name": "UltraTech Cement",
        "sector": "Construction",
        "keywords": ["ultratech", "ultracemco", "cement", "construction", "building materials"],
    },
    {
        "symbol": "GRASIM.NS",
        "display_name": "Grasim Industries",
        "sector": "Construction",
        "keywords": ["grasim", "cement", "construction", "building materials", "chemicals"],
    },

    # Industrials & Defense
    {
        "symbol": "BEL.NS",
        "display_name": "Bharat Electronics",
        "sector": "Industrials",
        "keywords": ["bel", "bharat electronics", "defense", "electronics", "industrials", "psu"],
    },
    {
        "symbol": "HAL.NS",
        "display_name": "Hindustan Aeronautics",
        "sector": "Industrials",
        "keywords": ["hal", "hindustan aeronautics", "defense", "aerospace", "industrials", "psu"],
    },

    # Retail & Consumer Goods
    {
        "symbol": "ASIANPAINT.NS",
        "display_name": "Asian Paints",
        "sector": "Consumer Goods",
        "keywords": ["asian paints", "paint", "paints", "consumer goods", "home"],
    },
    {
        "symbol": "TITAN.NS",
        "display_name": "Titan Company",
        "sector": "Consumer Goods",
        "keywords": ["titan", "tata", "jewellery", "watches", "retail", "consumer goods"],
    },
    {
        "symbol": "TRENT.NS",
        "display_name": "Trent",
        "sector": "Consumer Goods",
        "keywords": ["trent", "zudio", "westside", "tata", "retail", "consumer goods"],
    },
    {
        "symbol": "ZOMATO.NS",
        "display_name": "Zomato",
        "sector": "Technology",
        "keywords": ["zomato", "blinkit", "food delivery", "tech", "technology", "consumer"],
    },
]

SECTOR_PEERS = {
    "Technology": ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
    "Banking": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS"],
    "Financial Services": ["BAJFINANCE.NS", "BAJAJFINSV.NS", "JIOFIN.NS", "GROWW.NS", "HDFCLIFE.NS"],
    "Automotive": ["TATAMOTORS.NS", "MARUTI.NS", "M&M.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS"],
    "Pharma": ["SUNPHARMA.NS", "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS", "MANKIND.NS"],
    "Healthcare": ["APOLLOHOSP.NS", "SUNPHARMA.NS", "CIPLA.NS"],
    "Energy": ["RELIANCE.NS", "NTPC.NS", "POWERGRID.NS", "ONGC.NS", "TATAPOWER.NS"],
    "FMCG": ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS"],
    "Metals": ["TATASTEEL.NS", "HINDALCO.NS", "JSWSTEEL.NS", "COALINDIA.NS", "VEDL.NS"],
    "Telecom": ["BHARTIARTL.NS", "IDEA.NS"],
    "Construction": ["LT.NS", "ULTRACEMCO.NS", "GRASIM.NS"],
    "Industrials": ["BEL.NS", "HAL.NS"],
    "Consumer Goods": ["ASIANPAINT.NS", "TITAN.NS", "TRENT.NS"],
}


def get_stock_sector(symbol: str) -> str:
    """Return canonical sector for a stock symbol, looking up STOCK_CATALOG first with smart heuristics fallback."""
    target_symbol = (symbol or "").upper().strip()
    if not target_symbol.endswith(".NS") and not target_symbol.startswith("^"):
        target_symbol = f"{target_symbol}.NS"

    catalog_item = next((item for item in STOCK_CATALOG if item["symbol"] == target_symbol), None)
    if catalog_item:
        return catalog_item["sector"]

    sym_clean = target_symbol.removesuffix(".NS").lower()
    if "groww" in sym_clean or "billionbrains" in sym_clean:
        return "Financial Services"
    if any(k in sym_clean for k in ["bank", "sbin", "pnb", "bob"]):
        return "Banking"
    if any(k in sym_clean for k in ["fin", "finance", "life", "insur", "nbfc", "broker", "wealth"]):
        return "Financial Services"
    if any(k in sym_clean for k in ["pharma", "lab", "health", "hosp", "drug", "care"]):
        return "Pharma"
    if any(k in sym_clean for k in ["motor", "auto", "car", "wheel"]):
        return "Automotive"
    if any(k in sym_clean for k in ["tech", "soft", "infy", "tcs", "wipro"]):
        return "Technology"
    if any(k in sym_clean for k in ["power", "energy", "oil", "gas", "ntpc", "gail", "ongc"]):
        return "Energy"
    if any(k in sym_clean for k in ["steel", "metal", "mine", "coal", "iron", "copper", "aluminum"]):
        return "Metals"
    if any(k in sym_clean for k in ["telecom", "airtel", "idea"]):
        return "Telecom"
    if any(k in sym_clean for k in ["infra", "build", "cement", "construct"]):
        return "Construction"

    return "Other"


SECTOR_ALIASES = {
    "it": ["technology", "it", "software"],
    "tech": ["technology", "it", "software"],
    "technology": ["technology", "it", "software"],
    "software": ["technology", "it", "software"],
    "banking": ["banking", "bank", "financial services", "finance"],
    "bank": ["banking", "bank", "financial services", "finance"],
    "banks": ["banking", "bank", "financial services", "finance"],
    "financial services": ["financial services", "finance", "banking", "bank"],
    "finance": ["financial services", "finance", "banking", "bank"],
    "pharma": ["pharma", "pharmaceuticals", "healthcare", "health"],
    "pharmaceuticals": ["pharma", "pharmaceuticals", "healthcare", "health"],
    "healthcare": ["pharma", "pharmaceuticals", "healthcare", "health"],
    "health": ["pharma", "pharmaceuticals", "healthcare", "health"],
    "medicine": ["pharma", "pharmaceuticals", "healthcare", "health"],
    "auto": ["automotive", "auto", "vehicles", "motors", "cars"],
    "automotive": ["automotive", "auto", "vehicles", "motors", "cars"],
    "motors": ["automotive", "auto", "vehicles", "motors", "cars"],
    "energy": ["energy", "oil", "gas", "power", "petroleum", "renewable"],
    "oil": ["energy", "oil", "gas", "petroleum"],
    "gas": ["energy", "oil", "gas"],
    "power": ["energy", "power"],
    "fmcg": ["fmcg", "consumer goods", "consumer"],
    "consumer goods": ["fmcg", "consumer goods", "consumer"],
    "consumer": ["fmcg", "consumer goods", "consumer"],
    "metals": ["metals", "mining", "steel", "metal"],
    "metal": ["metals", "mining", "steel", "metal"],
    "mining": ["metals", "mining", "steel", "metal"],
    "steel": ["metals", "mining", "steel", "metal"],
    "telecom": ["telecom", "telecommunications"],
    "telecommunications": ["telecom", "telecommunications"],
    "construction": ["construction", "infrastructure", "engineering", "building materials"],
    "infrastructure": ["construction", "infrastructure", "engineering"],
    "engineering": ["construction", "infrastructure", "engineering"],
}


class MarketDataService:
    """Fetch daily and intraday OHLCV bars from Yahoo Finance."""

    def search_catalog(self, query: str = "", sector: str = "") -> list[dict[str, str]]:
        q = (query or "").strip().lower()
        sec = (sector or "").strip().lower()

        target_sec_terms = set()
        if sec and sec != "all":
            target_sec_terms.add(sec)
            for alias_key, alias_list in SECTOR_ALIASES.items():
                if sec == alias_key or sec in alias_list:
                    target_sec_terms.update(alias_list)

        target_query_sec_terms = set()
        if q:
            for alias_key, alias_list in SECTOR_ALIASES.items():
                if q == alias_key or q in alias_list:
                    target_query_sec_terms.update(alias_list)

        results = []
        for item in STOCK_CATALOG:
            symbol_raw = item["symbol"].lower()
            symbol_clean = symbol_raw.removesuffix(".ns")
            name = item["display_name"].lower()
            item_sector = item["sector"].lower()
            keywords = [k.lower() for k in item["keywords"]]

            if target_sec_terms:
                sector_matches = (
                    item_sector in target_sec_terms
                    or any(t in item_sector for t in target_sec_terms)
                    or any(any(t in kw for t in target_sec_terms) for kw in keywords)
                )
                if not sector_matches:
                    continue

            if q:
                q_matches = (
                    q in symbol_raw
                    or q in symbol_clean
                    or q in name
                    or q in item_sector
                    or any(q in kw for kw in keywords)
                    or (target_query_sec_terms and item_sector in target_query_sec_terms)
                    or (target_query_sec_terms and any(t in item_sector for t in target_query_sec_terms))
                    or (target_query_sec_terms and any(any(t in kw for t in target_query_sec_terms) for kw in keywords))
                )
                if not q_matches:
                    continue

            results.append(
                {
                    "symbol": item["symbol"],
                    "display_name": item["display_name"],
                    "sector": item["sector"],
                }
            )
        return results

    def fetch_volume_metrics(self, symbol: str) -> dict[str, Any]:
        """Compute volume stats: current, 5d, 20d, 60d average, and activity ratio."""
        df = self.fetch_daily_ohlcv(symbol, period="6mo")
        if df.empty or "volume" not in df.columns:
            return {
                "current_volume": None,
                "avg_5d": None,
                "avg_20d": None,
                "avg_60d": None,
                "activity_ratio": None,
                "status_note": "Volume data unavailable",
            }

        valid = df.dropna(subset=["volume"])
        if valid.empty:
            return {
                "current_volume": None,
                "avg_5d": None,
                "avg_20d": None,
                "avg_60d": None,
                "activity_ratio": None,
                "status_note": "Volume data unavailable",
            }

        current_vol = int(valid.iloc[-1]["volume"])
        vols = valid["volume"]

        avg_5d = float(vols.tail(5).mean()) if len(vols) >= 1 else None
        avg_20d = float(vols.tail(20).mean()) if len(vols) >= 1 else None
        avg_60d = float(vols.tail(60).mean()) if len(vols) >= 1 else None

        activity_ratio = None
        if avg_20d and avg_20d > 0:
            activity_ratio = round(current_vol / avg_20d, 2)

        latest_date = pd.Timestamp(valid.iloc[-1]["date"]).date()
        today = datetime.now().date()
        status_note = (
            "Market closed — showing last completed session volume"
            if latest_date < today
            else "Current session volume"
        )

        return {
            "current_volume": current_vol,
            "avg_5d": round(avg_5d, 0) if avg_5d is not None else None,
            "avg_20d": round(avg_20d, 0) if avg_20d is not None else None,
            "avg_60d": round(avg_60d, 0) if avg_60d is not None else None,
            "activity_ratio": activity_ratio,
            "status_note": status_note,
        }

    def fetch_stock_news(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch news articles for a symbol using Yahoo Finance."""
        ticker = (symbol or "").strip()
        if not ticker:
            return []

        try:
            raw_news = yf.Ticker(ticker).news
        except Exception:
            return []

        if not raw_news or not isinstance(raw_news, list):
            return []

        parsed = []
        for item in raw_news:
            if not isinstance(item, dict):
                continue
            content = item.get("content") if isinstance(item.get("content"), dict) else item
            title = content.get("title")
            if not title:
                continue

            provider = content.get("provider")
            publisher = provider.get("displayName") if isinstance(provider, dict) else content.get("publisher", "News")

            canonical = content.get("canonicalUrl")
            link = canonical.get("url") if isinstance(canonical, dict) else content.get("link")
            if not link:
                click_through = content.get("clickThroughUrl")
                link = click_through.get("url") if isinstance(click_through, dict) else "#"

            pub_date = content.get("pubDate") or content.get("displayTime")
            if not pub_date and content.get("providerPublishTime"):
                try:
                    pub_date = datetime.fromtimestamp(content["providerPublishTime"], tz=UTC).isoformat()
                except Exception:
                    pub_date = None

            parsed.append(
                {
                    "title": title,
                    "publisher": publisher or "News",
                    "link": link or "#",
                    "pub_date": pub_date,
                    "summary": content.get("summary") or "",
                }
            )
            if len(parsed) >= 5:
                break
        return parsed

    def fetch_sector_peers(self, symbol: str) -> list[dict[str, Any]]:
        """Fetch curated sector peers with today's move and info."""
        target_symbol = symbol.upper().strip()
        sector = get_stock_sector(target_symbol)

        peer_symbols = [s for s in SECTOR_PEERS.get(sector, []) if s != target_symbol]

        peers = []
        for peer_sym in peer_symbols:
            peer_item = next((item for item in STOCK_CATALOG if item["symbol"] == peer_sym), None)
            display_name = peer_item["display_name"] if peer_item else peer_sym.removesuffix(".NS")
            peer_sector = get_stock_sector(peer_sym)

            df = self.fetch_daily_ohlcv(peer_sym, period="5d")
            day_change_pct = None
            if len(df.index) >= 2:
                latest_close = float(df.iloc[-1]["close"])
                prev_close = float(df.iloc[-2]["close"])
                if prev_close > 0:
                    day_change_pct = (latest_close - prev_close) / prev_close

            peers.append(
                {
                    "symbol": peer_sym,
                    "display_name": display_name,
                    "sector": peer_sector,
                    "day_change_percent": day_change_pct,
                }
            )
        return peers

    def fetch_sector_performance(self, symbol: str) -> dict[str, Any]:
        """Fetch sector performance metrics, constituent moves, and plain-English takeaway."""
        target_symbol = symbol.upper().strip()
        sector = get_stock_sector(target_symbol)

        sector_symbols = list(SECTOR_PEERS.get(sector, [target_symbol]))
        if target_symbol not in sector_symbols:
            sector_symbols.append(target_symbol)

        valid_changes = []
        peers = []
        target_change_pct = None

        for sym in sector_symbols:
            item_info = next((item for item in STOCK_CATALOG if item["symbol"] == sym), None)
            display_name = item_info["display_name"] if item_info else sym.removesuffix(".NS")

            df = self.fetch_daily_ohlcv(sym, period="5d")
            day_change_pct = None
            if len(df.index) >= 2:
                latest_close = float(df.iloc[-1]["close"])
                prev_close = float(df.iloc[-2]["close"])
                if prev_close > 0:
                    day_change_pct = (latest_close - prev_close) / prev_close
                    valid_changes.append(day_change_pct)

            if sym == target_symbol:
                target_change_pct = day_change_pct
            else:
                peers.append(
                    {
                        "symbol": sym,
                        "display_name": display_name,
                        "day_change_percent": day_change_pct,
                    }
                )

        sector_avg = (sum(valid_changes) / len(valid_changes)) if valid_changes else None

        takeaway = None
        target_info = next((item for item in STOCK_CATALOG if item["symbol"] == target_symbol), None)
        target_name = target_info["display_name"] if target_info else target_symbol.removesuffix(".NS")
        if target_change_pct is not None and sector_avg is not None:
            diff = target_change_pct - sector_avg
            target_sign = "+" if target_change_pct > 0 else ""
            sector_sign = "+" if sector_avg > 0 else ""
            target_str = f"{target_name} ({target_sign}{target_change_pct * 100:.2f}%)"
            sector_str = f"{sector} sector ({sector_sign}{sector_avg * 100:.2f}%)"

            if diff > 0.002:
                takeaway = f"{target_str} is outperforming the {sector_str} today."
            elif diff < -0.002:
                takeaway = f"{target_str} is underperforming the {sector_str} today."
            else:
                takeaway = f"{target_str} is performing in line with the {sector_str} today."

        return {
            "sector": sector,
            "sector_change_percent": sector_avg,
            "stock_change_percent": target_change_pct,
            "takeaway": takeaway,
            "peers": peers[:4],
        }

    def fetch_daily_ohlcv(
        self,
        symbol: str,
        *,
        period: str | None = DEFAULT_PERIOD,
        start: DateLike | None = None,
        end: DateLike | None = None,
    ) -> pd.DataFrame:
        ticker = (symbol or "").strip()
        if not ticker:
            return self._empty()

        try:
            raw = yf.Ticker(ticker).history(
                **self._history_kwargs(period=period, start=start, end=end),
                interval="1d",
                auto_adjust=False,
                timeout=10,
            )
        except Exception:
            return self._empty()

        return self._normalize(raw)

    def fetch_nifty50(
        self,
        *,
        period: str | None = DEFAULT_PERIOD,
        start: DateLike | None = None,
        end: DateLike | None = None,
    ) -> pd.DataFrame:
        return self.fetch_daily_ohlcv(
            NIFTY_50_SYMBOL,
            period=period,
            start=start,
            end=end,
        )

    def fetch_intraday_ohlcv(
        self,
        symbol: str,
        *,
        period: str = "5d",
        interval: str = "5m",
    ) -> pd.DataFrame:
        ticker = (symbol or "").strip()
        if not ticker:
            return pd.DataFrame(columns=INTRADAY_COLUMNS)

        try:
            raw = yf.Ticker(ticker).history(
                period=period,
                interval=interval,
                auto_adjust=False,
                timeout=10,
            )
        except Exception:
            return pd.DataFrame(columns=INTRADAY_COLUMNS)

        return self._normalize_intraday(raw)

    def validate_symbol(self, symbol: str) -> bool:
        """Validate if a ticker exists and returns data on Yahoo Finance."""
        ticker = (symbol or "").strip()
        if not ticker:
            raise ValueError("symbol is required")
        try:
            raw = yf.Ticker(ticker).history(period="5d", interval="1d", auto_adjust=False, timeout=10)
        except (TimeoutError, ConnectionError, OSError) as exc:
            raise RuntimeError(f"Network error validating symbol '{ticker}': {exc}") from exc
        except Exception:
            return False

        normalized = self._normalize(raw)
        return not normalized.empty

    def fetch_nifty50_intraday(
        self,
        *,
        period: str = "5d",
        interval: str = "5m",
    ) -> pd.DataFrame:
        return self.fetch_intraday_ohlcv(
            NIFTY_50_SYMBOL,
            period=period,
            interval=interval,
        )

    @staticmethod
    def _history_kwargs(
        *,
        period: str | None,
        start: DateLike | None,
        end: DateLike | None,
    ) -> dict[str, DateLike | str]:
        if start is not None or end is not None:
            kwargs: dict[str, DateLike | str] = {}
            if start is not None:
                kwargs["start"] = start
            if end is not None:
                kwargs["end"] = end
            return kwargs
        return {"period": period or DEFAULT_PERIOD}

    @staticmethod
    def _empty() -> pd.DataFrame:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    @staticmethod
    def _normalize(raw: pd.DataFrame | None) -> pd.DataFrame:
        if raw is None or raw.empty:
            return MarketDataService._empty()

        frame = raw.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        required = ["open", "high", "low", "close", "volume"]
        if any(column not in frame.columns for column in required):
            return MarketDataService._empty()

        dates = frame.index
        if getattr(dates, "tz", None) is not None:
            dates = dates.tz_convert("Asia/Kolkata").tz_localize(None)

        out = pd.DataFrame(
            {
                "date": pd.to_datetime(dates).normalize(),
                "open": pd.to_numeric(frame["open"], errors="coerce"),
                "high": pd.to_numeric(frame["high"], errors="coerce"),
                "low": pd.to_numeric(frame["low"], errors="coerce"),
                "close": pd.to_numeric(frame["close"], errors="coerce"),
                "volume": pd.to_numeric(frame["volume"], errors="coerce"),
            }
        )
        out = out.dropna(subset=["close"])
        return out.reset_index(drop=True)[OHLCV_COLUMNS]

    @staticmethod
    def _normalize_intraday(raw: pd.DataFrame | None) -> pd.DataFrame:
        empty = pd.DataFrame(columns=INTRADAY_COLUMNS)
        if raw is None or raw.empty:
            return empty

        frame = raw.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        required = ["open", "high", "low", "close", "volume"]
        if any(column not in frame.columns for column in required):
            return empty

        timestamps = frame.index
        if getattr(timestamps, "tz", None) is not None:
            timestamps = timestamps.tz_convert("UTC")
        else:
            timestamps = pd.to_datetime(timestamps).tz_localize("UTC")

        out = pd.DataFrame(
            {
                "timestamp": timestamps,
                "date": pd.to_datetime(timestamps).date,
                "open": pd.to_numeric(frame["open"], errors="coerce"),
                "high": pd.to_numeric(frame["high"], errors="coerce"),
                "low": pd.to_numeric(frame["low"], errors="coerce"),
                "close": pd.to_numeric(frame["close"], errors="coerce"),
                "volume": pd.to_numeric(frame["volume"], errors="coerce"),
            }
        )
        out = out.dropna(subset=["close"])
        return out.reset_index(drop=True)[INTRADAY_COLUMNS]


_service = MarketDataService()
fetch_daily_ohlcv = _service.fetch_daily_ohlcv
fetch_nifty50 = _service.fetch_nifty50
fetch_intraday_ohlcv = _service.fetch_intraday_ohlcv
fetch_nifty50_intraday = _service.fetch_nifty50_intraday

_configure_yfinance_cache()


