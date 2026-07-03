# PDF Report Redesign — NSE Portfolio Risk Scanner

> Using pdf-studio v0.1.0 natively. Three minor additions to pdf-studio, then a clean build from scratch.

---

## Phase 0: Two ponytail additions to pdf-studio

Before the redesign, two small features needed in pdf-studio itself. Each is 1-3 lines.

### 0a. `doc.add_page_break()`

Enables explicit section breaks so 1. Executive Summary starts on page 2, 2. Risk Analysis on page 3, etc.

**`document.py`** — add method:
```python
def add_page_break(self) -> None:
    self._elements.append(("page_break",))
```

**`render.py`** — add to `_build_story()` dispatch:
```python
elif etype == "page_break":
    from reportlab.platypus import PageBreak
    story.append(PageBreak())
```

### 0b. `doc.add_bullet(text, style=None)`

Enables clean bullet points for recommendations instead of prefixing "• " in each paragraph.

**`document.py`** — add method:
```python
def add_bullet(self, text: str, style: Style | None = None) -> None:
    self._elements.append(("bullet", text, style or _default_style()))
```

**`render.py`** — add to `_build_story()` dispatch:
```python
elif etype == "bullet":
    _, text, style = el
    from reportlab.platypus import ListFlowable, ListItem
    p = Paragraph(text, _to_reportlab_style(style))
    story.append(ListFlowable([ListItem(p, bulletColor=colors.HexColor("#1a1a1a"))], bulletType='bullet', start=None, bulletFontSize=style.font.size * 0.7))
```

---

## Phase 1: Complete 4-page report design

### Global styling

| Element | Font | Size | Weight | Spacing |
|---------|------|------|--------|---------|
| Page header (every page) | Inter | 8 | Regular | Navy bar, white text |
| Section heading (h1) | Inter | 18 | Bold | before=16, after=8 |
| Subsection (h2) | Inter | 14 | Bold | before=12, after=6 |
| Body text | Inter | 9 | Regular | before=2, after=4 |
| Disclaimer | Inter | 7 | Italic | before=12, center |
| Table cells | Inter | 8 | Regular | 4px padding |

Theme colors: Navy `#1a3c6e`, Dark text `#1a1a1a`, Muted `#6b7280`, Light bg `#f4f6f9`

---

### Page 1: Cover

```
┌──────────────────────────────────────────────────┐
│  [ matplotlib figure — brand block ]              │  ← fills top ~3in
│  ┌──────────────────────────────────────────┐     │
│  │   NSE Portfolio Risk Report              │     │  20pt bold white
│  │   Portfolio Name                         │     │  13pt white
│  │   03 July 2026                           │     │  9pt muted white
│  └──────────────────────────────────────────┘     │
├──────────────────────────────────────────────────┤
│  [ pdf-studio table — portfolio summary ]         │  ← compact, no header row
│  ┌────────────┬──────────┬───────────┬──────────┐ │
│  │ Holdings   │   15     │ Invested  │ Rs 1.37L │ │  alternating bg
│  │ Value      │ Rs 1.39L │ P&L       │ +Rs 1,150│ │
│  │ P&L %      │  +0.84%  │ Sharpe    │ 1.05     │ │
│  └────────────┴──────────┴───────────┴──────────┘ │
├──────────────────────────────────────────────────┤
│  [ pdf-studio heading h2 ] Risk Assessment        │
├──────────────────────────────────────────────────┤
│  [ matplotlib figure — risk gauge + text ]        │  ← composite figure
│  ┌──────────────────────────────────────────┐     │
│  │  Low ██████████████░░░░░░░░ Mod ░░ High  │     │
│  │           18.5% ▴                         │     │
│  │  Risk Level: LOW — low volatility with   │     │
│  │  strong risk-adjusted returns.           │     │
│  └──────────────────────────────────────────┘     │
├──────────────────────────────────────────────────┤
│  [ pdf-studio paragraph — italic muted ]          │
│  Report generated: 03 Jul 2026, 12:54 PM          │
└──────────────────────────────────────────────────┘

   ── page break ──
```

**Implementation:**
1. `cover_banner = _cover_banner_figure(portfolio, plt)` → matplotlib figure, 6.3in × 2.5in, navy block with text
2. `doc.add_chart(cover_banner)` → adds it as vector SVG
3. `doc.add_paragraph("Portfolio Summary", style=Style(...))` → subtitle
4. `doc.add_table(metrics_df, caption=None)` → 4-column compact table (no header row, or use a minimal one)
5. `doc.add_heading("Risk Assessment", level=2)`
6. `gauge = _gauge_figure(risk, plt)` → composite matplotlib figure with gauge bar + assessment text
7. `doc.add_chart(gauge)`
8. `doc.add_paragraph("Report generated: ...", style=Style(...italic, muted, center...))`
9. `doc.add_page_break()`

---

### Page 2: Executive Summary

```
┌──────────────────────────────────────────────────┐
│  (page header: "NSE Portfolio Risk Report")       │  ← set_header("NSE Portfolio Risk Report")
├──────────────────────────────────────────────────┤
│  [ pdf-studio heading h1 ] 1. Executive Summary   │
├──────────────────────────────────────────────────┤
│  [ pdf-studio table — key metrics ]              │
│  ┌────────────┬──────────┬───────────┬──────────┐ │
│  │ Metric     │ Value    │ Metric    │ Value     │ │  ← proper header row
│  ├────────────┼──────────┼───────────┼──────────┤ │
│  │ Holdings   │   15     │ Invested  │ Rs 1.37L │ │
│  │ Value      │ Rs 1.39L │ P&L       │ +1,150   │ │
│  │ P&L %      │ +0.84%   │ Sharpe    │ 1.05     │ │
│  │ Sortino    │ 1.60     │ Beta      │ 0.92     │ │
│  │ CAGR       │ 14.2%    │ VaR (95%) │ -2.8%    │ │
│  └────────────┴──────────┴───────────┴──────────┘ │
├──────────────────────────────────────────────────┤
│  [ pdf-studio paragraph — assessment text ]       │
│  Annual volatility at 18.5% with a Sharpe of      │
│  1.05 indicates adequate risk-adjusted returns.   │
├──────────────────────────────────────────────────┤
│  [ matplotlib figure — sector + weight side-by-side ]│  ← composite with 2 subplots
│  ┌──────────┐ ┌──────────┐                        │
│  │ Pie      │ │ Bar      │                        │
│  │ chart    │ │ chart    │                        │
│  └──────────┘ └──────────┘                        │
└──────────────────────────────────────────────────┘

   ── page break ──
```

---

### Page 3: Risk Analysis

```
┌──────────────────────────────────────────────────┐
│  [ pdf-studio heading h1 ] 2. Risk Analysis       │
├──────────────────────────────────────────────────┤
│  [ pdf-studio table — risk metrics ]             │
│  ┌────────────┬──────────┬───────────┬──────────┐ │
│  │ Metric     │ Value    │ Metric    │ Value     │ │
│  ├────────────┼──────────┼───────────┼──────────┤ │
│  │ VaR (95%)  │ -2.8%    │ CVaR      │ -3.5%    │ │
│  │ Volatility │ 18.5%    │ CAGR      │ 14.2%    │ │
│  │ Max DD     │ -22.0%   │ Total Ret │ +28.0%   │ │
│  │ Sortino    │ 1.60     │ Beta      │ 0.92     │ │
│  └────────────┴──────────┴───────────┴──────────┘ │
├──────────────────────────────────────────────────┤
│  [ chart — drawdown area ]                        │
│  [ chart — monte carlo fan ]                      │
├──────────────────────────────────────────────────┤
│  [ pdf-studio heading h2 ] Top Priority Actions   │
│  [ bullet ] REDUCE SBIN — high weight...          │  ← doc.add_bullet()
│  [ bullet ] HEDGE ENERGY — oil price exposure... │
│  [ bullet ] DIVERSIFY sector concentration...    │
├──────────────────────────────────────────────────┤
│  [ pdf-studio paragraph — italic muted ]          │
│  Disclaimer text at bottom of every content page  │
└──────────────────────────────────────────────────┘

   ── page break ──
```

---

### Page 4: Holdings Breakdown

```
┌──────────────────────────────────────────────────┐
│  [ pdf-studio heading h1 ] 3. Holdings Breakdown  │
├──────────────────────────────────────────────────┤
│  [ chart — P&L horizontal bar ]                  │
├──────────────────────────────────────────────────┤
│  [ pdf-studio table — full holdings table ]       │
│  ┌────────┬────────────────┬─────┬───────┬──────┐ │
│  │ Ticker │ Name           │ Qty │ Price │ P&L% │ │  ← proper header
│  ├────────┼────────────────┼─────┼───────┼──────┤ │
│  │ RELI   │ Reliance Ind.  │ 10  │ 2,800 │+12.0%│ │  ← alternating rows
│  │ TCS    │ TCS            │  5  │ 3,800 │ +8.6%│ │
│  │ HDFCB  │ HDFC Bank      │ 20  │ 1,700 │ +6.3%│ │
│  └────────┴────────────────┴─────┴───────┴──────┘ │
├──────────────────────────────────────────────────┤
│  [ pdf-studio paragraph — center italic muted ]   │
│  Disclaimer text                                  │
└──────────────────────────────────────────────────┘
```

---

## Key changes from current version

| Aspect | Current (broken) | Redesign |
|--------|-----------------|----------|
| Cover page | Messy matplotlib KPI cards | Clean banner figure + native table + gauge figure |
| KPI cards | matplotlib rects with text → blurry | Native pdf-studio table (cleaner, sharper, proper fonts) |
| Section separation | Content flows linearly → awkward breaks | Explicit `add_page_break()` per section |
| Metric badges | matplotlib figures per badge row | Single table per section (compact, readable) |
| Recommendations | flat paragraphs | `add_bullet()` with proper list rendering |
| Tables | ad-hoc dataframe columns | Clean metric/risk tables with 4 columns |
| Gauge + assessment | Two separate figures | Combined single figure |
| Charts | Individual figures stacked vertically | Composite figures where they logically pair (sector+weight) |

---

## Implementation order

1. **pdf-studio: add `add_page_break()`** (document.py + render.py) — 3 lines
2. **pdf-studio: add `add_bullet()`** (document.py + render.py) — 8 lines
3. **Rewrite `charts_pdf.py`** — full replacement with clean design
   - Remove all dead helpers from first attempt
   - `_cover_banner_figure(portfolio, plt)` → composite banner
   - `_gauge_figure(risk, plt)` → gauge + risk text
   - `_sector_weight_figure(sector_data, portfolio, plt)` → side-by-side charts
   - `_drawdown_figure(portfolio_cum, plt)` → drawdown area chart
   - `_mc_figure(mc_result, plt)` → monte carlo fan chart
   - `_pnl_figure(df, plt)` → P&L bar chart
   - `_make_metrics_df(...)` → reshape risk data into display tables
   - `_generate_pdf_report(...)` → clean pdf-studio assembly
4. **Update tests** → 12-14 tests, figure assertions
5. **Remove fpdf2** — already done, verify clean
6. **Verify smoke test** → generate sample PDF, manual visual check
7. **Push both repos**
