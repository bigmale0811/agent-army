"""ATG Adapter 測試"""
from slot_cloner.plugins.atg.adapter import ATGAdapter


class TestATGAdapter:
    def test_can_handle_atg_url(self):
        assert ATGAdapter.can_handle("https://play.godeebxp.com/egames/test")

    def test_cannot_handle_other(self):
        assert not ATGAdapter.can_handle("https://pgsoft.com/game")

    def test_name(self):
        adapter = ATGAdapter()
        assert adapter.name == "atg"
