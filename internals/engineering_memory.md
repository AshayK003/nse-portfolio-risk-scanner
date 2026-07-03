# NSE Portfolio Risk Scanner — Engineering Memory

## PDF Export Architecture (from v0.3.0+)

Switched from fpdf2 to **pdf-studio** (ReportLab backend) for PDF report generation.

**Layer structure:**
- `ui/charts_pdf.py` — all PDF logic: matplotlib chart builders (return Figure objects), cover page figure, KPI row figures, pdf-studio assembler
- `ui/export.py` — Streamlit UI layer: calls `_generate_pdf_report()` → gets bytes → download button
- `tests/test_pdf_export.py` — 14 tests: chart figures (8), PDF generation (2), utility functions (3), risk assessment (3)

**Key design decisions:**
- Chart functions return `matplotlib.figure.Figure` objects (not PNG bytes) — pdf-studio's `add_chart(fig)` renders them as inline vector SVGs
- Cover page rendered as a single matplotlib figure (navy block + KPI grid + risk gauge + assessment)
- KPI/metric badges rendered as `_kpi_row_figure()` — compact matplotlib figures with colored rects + text
- pdf-studio's `add_table(df)` handles the holdings data table (alternating rows, header repeat)
- `set_header()` adds running header on every page

**Dependencies:** pdf-studio installed as local editable dep at `D:/Personal projects/pdf-studio/`
- `pip install -e "D:/Personal projects/pdf-studio/"`

**What was removed:**
- fpdf2 dependency (from requirements.txt)
- 3 fpdf2-specific tests (chart_bytes PNG, metric_badge, page count check)
- 200+ lines of fpdf2 layout helpers (_metric_badge, _kpi_card, _data_table, _add_page_header, _add_cover_page, _section_header)
