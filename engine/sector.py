"""
NSE sector classification and concentration analysis.

Uses a static sector mapping for ticker→sector lookups.
Falls back to yfinance sector info when a ticker isn't in the mapping.
"""

from __future__ import annotations

import numpy as np

from . import Holding, SectorExposure

# Attempt to import nselib for sector data fallback (optional dep)
try:
    from nselib import capital_market

    _NSELIB_AVAILABLE = True
except ImportError:
    _NSELIB_AVAILABLE = False

# Default mapping for common NSE stocks
_DEFAULT_SECTORS: dict[str, str] = {
    # Nifty 50
    "RELIANCE": "Oil & Gas",
    "TCS": "IT",
    "HDFCBANK": "Banking",
    "INFY": "IT",
    "ICICIBANK": "Banking",
    "HINDUNILVR": "FMCG",
    "SBIN": "Banking",
    "BHARTIARTL": "Telecom",
    "ITC": "FMCG",
    "KOTAKBANK": "Banking",
    "LT": "Construction",
    "WIPRO": "IT",
    "AXISBANK": "Banking",
    "TITAN": "Consumer Durables",
    "BAJFINANCE": "Financial Services",
    "MARUTI": "Automobile",
    "SUNPHARMA": "Pharma",
    "NTPC": "Power",
    "ONGC": "Oil & Gas",
    "POWERGRID": "Power",
    "M&M": "Automobile",
    "HCLTECH": "IT",
    "ASIANPAINT": "Consumer Durables",
    "TATASTEEL": "Metals & Mining",
    "ULTRACEMCO": "Construction Materials",
    "TRENT": "Retail",
    "NESTLE": "FMCG",
    "BAJAJ-AUTO": "Automobile",
    "BAJAJFINSV": "Financial Services",
    "COALINDIA": "Metals & Mining",
    "ADANIPORTS": "Infrastructure",
    "HINDALCO": "Metals & Mining",
    "CIPLA": "Pharma",
    "BEL": "Defense",
    "JSWSTEEL": "Metals & Mining",
    "TATAMOTORS": "Automobile",
    "EICHERMOT": "Automobile",
    "BRITANNIA": "FMCG",
    "DLF": "Real Estate",
    "SHRIRAMFIN": "Financial Services",
    "GRASIM": "Textiles",
    "HEROMOTOCO": "Automobile",
    "ADANIGREEN": "Power",
    "INDUSINDBK": "Banking",
    "ABB": "Capital Goods",
    "SIEMENS": "Capital Goods",
    "BPCL": "Oil & Gas",
    "HDFCLIFE": "Insurance",
    "SBILIFE": "Insurance",
    # Non-Nifty but common
    "VEDL": "Metals & Mining",
    "IEX": "Power",
    "IDEA": "Telecom",
    "YESBANK": "Banking",
    "PNB": "Banking",
    "BANKBARODA": "Banking",
    "CANBK": "Banking",
    "IRCTC": "Infrastructure",
    "ZOMATO": "Internet",
    "PAYTM": "Internet",
    "NYKAA": "Retail",
    "DIXON": "Consumer Durables",
    "POLYCAB": "Capital Goods",
    "HAVELLS": "Capital Goods",
    "TVSMOTOR": "Automobile",
    "ASHOKLEY": "Automobile",
    "MCDOWELL-N": "FMCG",
    "DABUR": "FMCG",
    "MARICO": "FMCG",
    "COLPAL": "FMCG",
    "PIDILITIND": "Chemicals",
    "SRF": "Chemicals",
    "DIVISLAB": "Pharma",
    "DRREDDY": "Pharma",
    "APOLLOHOSP": "Healthcare",
    "GAIL": "Oil & Gas",
    "IOC": "Oil & Gas",
    "HAL": "Defense",
    "GODREJCP": "FMCG",
    "AMBUJACEM": "Construction Materials",
    "JSWENERGY": "Power",
    "TATAPOWER": "Power",
    "ADANIENSOL": "Power",
    "INOXWIND": "Power",
    "SUZLON": "Power",
    "NHPC": "Power",
    "LICHSGFIN": "Financial Services",
    "MUTHOOTFIN": "Financial Services",
    "PEL": "Financial Services",
    "HINDZINC": "Metals & Mining",
    "NATIONALUM": "Metals & Mining",
    "TORNTPHARM": "Pharma",
    "LUPIN": "Pharma",
    "AUROPHARMA": "Pharma",
    "BIOCON": "Pharma",
    "MANKIND": "Pharma",
    "MAXHEALTH": "Healthcare",
    "FORTIS": "Healthcare",
    "PAGEIND": "Textiles",
    "TECHM": "IT",
    "LTIM": "IT",
    "MPHASIS": "IT",
    "PERSISTENT": "IT",
    "COFORGE": "IT",
    "ZENSARTECH": "IT",
    "BSE": "Financial Services",
    "NSE": "Financial Services",
    "CDSL": "Financial Services",
    "HDFCAMC": "Financial Services",
    "MFSL": "Insurance",
    "ICICIPRULI": "Insurance",
    "CHOLAFIN": "Financial Services",
    "BAJAJHLDNG": "Financial Services",
    "GODREJPROP": "Real Estate",
    "OBEROIRLTY": "Real Estate",
    "PHOENIXLTD": "Real Estate",
    "SONACOMS": "Automobile",
    "BOSCHLTD": "Automobile",
    "CUB": "Banking",
    "FEDERALBNK": "Banking",
    "IDFCFIRSTB": "Banking",
    "RBLBANK": "Banking",
    "AUBANK": "Banking",
    "BANDHANBNK": "Banking",
    # ETFs
    "NIFTYBEES": "ETF",
    "NEXT50IETF": "ETF",
    "MIDCAPETF": "ETF",
    "HDFCSML250": "ETF",
    "ENERGY": "ETF",
    "MODEFENCE": "ETF",
    "MAKEINDIA": "ETF",
    "GOLDBEES": "ETF",
    "METALETF": "ETF",
    "MON100": "ETF",
    "MOM100": "ETF",
    "QNIFTY": "ETF",
    "LIQUIDBEES": "ETF",
    "BANKBEES": "ETF",
}


def load_sector_map() -> dict[str, str]:
    """Return the default ticker-to-sector mapping."""
    return dict(_DEFAULT_SECTORS)


def classify_holdings(
    holdings: list[Holding],
    sector_map: dict[str, str] | None = None,
) -> list[Holding]:
    """
    Assign sector to each holding using the provided mapping.
    Falls back to nselib or yfinance for unknown tickers.
    """
    if sector_map is None:
        sector_map = load_sector_map()

    result = []
    for h in holdings:
        clean_ticker = h.ticker.replace(".NS", "")
        sector = sector_map.get(clean_ticker, "")

        if not sector and _NSELIB_AVAILABLE:
            try:
                raw = capital_market.price_volume_data(symbol=clean_ticker, period="1d")
                if raw is not None and not raw.empty and "SECTOR" in raw.columns:
                    sector = str(raw.iloc[0].get("SECTOR", ""))
            except Exception:
                pass

        if not sector:
            try:
                import yfinance as yf

                info = yf.Ticker(h.ticker).info
                sector = info.get("sector", "")
            except Exception:
                sector = "Unknown"

        h.sector = sector or "Unknown"
        result.append(h)

    return result


def compute_sector_exposure(holdings: list[Holding]) -> SectorExposure:
    """
    Compute sector concentration metrics from classified holdings.
    """
    total_value = sum(h.current_value for h in holdings)
    if total_value == 0:
        return SectorExposure(
            holdings=holdings,
            sector_allocation={},
            concentrated_sectors=[],
            diversification_score=0.0,
            herfindahl_index=0.0,
        )

    # Aggregate by sector
    sector_values: dict[str, float] = {}
    for h in holdings:
        sec = h.sector or "Unknown"
        sector_values[sec] = sector_values.get(sec, 0) + h.current_value

    # Compute percentages
    sector_alloc = {sec: round(val / total_value * 100, 1) for sec, val in sector_values.items()}
    sector_alloc = dict(sorted(sector_alloc.items(), key=lambda x: x[1], reverse=True))

    # Concentrated sectors (>20%)
    concentrated = [sec for sec, pct in sector_alloc.items() if pct > 20]

    # Diversification score (0-100)
    # Inverse Herfindahl-Hirschman Index normalized
    weights = np.array(list(sector_alloc.values())) / 100
    hhi = (weights**2).sum()
    div_score = max(0, min(100, (1 - hhi) * 100))

    return SectorExposure(
        holdings=holdings,
        sector_allocation=sector_alloc,
        concentrated_sectors=concentrated,
        diversification_score=round(div_score, 1),
        herfindahl_index=round(hhi, 3),
    )
