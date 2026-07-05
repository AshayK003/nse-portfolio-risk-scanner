import re
with open('CHANGELOG.md', 'r', encoding='utf-8') as f:
    content = f.read()

old = '## v0.16.1 (2026-07-03)\n\n### Fixed\n\n- **All-NaN price history inflated negative P&L** (`app.py:210-216`)'
new = """## v0.16.2 (2026-07-05)

### Added

- **One-click sample portfolio** (`ui/upload.py`) — "Try Sample Portfolio" button in the empty state instantly loads a 7-holding diversified portfolio covering stocks (RELIANCE, TCS, INFY, ITC, ICICIBANK) plus sector and thematic ETFs (BANKBEES, CPSEETF). No CSV download → re-upload step. Zero overlap with user's personal holdings.

### Fixed

- **Save-before-fetch caused -100% P&L on reload** (`app.py:501-502`) — `render_save_button()` ran before the price-fetch block, persisting `current_price=0.0` to the database. Every newly loaded portfolio briefly showed `-100.00%` until the user triggered a manual refresh. Moved save call after the computation pipeline so only real prices are saved.
- **-100.00% flash between load and compute** (`ui/dashboard.py`) — `render_metric_row()` now checks `total_current > 0` before computing P&L. When prices haven't loaded yet, it shows "\u2014" and "Awaiting prices" instead of `-100.00%`.

### Changed

- **Sample portfolio prices reflect profit** — all 7 avg prices set 15-23% below live market close. Portfolio loads showing +21.59% total P&L with every holding in the green.
- **No overlap with user data** — sample tickers (RELIANCE, TCS, INFY, ITC, ICICIBANK, BANKBEES, CPSEETF) are distinct from any holdings in Ashay's or Rishu's real portfolios.

## v0.16.1 (2026-07-03)

### Fixed

- **All-NaN price history inflated negative P&L** (`app.py:210-216`)"""

if old not in content:
    print('ERROR: old string not found')
else:
    content = content.replace(old, new, 1)
    with open('CHANGELOG.md', 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK')
