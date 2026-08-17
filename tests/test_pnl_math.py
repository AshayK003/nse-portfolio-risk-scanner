"""Tests for PnL math on Holding and Portfolio dataclasses.

An investor reads these numbers directly. A wrong sign or a div-by-zero
silently hides a loss. These tests lock the arithmetic.
"""

from engine import Holding, Portfolio


class TestHoldingPnL:
    def test_profit(self):
        h = Holding(ticker="RIL", name="RIL", quantity=10, avg_price=100, current_price=120)
        assert h.invested_value == 1000
        assert h.current_value == 1200
        assert h.pnl == 200
        assert h.pnl_pct == 20.0

    def test_loss(self):
        h = Holding(ticker="RIL", name="RIL", quantity=10, avg_price=100, current_price=80)
        assert h.pnl == -200
        assert h.pnl_pct == -20.0

    def test_fractional_quantity(self):
        h = Holding(ticker="RIL", name="RIL", quantity=5, avg_price=250.5, current_price=300.25)
        assert h.invested_value == 1252.5
        assert h.current_value == 1501.25
        assert abs(h.pnl_pct - (248.75 / 1252.5 * 100)) < 1e-6

    def test_zero_current_price_no_loss_of_sign(self):
        """current_price=0 -> no current value, but invested is real."""
        h = Holding(ticker="RIL", name="RIL", quantity=10, avg_price=100, current_price=0)
        assert h.current_value == 0.0
        assert h.pnl == -1000.0
        assert h.pnl_pct == -100.0

    def test_zero_avg_price_no_division_by_zero(self):
        h = Holding(ticker="RIL", name="RIL", quantity=10, avg_price=0, current_price=100)
        assert h.invested_value == 0.0
        assert h.current_value == 1000.0
        assert h.pnl == 1000.0
        assert h.pnl_pct == 0.0  # invested 0 -> guarded

    def test_nan_current_price_treated_as_zero(self):
        h = Holding(
            ticker="RIL", name="RIL", quantity=10, avg_price=100, current_price=float("nan")
        )
        assert h.current_value == 0.0
        assert h.pnl == -1000.0


class TestPortfolioPnL:
    def _pf(self, holdings):
        return Portfolio(holdings=holdings, name="P")

    def test_total_pnl_sums_holdings(self):
        pf = self._pf(
            [
                Holding(ticker="A", name="A", quantity=10, avg_price=100, current_price=120),
                Holding(ticker="B", name="B", quantity=5, avg_price=200, current_price=180),
            ]
        )
        # A: +200, B: -100
        assert pf.total_invested == 2000
        assert pf.total_current == 2100
        assert pf.total_pnl == 100
        assert abs(pf.total_pnl_pct - 5.0) < 1e-9

    def test_all_zero_current_price(self):
        pf = self._pf(
            [
                Holding(ticker="A", name="A", quantity=10, avg_price=100, current_price=0),
                Holding(ticker="B", name="B", quantity=5, avg_price=200, current_price=0),
            ]
        )
        assert pf.total_current == 0.0
        assert pf.total_pnl == -2000.0
        assert pf.total_pnl_pct == -100.0

    def test_empty_portfolio(self):
        pf = Portfolio(holdings=[])
        assert pf.total_invested == 0.0
        assert pf.total_current == 0.0
        assert pf.total_pnl == 0.0
        assert pf.total_pnl_pct == 0.0

    def test_weight_normalizes_to_one(self):
        pf = self._pf(
            [
                Holding(ticker="A", name="A", quantity=10, avg_price=100, current_price=100),
                Holding(ticker="B", name="B", quantity=5, avg_price=200, current_price=300),
            ]
        )
        # A: 1000, B: 1500 -> weights 0.4 / 0.6
        w = pf.weight
        assert abs(sum(w) - 1.0) < 1e-9
        assert abs(w[0] - 0.4) < 1e-9
        assert abs(w[1] - 0.6) < 1e-9

    def test_weight_with_zero_current_is_excluded(self):
        pf = self._pf(
            [
                Holding(ticker="A", name="A", quantity=10, avg_price=100, current_price=100),
                Holding(ticker="B", name="B", quantity=5, avg_price=200, current_price=0),
            ]
        )
        w = pf.weight
        assert w[0] == 1.0
        assert w[1] == 0.0
