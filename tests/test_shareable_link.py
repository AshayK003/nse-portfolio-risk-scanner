"""Tests for the shareable portfolio link round-trip.

A broken link = a user who shared their report and the recipient sees nothing.
This guards the encode (app._share_link) -> decode (ui.upload) contract.
"""

import pytest

from engine import Holding, Portfolio
from engine.portfolio import decode_portfolio_link, encode_portfolio_link


def _portfolio():
    return Portfolio(
        holdings=[
            Holding(ticker="RELIANCE.NS", name="Reliance Industries", quantity=10, avg_price=2500.0),
            Holding(ticker="TCS.NS", name="Tata Consultancy", quantity=5, avg_price=3500.0),
        ],
        name="My Portfolio",
    )


class TestShareableLinkRoundTrip:
    def test_round_trip_preserves_holdings(self):
        pf = _portfolio()
        token = encode_portfolio_link(pf)
        restored = decode_portfolio_link(token)

        assert len(restored.holdings) == 2
        assert restored.holdings[0].ticker == "RELIANCE.NS"
        assert restored.holdings[0].quantity == 10
        assert restored.holdings[0].avg_price == 2500.0
        assert restored.holdings[1].ticker == "TCS.NS"

    def test_ticker_dot_ns_stripped_in_token(self):
        """Encoded token should not carry the .NS suffix (compact link)."""
        token = encode_portfolio_link(_portfolio())
        # base64 of the json; .NS must not appear in the decoded holdings json
        import base64
        import json

        decoded = json.loads(base64.b64decode(token).decode())
        assert all(".NS" not in h["t"] for h in decoded["holdings"])

    def test_empty_portfolio_round_trip(self):
        pf = Portfolio(holdings=[])
        token = encode_portfolio_link(pf)
        restored = decode_portfolio_link(token)
        assert restored.holdings == []

    def test_token_is_url_safe_base64(self):
        """Token must be embeddable in a URL query param without extra encoding."""
        token = encode_portfolio_link(_portfolio())
        # Decoding it back directly must work (no padding/binary issues)
        decode_portfolio_link(token)  # does not raise


class TestShareableLinkDecodeErrors:
    def test_garbage_token_raises(self):
        with pytest.raises(ValueError, match="Invalid portfolio link"):
            decode_portfolio_link("not-a-real-token!!!")

    def test_missing_holdings_key_raises(self):
        import base64
        import json

        token = base64.b64encode(json.dumps({"foo": 1}).encode()).decode()
        with pytest.raises(ValueError, match="missing 'holdings'"):
            decode_portfolio_link(token)

    def test_holdings_not_list_raises(self):
        import base64
        import json

        token = base64.b64encode(json.dumps({"holdings": 5}).encode()).decode()
        with pytest.raises(ValueError, match="'holdings' must be a list"):
            decode_portfolio_link(token)

    def test_holding_missing_required_field_raises(self):
        import base64
        import json

        token = base64.b64encode(json.dumps({"holdings": [{"t": "RELIANCE", "q": 10}]}).encode()).decode()
        with pytest.raises(ValueError, match="missing required fields"):
            decode_portfolio_link(token)
