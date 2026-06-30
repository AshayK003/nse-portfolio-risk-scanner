"""Tests for the delivery analysis module."""

from engine.delivery import fetch_delivery_for_holdings


class TestDeliveryAnalysis:
    def test_returns_empty_dict_without_nselib(self):
        """When nselib is not installed, should return empty dict."""
        result = fetch_delivery_for_holdings(["RELIANCE", "TCS"])
        from engine.delivery import _NSELIB_AVAILABLE
        if not _NSELIB_AVAILABLE:
            assert result == {}
        else:
            assert isinstance(result, dict)
