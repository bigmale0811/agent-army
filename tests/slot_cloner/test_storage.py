"""Storage Manager 測試"""
from slot_cloner.storage.manager import StorageManager, OUTPUT_DIRS


class TestStorageManager:
    def test_setup(self, tmp_path):
        sm = StorageManager(tmp_path / "output")
        result = sm.setup()
        assert result == tmp_path / "output"
        assert (tmp_path / "output" / "assets" / "images").is_dir()
        assert (tmp_path / "output" / "game" / "dist").is_dir()

    def test_verify_structure(self, tmp_path):
        sm = StorageManager(tmp_path / "output")
        assert sm.verify_structure() is False  # 尚未建立
        sm.setup()
        assert sm.verify_structure() is True

    def test_path_helpers(self, tmp_path):
        sm = StorageManager(tmp_path / "output")
        assert sm.images_dir() == tmp_path / "output" / "assets" / "images"
        assert sm.audio_dir() == tmp_path / "output" / "assets" / "audio"
        assert sm.game_dir() == tmp_path / "output" / "game"

    def test_get_path(self, tmp_path):
        sm = StorageManager(tmp_path / "output")
        assert sm.get_path("analysis", "report.md") == tmp_path / "output" / "analysis" / "report.md"
