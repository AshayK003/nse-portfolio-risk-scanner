"""
Sample portfolio template generator.

Creates an .xlsx file matching the exact column format the parser accepts,
so users can download it, fill in their own holdings, and re-upload.
"""

from __future__ import annotations

import io

import pandas as pd

# Columns the parser recognizes (see engine/portfolio.py _COLUMN_ALIASES).
# We use the canonical names so the sample works out-of-the-box.
_SAMPLE_ROWS = [
    {"Ticker": "RELIANCE", "Name": "Reliance Industries Ltd", "Quantity": 10, "Avg Price": 1100.00},
    {"Ticker": "TCS", "Name": "Tata Consultancy Services Ltd", "Quantity": 5, "Avg Price": 1700.00},
    {"Ticker": "INFY", "Name": "Infosys Ltd", "Quantity": 20, "Avg Price": 850.00},
    {"Ticker": "ITC", "Name": "ITC Ltd", "Quantity": 50, "Avg Price": 240.00},
    {"Ticker": "ICICIBANK", "Name": "ICICI Bank Ltd", "Quantity": 30, "Avg Price": 1150.00},
    {"Ticker": "HDFCBANK", "Name": "HDFC Bank Ltd", "Quantity": 15, "Avg Price": 1650.00},
    {"Ticker": "NIFTYBEES", "Name": "Nippon India ETF Nifty 50 BeES", "Quantity": 100, "Avg Price": 240.00},
]


def build_sample_excel() -> bytes:
    """Return an .xlsx template with header + sample rows as bytes."""
    df = pd.DataFrame(_SAMPLE_ROWS)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Holdings")
    return buf.getvalue()
