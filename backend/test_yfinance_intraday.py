"""Test live yfinance intraday data retrieval for NSE symbols and NIFTY 50."""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from market_data import fetch_intraday_ohlcv, fetch_nifty50_intraday


def test_intraday():
    print("Testing fetch_intraday_ohlcv for RELIANCE.NS...")
    df_rel = fetch_intraday_ohlcv("RELIANCE.NS", period="5d", interval="5m")
    print(f"RELIANCE.NS intraday shape: {df_rel.shape}")
    if not df_rel.empty:
        print("RELIANCE.NS columns:", list(df_rel.columns))
        print("RELIANCE.NS sample head:")
        print(df_rel.head(2))
        print("RELIANCE.NS sample tail:")
        print(df_rel.tail(2))

    print("\nTesting fetch_nifty50_intraday...")
    df_nifty = fetch_nifty50_intraday(period="5d", interval="5m")
    print(f"NIFTY 50 intraday shape: {df_nifty.shape}")
    if not df_nifty.empty:
        print("NIFTY 50 sample head:")
        print(df_nifty.head(2))
        print("NIFTY 50 sample tail:")
        print(df_nifty.tail(2))

    assert not df_rel.empty, "RELIANCE.NS intraday data should not be empty"
    assert not df_nifty.empty, "NIFTY 50 intraday data should not be empty"
    assert "timestamp" in df_rel.columns
    assert "close" in df_rel.columns
    print("\nIntraday test PASSED successfully!")


if __name__ == "__main__":
    test_intraday()
