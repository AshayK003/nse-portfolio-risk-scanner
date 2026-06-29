# NSE Portfolio Risk Scanner - Open-Source Ecosystem Research

**Date:** June 18, 2026
**Purpose:** Identify the best free/open-source libraries, patterns, and architectures for building the NSE Portfolio Risk Scanner.

---

## 1. Data Layer (NSE Stock Data)

### 🥇 yfinance (ranaroussi/yfinance)
| Metric | Value |
|--------|-------|
| **Stars** | 24.3k |
| **Last commit** | 3 weeks ago (v1.4.1) |
| **License** | Apache 2.0 |
| **Status** | ✅ ACTIVE |

**Why it matters:** Already powering Tool #1 (NSE Sentiment Analyzer). NSE stocks work by appending `.NS` (e.g., `RELIANCE.NS`, `HDFCBANK.NS`). No API key, no registration, pure Python.

**Tradeoffs:**
- Unofficial Yahoo Finance API (could break if Yahoo changes things)
- Rate-limited for bulk historical data (manageable with delays)
- `.NS` suffix mapping requires pre-processing user's stock names (e.g., "RELIANCE" -> "RELIANCE.NS")

**Integration:** Already installed in your env. `pip install yfinance`.

**What it solves:** One-line data fetch for any NSE stock's OHLCV and fundamental data. No alternative comes close in simplicity and reliability.

---

### ❌ nsepy (swapniljariwala/nsepy) — SKIP
802 stars, **3 years since last commit**. DEAD. NSE changed their website structure multiple times since. Broken.

### ❌ nsetools — SKIP
Historically popular but NSE actively blocks scraping now. The API endpoints used by this library have been deprecated.

### 💡 Approach: yfinance + Nifty 50 benchmark
Use yfinance exclusively. Maintain a static NSE symbol mapping for the Nifty 50 and common stocks. User's portfolio CSV uses plain ticker names (e.g., "RELIANCE") which get converted to `RELIANCE.NS` internally.

---

## 2. Portfolio Risk / Analytics Libraries

### 🥇 quantstats (ranaroussi/quantstats)
| Metric | Value |
|--------|-------|
| **Stars** | 7.3k |
| **Last commit** | 5 months ago (v0.0.78) |
| **License** | Apache 2.0 |
| **Status** | ✅ ACTIVE |

**Why it matters:** Purpose-built for portfolio performance reporting. Generates a comprehensive report with: Sharpe ratio, Sortino ratio, max drawdown, Calmar ratio, Value at Risk, alpha, beta, volatility, CAGR, and comparative plots against a benchmark.

**Tradeoffs:**
- Generates HTML reports (good for export, but we want interactive Streamlit)
- Heavy-ish dependency tree (matplotlib, seaborn, scipy)
- Some metrics tuned for US market conventions (risk-free rate default = 0, vs India's ~6.5%)
- Last release 5 months ago, but development seems stable

**What it solves:** Would give us a ready-made "Download Risk Report (PDF/HTML)" feature. We can cherry-pick the computation functions and build our own Streamlit UI around them.

**Recommendation:** USE the calculation functions internally (`quantstats.stats.*`) but NOT the reporting/plotting modules. Build our own Streamlit views.

---

### 🥈 riskfolio-lib (dcajasn/Riskfolio-Lib)
| Metric | Value |
|--------|-------|
| **Stars** | 4.3k |
| **Last commit** | 2 weeks ago (v7.3) |
| **License** | MIT |
| **Status** | ✅ VERY ACTIVE |

**Why it matters:** The most comprehensive Python portfolio optimization library. Supports mean-variance, Black-Litterman, Hierarchical Risk Parity (HRP), CVaR optimization, and Monte Carlo VaR. Excellent documentation with Jupyter notebooks.

**Tradeoffs:**
- **Overkill for this app.** This is designed for portfolio CONSTRUCTION (finding optimal weights), not portfolio RISK ANALYSIS (measuring risk of an existing portfolio).
- Large dependency footprint (cvxpy, scipy, matplotlib, pandas)
- The HRP and optimization algorithms require significant computation for a Streamlit app
- Too many features = confusing UX for a ₹199 tool

**What it solves:** If you ever add portfolio optimization (e.g., "suggest optimal allocation to match my current risk"), this is the library.

**Recommendation:** SKIP for v1. Keep in mind for v2 (portfolio optimization feature).

---

### 🥉 PyPortfolioOpt (robertmartin8/PyPortfolioOpt)
| Metric | Value |
|--------|-------|
| **Stars** | 5.8k |
| **Last commit** | 3 months ago |
| **License** | MIT |
| **Status** | ✅ ACTIVE |

**Why it matters:** Clean, well-documented, textbook-style implementation of Modern Portfolio Theory. Efficient frontier, Black-Litterman, HRP support.

**Tradeoffs:** Same as riskfolio-lib — it's for portfolio construction, not risk measurement. Less comprehensive than riskfolio-lib.

**Recommendation:** SKIP for v1.

---

### ❌ pyfolio (quantopian/pyfolio) — SKIP
6.3k stars but **6 years since last commit**. DEAD. Quantopian shut down. The code is useful as a reference for metrics implementation, but cannot be used as a dependency.

### ❌ empyrical (quantopian/empyrical) — SKIP
1.5k stars, **6 years since last commit**. DEAD. The statistical functions are trivial to reimplement.

---

## 3. NSE Sector Classification

### 🗺️ Approach: Static Mapping
NSE stocks have sector classifications (Banking, IT, Pharma, Auto, etc.). There's no reliable maintained open-source library for this.

**Strategy:** Maintain a hand-curated mapping for the ~200 most common NSE stocks. This is a one-time effort and gives you full control. Source from:
- NSE's own sector indices (Nifty Bank, Nifty IT, Nifty Pharma, etc.)
- Moneycontrol / Screener sector tags
- BSE sector classification

For the MVP, support the Nifty 50 sectors (comprehensive mapping can be a v2 feature). User's portfolio will mostly contain these stocks.

---

## 4. VaR & Risk Computation — Implementation Strategy

### ⚡ Verdict: Write our own with numpy/scipy

The core risk calculations are **1-3 lines** of numpy. Pulling in a library for these is dependency bloat that hurts maintainability.

| Metric | Formula | Complexity |
|--------|---------|------------|
| **Volatility** | `std(returns) * sqrt(252)` | 1 line |
| **VaR (95%)** | `percentile(returns, 5)` | 1 line |
| **CVaR** | `mean(returns[returns <= VaR])` | 1 line |
| **Beta** | `cov(returns, benchmark) / var(benchmark)` | 1 line |
| **Max Drawdown** | `min(cummax(cum_returns) - cum_returns)` | 2 lines |
| **Sharpe Ratio** | `(mean_return - rf) / std(returns)` | 1 line |
| **Sortino Ratio** | `(mean_return - rf) / std(negative_returns)` | 2 lines |
| **Sector Concentration** | Group by sector, calc % of total value | 3 lines |

**Total:** ~20 lines of numpy/pandas for ALL risk metrics. No library needed.

**Reference implementations to study:**
- quantstats source: `quantstats/stats.py` — clean, MIT-licensed implementations
- empyrical source: `empyrical/stats.py` — reference-level implementation
- pyfolio source: `pyfolio/tears.py` — good for understanding the report structure

---

## 5. Streamlit UI / Architecture Patterns

### 🥇 Native Streamlit + Plotly
**Stack:** `streamlit` + `plotly` + `pandas` + `numpy`

**Why:** Streamlit's native components (st.data_editor, st.dataframe, st.columns, st.tabs, st.metric) are sufficient for v1. Plotly handles all interactive charts. No need for ag-Grid or custom components.

**UI Pattern:**
```
CSV Upload (st.file_uploader)
  → st.data_editor (editable preview table)
  → Fetch prices via yfinance
  → Compute metrics
  → Display:
     ├── Portfolio Summary (st.metric cards)
     ├── Risk Dashboard (Plotly gauge charts)
     ├── Sector Breakdown (Plotly treemap/pie)
     ├── Drawdown Analysis (Plotly area chart)
     ├── Individual Stock Risk (st.dataframe with colored cells)
     └── Export Report (st.download_button → CSV/PDF)
```

### 🥈 Streamlit Theming
- Streamlit has built-in light/dark mode
- Use `st.set_page_config(layout="wide")` for professional look
- Custom CSS via `st.markdown(f"<style>...</style>")` for Indian color palette (saffron/green/blue)

### ❌ Heavy Components to AVOID
- **st-aggrid**: Requires separate installation, React dependency, overkill for CSV editing
- **streamlit-plotly-events**: Not needed for v1
- **streamlit-authenticator**: Not needed (no auth for ₹199 tool)
- **streamlit-folium**: Not needed (no map visualization)

---

## 6. Proposed Tech Stack (v1)

| Layer | Library | Why |
|-------|---------|-----|
| **Data** | yfinance | Only viable option for NSE prices |
| **Computation** | numpy + pandas + scipy | Write our own (20 lines total) |
| **UI** | streamlit + plotly | Proven, lightweight, interactive |
| **CSV handling** | pandas | Built into Streamlit |
| **PDF Export** | weasyprint or fpdf | Lightweight, no LaTeX needed |
| **Sector data** | Static YAML/JSON mapping | Authoritative, no dependency |
| **Hosting** | Streamlit Community Cloud | Free tier, works perfectly |

**Total Python dependencies:** ~8 (yfinance, streamlit, plotly, numpy, pandas, scipy, fpdf, pyyaml)

---

## 7. Reference Architectures (Open-Source Repos)

### To Learn From (not clone)
These repos demonstrate portfolio analysis in Streamlit — study their patterns but don't reuse code:

1. **shiv-rna/Investment-Portfolio-AI-Agent** (13 stars)
   - Streamlit + AI agent for portfolio analysis
   - Good: clean separation of compute layer from UI
   - Bad: adds LLM complexity where not needed

2. **abhaypaii/risk-analysis-app** (1 star)
   - Streamlit + yfinance + portfolio risk
   - Good: basic risk metric computation structure
   - Bad: small, incomplete

3. **eudouglasnery/riskcontrol** (5 stars)
   - Risk dashboard + Markowitz optimization
   - Good: Plotly visualization patterns
   - Bad: Not NSE-specific

**None of these are production-ready or NSE-specific. You're breaking new ground for the Indian market.**

---

## 8. Recommendations Summary

| Component | Recommendation | Confidence |
|-----------|---------------|------------|
| Price data | **yfinance** (.NS suffix) | ✅ Strong |
| Risk metrics | **Write our own** (numpy/scipy) | ✅ Strong |
| Sector mapping | **Static JSON file** | ✅ Strong |
| Charts | **Plotly** via Streamlit | ✅ Strong |
| CSV upload/edit | **st.file_uploader + st.data_editor** | ✅ Strong |
| Report export | **fpdf** (PDF) or **st.download_button** (CSV) | ✅ Strong |
| Portfolio optimization | **Not in v1** (defer to riskfolio-lib for v2) | ✅ Strong |
| Backtesting | **Not in v1** (defer to vectorbt for v2) | ✅ Strong |

### What NOT to use (hype / abandoned / overkill):
- ❌ nsepy — dead (3 years stale)
- ❌ nsetools — dead (NSE blocks scraping)
- ❌ pyfolio — dead (6 years stale)
- ❌ empyrical — dead (6 years stale)
- ❌ QuantLib — C++, 50x overkill
- ❌ Qlib — Microsoft's AI quant platform, overkill for risk reporting
- ❌ OpenBB — whole terminal platform, dependencies nightmare
- ❌ Lean/QuantConnect — C# algorithmic trading engine

### Key Insight
The "moat" of 2/6 is too conservative. **The real moat is that this tool speaks NSE natively** (sector classifications, Indian risk-free rate, Nifty 50 benchmark, INR formatting). No global portfolio tool does this well. Combined with CSV upload (ChatGPT can't see your Zerodha portfolio), this is stronger than 2/6.
