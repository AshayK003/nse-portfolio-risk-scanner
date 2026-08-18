"""
News section for portfolio holdings.

Fetches recent news headlines for each holding (and the benchmark) via the
Yahoo Finance RSS feed. Cached per ticker so re-renders don't re-hit the
network. Each item links to the original source.

No API key required — uses the public Yahoo Finance RSS endpoint.
"""

from __future__ import annotations

import urllib.parse

import streamlit as st

from engine import Portfolio

_RSS_TEMPLATE = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}"


@st.cache_data(ttl=1800, show_spinner=False, max_entries=64)
def fetch_news(ticker: str, limit: int = 6) -> list[dict]:
    """Fetch recent news for one ticker from Yahoo Finance RSS.

    Returns a list of dicts: {title, link, published, source}.
    Empty list on failure (RSS endpoint down, no news, rate-limited).
    """
    try:
        import feedparser
    except ImportError:
        return []
    symbol = f"{ticker}.NS" if not ticker.endswith(".NS") else ticker
    url = _RSS_TEMPLATE.format(symbol=urllib.parse.quote(symbol))
    try:
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:limit]:
            items.append(
                {
                    "title": entry.get("title", "Untitled"),
                    "link": entry.get("link", "#"),
                    "published": entry.get("published", ""),
                    "source": entry.get("source", {}).get("title", "")
                    if isinstance(entry.get("source"), dict)
                    else "",
                }
            )
        return items
    except (AttributeError, KeyError, ValueError, TypeError):
        return []


def render_news_section(portfolio: Portfolio):
    """Render the News tab content."""
    st.subheader("Latest News")
    st.caption(
        "Recent headlines for your holdings, pulled from Yahoo Finance RSS. "
        "Click any headline to read the full article."
    )

    holdings = portfolio.holdings
    if not holdings:
        st.info("Add holdings to see related news.")
        return

    # Aggregate news across all holdings, de-duplicated by title
    seen = set()
    aggregated = []
    for h in holdings:
        items = fetch_news(h.ticker.replace(".NS", ""))
        for it in items:
            if it["title"] not in seen:
                seen.add(it["title"])
                it["ticker"] = h.ticker.replace(".NS", "")
                aggregated.append(it)

    if not aggregated:
        st.info(
            "No news available right now. The Yahoo Finance RSS feed may be "
            "rate-limited or temporarily unavailable."
        )
        return

    # Show as a clean list with source + date
    for item in aggregated[:20]:
        title = item["title"]
        link = item["link"]
        src = item.get("source", "")
        published = item.get("published", "")
        ticker_tag = item.get("ticker", "")

        meta = " · ".join(p for p in [ticker_tag, src, published] if p)
        st.markdown(
            f"**<a href='{link}' target='_blank' rel='noopener'>{title}</a>**  "
            f"<span style='color: var(--text-muted); font-size: 0.8rem;'>{meta}</span>",
            unsafe_allow_html=True,
        )
        st.divider()
