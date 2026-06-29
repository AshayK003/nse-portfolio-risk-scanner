"""
SQLite database manager for portfolio persistence and analysis history.

Schema Management:
- Versioned with a single integer in schema_version table
- WAL mode for concurrent read performance
- Raw sqlite3 with parameterized queries (no ORM)

Tables:
  - saved_portfolios: Named portfolio snapshots
  - price_cache: Cross-session price data (TTL-managed)
  - analysis_runs: History of analysis runs for trend tracking
"""
from __future__ import annotations
import os
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Optional

from .models import SavedPortfolio, AnalysisRun, CachedPrice

# Default database path (relative to project root)
_DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_DEFAULT_DB_PATH = os.path.join(_DEFAULT_DB_DIR, "nse_risk_scanner.db")

# Current schema version — bump on schema changes
_SCHEMA_VERSION = 1

# Thread-local connections for thread safety
_local = threading.local()


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get a thread-local SQLite connection with WAL mode."""
    path = db_path or _DEFAULT_DB_PATH

    # Ensure directory exists
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Thread-local connection
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn

        # Ensure schema
        _ensure_schema(conn)

    return conn


def close_connection():
    """Close the thread-local connection if open."""
    conn = getattr(_local, "conn", None)
    if conn:
        conn.close()
        _local.conn = None


def _ensure_schema(conn: sqlite3.Connection):
    """Create or migrate the database schema."""
    # Check current version
    version = 0
    try:
        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if row:
            version = row["version"]
    except sqlite3.OperationalError:
        pass

    if version >= _SCHEMA_VERSION:
        return

    # Create schema tables
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS saved_portfolios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            holdings_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            total_invested REAL DEFAULT 0,
            total_current REAL DEFAULT 0,
            total_pnl REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS price_cache (
            ticker TEXT NOT NULL,
            date TEXT NOT NULL,
            close REAL NOT NULL,
            fetched_at TEXT NOT NULL,
            PRIMARY KEY (ticker, date)
        );

        CREATE INDEX IF NOT EXISTS idx_price_cache_ticker ON price_cache(ticker);
        CREATE INDEX IF NOT EXISTS idx_price_cache_fetched ON price_cache(fetched_at);

        CREATE TABLE IF NOT EXISTS analysis_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            portfolio_name TEXT NOT NULL,
            holding_count INTEGER DEFAULT 0,
            volatility REAL DEFAULT 0,
            var_95 REAL DEFAULT 0,
            max_drawdown REAL DEFAULT 0,
            sharpe REAL DEFAULT 0,
            cagr REAL DEFAULT 0,
            beta REAL DEFAULT 0,
            diversification_score REAL DEFAULT 0,
            benchmark_name TEXT DEFAULT 'NIFTY 50',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_analysis_created ON analysis_runs(created_at);
    """)

    # Update version
    if version == 0:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (_SCHEMA_VERSION,))
    else:
        conn.execute("UPDATE schema_version SET version = ?", (_SCHEMA_VERSION,))
    conn.commit()


# ── Portfolio CRUD ──

def save_portfolio(portfolio: SavedPortfolio) -> int:
    """Insert or update a saved portfolio. Returns the portfolio ID."""
    conn = get_connection()
    now = datetime.now().isoformat()
    portfolio.updated_at = now

    if portfolio.id:
        conn.execute("""
            UPDATE saved_portfolios
            SET name=?, holdings_json=?, updated_at=?, total_invested=?,
                total_current=?, total_pnl=?
            WHERE id=?
        """, (
            portfolio.name, portfolio.holdings_json, now,
            portfolio.total_invested, portfolio.total_current, portfolio.total_pnl,
            portfolio.id,
        ))
        conn.commit()
        return portfolio.id
    else:
        portfolio.created_at = now
        cursor = conn.execute("""
            INSERT INTO saved_portfolios
                (name, holdings_json, created_at, updated_at,
                 total_invested, total_current, total_pnl)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            portfolio.name, portfolio.holdings_json, now, now,
            portfolio.total_invested, portfolio.total_current, portfolio.total_pnl,
        ))
        conn.commit()
        portfolio.id = cursor.lastrowid
        return cursor.lastrowid


def load_portfolio(portfolio_id: int) -> Optional[SavedPortfolio]:
    """Load a saved portfolio by ID."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM saved_portfolios WHERE id = ?", (portfolio_id,)
    ).fetchone()
    if row is None:
        return None
    return SavedPortfolio(**dict(row))


def list_saved_portfolios() -> list[SavedPortfolio]:
    """List all saved portfolios, newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM saved_portfolios ORDER BY updated_at DESC"
    ).fetchall()
    return [SavedPortfolio(**dict(r)) for r in rows]


def delete_portfolio(portfolio_id: int) -> bool:
    """Delete a saved portfolio. Returns True if deleted."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM saved_portfolios WHERE id = ?", (portfolio_id,))
    conn.commit()
    return cursor.rowcount > 0


# ── Analysis History ──

def save_analysis_run(run: AnalysisRun) -> int:
    """Record an analysis run. Returns the run ID."""
    conn = get_connection()
    cursor = conn.execute("""
        INSERT INTO analysis_runs
            (portfolio_name, holding_count, volatility, var_95, max_drawdown,
             sharpe, cagr, beta, diversification_score, benchmark_name, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        run.portfolio_name, run.holding_count, run.volatility, run.var_95,
        run.max_drawdown, run.sharpe, run.cagr, run.beta,
        run.diversification_score, run.benchmark_name, run.created_at,
    ))
    conn.commit()
    return cursor.lastrowid


def list_recent_analyses(limit: int = 10) -> list[AnalysisRun]:
    """Get the most recent analysis runs."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM analysis_runs ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [AnalysisRun(**dict(r)) for r in rows]


# ── Price Cache ──

def get_cached_prices(ticker: str, max_age_hours: int = 24) -> Optional[list[CachedPrice]]:
    """Get cached price data for a ticker if within TTL."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    rows = conn.execute(
        "SELECT * FROM price_cache WHERE ticker = ? AND fetched_at > ? ORDER BY date",
        (ticker, cutoff),
    ).fetchall()
    if not rows:
        return None
    return [CachedPrice(**dict(r)) for r in rows]


def save_cached_prices(ticker: str, prices: list[CachedPrice]):
    """Save price data for a ticker (upsert)."""
    conn = get_connection()
    now = datetime.now().isoformat()
    conn.executemany(
        """INSERT OR REPLACE INTO price_cache (ticker, date, close, fetched_at)
           VALUES (?, ?, ?, ?)""",
        [(p.ticker, p.date, p.close, now) for p in prices],
    )
    conn.commit()


def clear_stale_cache(max_age_hours: int = 48):
    """Remove cached entries older than max_age_hours."""
    conn = get_connection()
    cutoff = (datetime.now() - timedelta(hours=max_age_hours)).isoformat()
    conn.execute("DELETE FROM price_cache WHERE fetched_at < ?", (cutoff,))
    conn.commit()


def clear_ticker_cache(ticker: str):
    """Remove cached prices for a specific ticker (force refresh)."""
    conn = get_connection()
    conn.execute("DELETE FROM price_cache WHERE ticker = ?", (ticker,))
    conn.commit()


def clear_all_cache():
    """Remove all cached price data."""
    conn = get_connection()
    conn.execute("DELETE FROM price_cache")
    conn.commit()
