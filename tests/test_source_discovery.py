# -*- coding: utf-8 -*-
"""來源探索模組測試

測試 DiscoveredSource 資料模型與 SourceDiscovery 核心邏輯。
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.reading_agent.models import DiscoveredSource
from src.reading_agent.source_discovery import SourceDiscovery


# ================================================================== #
#  TestDiscoveredSource：資料模型測試                                    #
# ================================================================== #

class TestDiscoveredSource:
    """DiscoveredSource 資料模型的基本行為測試"""

    def test_create_with_defaults(self):
        """建立時預設值應正確填入"""
        source = DiscoveredSource(name="測試頻道", url="https://example.com")
        assert source.name == "測試頻道"
        assert source.url == "https://example.com"
        assert source.source_type == "youtube_channel"
        assert source.category == "general"
        assert source.language == "zh"
        assert source.score == 0.0
        assert source.status == "pending"
        assert source.discovered_at != ""  # __post_init__ 會自動填入

    def test_equality_by_url(self):
        """兩個 DiscoveredSource 以 URL 判斷相等"""
        s1 = DiscoveredSource(name="A", url="https://same.url")
        s2 = DiscoveredSource(name="B", url="https://same.url")
        s3 = DiscoveredSource(name="A", url="https://other.url")
        assert s1 == s2
        assert s1 != s3

    def test_hash_by_url(self):
        """hash 以 URL 計算，可放入 set"""
        s1 = DiscoveredSource(name="A", url="https://same.url")
        s2 = DiscoveredSource(name="B", url="https://same.url")
        assert hash(s1) == hash(s2)
        assert len({s1, s2}) == 1  # set 中只會保留一個

    def test_to_dict(self):
        """to_dict 應包含所有欄位"""
        source = DiscoveredSource(
            name="頻道X", url="https://yt.com/x",
            source_type="youtube_channel", score=85.0,
            category="business", reason="很棒", status="approved",
        )
        d = source.to_dict()
        assert d["name"] == "頻道X"
        assert d["url"] == "https://yt.com/x"
        assert d["score"] == 85.0
        assert d["status"] == "approved"
        assert d["category"] == "business"

    def test_from_dict(self):
        """from_dict 應正確還原物件"""
        data = {
            "name": "頻道Y",
            "url": "https://yt.com/y",
            "source_type": "website",
            "score": 72.5,
            "status": "rejected",
            "language": "en",
            "category": "science",
            "reason": "不太相關",
            "discovered_at": "2026-01-01T00:00:00",
            "metadata": {"key": "value"},
        }
        source = DiscoveredSource.from_dict(data)
        assert source.name == "頻道Y"
        assert source.source_type == "website"
        assert source.score == 72.5
        assert source.status == "rejected"
        assert source.metadata == {"key": "value"}

    def test_from_dict_missing_fields(self):
        """from_dict 遇到缺少的欄位應使用預設值"""
        data = {"name": "簡單", "url": "https://simple.com"}
        source = DiscoveredSource.from_dict(data)
        assert source.source_type == "youtube_channel"
        assert source.score == 0.0
        assert source.status == "pending"

    def test_roundtrip(self):
        """to_dict → from_dict 往返應保持資料一致"""
        original = DiscoveredSource(
            name="往返測試", url="https://round.trip",
            score=90.0, metadata={"a": 1},
        )
        restored = DiscoveredSource.from_dict(original.to_dict())
        assert original == restored
        assert restored.score == 90.0
        assert restored.metadata == {"a": 1}


# ================================================================== #
#  TestSourceDiscovery_Storage：儲存與載入測試                            #
# ================================================================== #

class TestSourceDiscoveryStorage:
    """測試 SourceDiscovery 的 load/save 功能"""

    def test_load_discovered_empty(self, tmp_path):
        """檔案不存在時應回傳空列表"""
        with patch("src.reading_agent.source_discovery.DISCOVERED_SOURCES_FILE",
                    tmp_path / "nonexist.json"):
            sd = SourceDiscovery()
            result = sd.load_discovered()
            assert result == []

    def test_save_and_load_discovered(self, tmp_path):
        """存入後應能正確讀出"""
        file = tmp_path / "discovered.json"
        sources = [
            DiscoveredSource(name="A", url="https://a.com", score=80.0),
            DiscoveredSource(name="B", url="https://b.com", score=60.0),
        ]
        with patch("src.reading_agent.source_discovery.DISCOVERED_SOURCES_FILE", file):
            sd = SourceDiscovery()
            sd.save_discovered(sources)
            loaded = sd.load_discovered()
            assert len(loaded) == 2
            assert loaded[0].name == "A"
            assert loaded[1].score == 60.0

    def test_load_discovered_invalid_json(self, tmp_path):
        """JSON 格式錯誤時應回傳空列表"""
        file = tmp_path / "bad.json"
        file.write_text("not json!", encoding="utf-8")
        with patch("src.reading_agent.source_discovery.DISCOVERED_SOURCES_FILE", file):
            sd = SourceDiscovery()
            result = sd.load_discovered()
            assert result == []


# ================================================================== #
#  TestSourceDiscovery_ApproveReject：審核功能測試                        #
# ================================================================== #

class TestSourceDiscoveryApproveReject:
    """測試 approve_source / reject_source"""

    def _setup_sources(self, tmp_path):
        """建立測試用的 discovered_sources.json"""
        file = tmp_path / "discovered.json"
        channels_file = tmp_path / "channels.json"
        channels_file.write_text("[]", encoding="utf-8")
        sources = [
            DiscoveredSource(
                name="好頻道", url="https://yt.com/good",
                source_type="youtube_channel", score=85.0,
                metadata={"channel_id": "UC_good"},
            ),
            DiscoveredSource(
                name="爛頻道", url="https://yt.com/bad",
                source_type="youtube_channel", score=40.0,
                metadata={"channel_id": "UC_bad"},
            ),
        ]
        data = [s.to_dict() for s in sources]
        file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return file, channels_file

    def test_approve_source_success(self, tmp_path):
        """approve 成功應更新 status 並寫入 channels.json"""
        file, channels_file = self._setup_sources(tmp_path)
        with patch("src.reading_agent.source_discovery.DISCOVERED_SOURCES_FILE", file), \
             patch("src.reading_agent.source_discovery.CHANNELS_FILE", channels_file):
            sd = SourceDiscovery()
            result = sd.approve_source("好頻道")
            assert result is True

            # 驗證 discovered_sources.json 已更新
            loaded = sd.load_discovered()
            approved = [s for s in loaded if s.name == "好頻道"][0]
            assert approved.status == "approved"

            # 驗證 channels.json 已寫入
            with open(channels_file, "r", encoding="utf-8") as f:
                channels = json.load(f)
            assert len(channels) == 1
            assert channels[0]["channel_id"] == "UC_good"

    def test_approve_source_not_found(self, tmp_path):
        """找不到名稱時應回傳 False"""
        file, channels_file = self._setup_sources(tmp_path)
        with patch("src.reading_agent.source_discovery.DISCOVERED_SOURCES_FILE", file), \
             patch("src.reading_agent.source_discovery.CHANNELS_FILE", channels_file):
            sd = SourceDiscovery()
            result = sd.approve_source("不存在的頻道")
            assert result is False

    def test_reject_source_success(self, tmp_path):
        """reject 成功應更新 status"""
        file, channels_file = self._setup_sources(tmp_path)
        with patch("src.reading_agent.source_discovery.DISCOVERED_SOURCES_FILE", file):
            sd = SourceDiscovery()
            result = sd.reject_source("爛頻道")
            assert result is True

            loaded = sd.load_discovered()
            rejected = [s for s in loaded if s.name == "爛頻道"][0]
            assert rejected.status == "rejected"

    def test_reject_source_not_found(self, tmp_path):
        """找不到名稱時應回傳 False"""
        file, _ = self._setup_sources(tmp_path)
        with patch("src.reading_agent.source_discovery.DISCOVERED_SOURCES_FILE", file):
            sd = SourceDiscovery()
            result = sd.reject_source("根本沒有")
            assert result is False


# ================================================================== #
#  TestSourceDiscovery_DiscoveryDue：週期判斷測試                        #
# ================================================================== #

class TestSourceDiscoveryDue:
    """測試 _is_due_for_discovery 週期判斷邏輯"""

    def test_no_log_file(self, tmp_path):
        """discovery_log.json 不存在時應回傳 True"""
        with patch("src.reading_agent.source_discovery.DISCOVERY_LOG_FILE",
                    tmp_path / "no_log.json"):
            sd = SourceDiscovery()
            assert sd._is_due_for_discovery() is True

    def test_recent_log(self, tmp_path):
        """最近有探索記錄時應回傳 False"""
        log_file = tmp_path / "log.json"
        log_data = [{
            "timestamp": datetime.now().isoformat(),
            "trigger": "manual",
            "candidates_found": 3,
            "duration_seconds": 10.0,
        }]
        log_file.write_text(json.dumps(log_data), encoding="utf-8")
        with patch("src.reading_agent.source_discovery.DISCOVERY_LOG_FILE", log_file), \
             patch("src.reading_agent.source_discovery.DISCOVERY_INTERVAL_DAYS", 30):
            sd = SourceDiscovery()
            assert sd._is_due_for_discovery() is False

    def test_old_log(self, tmp_path):
        """超過週期時應回傳 True"""
        log_file = tmp_path / "log.json"
        old_time = (datetime.now() - timedelta(days=31)).isoformat()
        log_data = [{
            "timestamp": old_time,
            "trigger": "manual",
            "candidates_found": 1,
            "duration_seconds": 5.0,
        }]
        log_file.write_text(json.dumps(log_data), encoding="utf-8")
        with patch("src.reading_agent.source_discovery.DISCOVERY_LOG_FILE", log_file), \
             patch("src.reading_agent.source_discovery.DISCOVERY_INTERVAL_DAYS", 30):
            sd = SourceDiscovery()
            assert sd._is_due_for_discovery() is True

    def test_invalid_log_json(self, tmp_path):
        """log 檔案壞掉時應回傳 True（保守策略：執行探索）"""
        log_file = tmp_path / "log.json"
        log_file.write_text("broken!", encoding="utf-8")
        with patch("src.reading_agent.source_discovery.DISCOVERY_LOG_FILE", log_file):
            sd = SourceDiscovery()
            assert sd._is_due_for_discovery() is True


# ================================================================== #
#  TestSourceDiscovery_BuildPrompt：Prompt 建構測試                     #
# ================================================================== #

class TestSourceDiscoveryBuildPrompt:
    """測試 _build_evaluation_prompt 的 prompt 建構"""

    def test_youtube_prompt_includes_titles(self):
        """YouTube 頻道的 prompt 應包含近期影片標題"""
        sd = SourceDiscovery()
        source = DiscoveredSource(
            name="說書頻道", url="https://yt.com/ch",
            source_type="youtube_channel",
            metadata={
                "channel_id": "UC_test",
                "recent_video_titles": ["影片A", "影片B"],
            },
        )
        prompt = sd._build_evaluation_prompt(source)
        assert "說書頻道" in prompt
        assert "影片A" in prompt
        assert "影片B" in prompt
        assert "YouTube 頻道" in prompt

    def test_website_prompt_includes_description(self):
        """網站的 prompt 應包含網站描述"""
        sd = SourceDiscovery()
        source = DiscoveredSource(
            name="書評網", url="https://books.example.com",
            source_type="website",
            metadata={"description": "優質書評平台"},
        )
        prompt = sd._build_evaluation_prompt(source)
        assert "書評網" in prompt
        assert "優質書評平台" in prompt
        assert "書評網站" in prompt

    def test_prompt_contains_scoring_criteria(self):
        """prompt 應包含四個評分維度"""
        sd = SourceDiscovery()
        source = DiscoveredSource(name="X", url="https://x.com")
        prompt = sd._build_evaluation_prompt(source)
        assert "內容相關性" in prompt
        assert "品質" in prompt
        assert "活躍度" in prompt
        assert "受眾契合度" in prompt

    def test_prompt_contains_json_format(self):
        """prompt 應包含 JSON 格式要求"""
        sd = SourceDiscovery()
        source = DiscoveredSource(name="X", url="https://x.com")
        prompt = sd._build_evaluation_prompt(source)
        assert '"score"' in prompt
        assert '"category"' in prompt
        assert '"reason"' in prompt


# ================================================================== #
#  TestSourceDiscovery_ParseGemini：Gemini 回應解析測試                  #
# ================================================================== #

class TestSourceDiscoveryParseGemini:
    """測試 _parse_gemini_evaluation 的防禦性解析"""

    def test_parse_valid_json(self):
        """正確的 JSON 應能順利解析"""
        sd = SourceDiscovery()
        text = '{"score": 85, "category": "business", "reason": "很好", "language": "zh", "update_frequency": "每週"}'
        result = sd._parse_gemini_evaluation(text)
        assert result["score"] == 85.0
        assert result["category"] == "business"
        assert result["reason"] == "很好"

    def test_parse_json_with_markdown(self):
        """JSON 被 markdown 包裹時也能解析"""
        sd = SourceDiscovery()
        text = '```json\n{"score": 70, "category": "general", "reason": "還行"}\n```'
        result = sd._parse_gemini_evaluation(text)
        assert result["score"] == 70.0

    def test_parse_empty_text(self):
        """空文字應回傳預設值"""
        sd = SourceDiscovery()
        result = sd._parse_gemini_evaluation("")
        assert result["score"] == 0.0
        assert result["reason"] == "無法解析評估結果"

    def test_parse_garbage_text(self):
        """完全無法解析的文字應回傳預設值"""
        sd = SourceDiscovery()
        result = sd._parse_gemini_evaluation("這不是 JSON 也不包含任何 JSON")
        assert result["score"] == 0.0

    def test_parse_score_clamped(self):
        """分數超過 100 或低於 0 應被限制"""
        sd = SourceDiscovery()
        text = '{"score": 150, "category": "general", "reason": "test"}'
        result = sd._parse_gemini_evaluation(text)
        assert result["score"] == 100.0

        text2 = '{"score": -10, "category": "general", "reason": "test"}'
        result2 = sd._parse_gemini_evaluation(text2)
        assert result2["score"] == 0.0

    def test_parse_json_with_extra_text(self):
        """JSON 前後有多餘文字時也能解析"""
        sd = SourceDiscovery()
        text = '以下是評估結果：\n{"score": 65, "category": "science", "reason": "科學相關"}\n希望對你有幫助。'
        result = sd._parse_gemini_evaluation(text)
        assert result["score"] == 65.0
        assert result["category"] == "science"


# ================================================================== #
#  TestSourceDiscovery_TrackedChannels：已追蹤頻道載入測試                #
# ================================================================== #

class TestSourceDiscoveryTrackedChannels:
    """測試 _load_tracked_channel_ids"""

    def test_no_channels_file(self, tmp_path):
        """channels.json 不存在時回傳空集合"""
        with patch("src.reading_agent.source_discovery.CHANNELS_FILE",
                    tmp_path / "no_channels.json"):
            sd = SourceDiscovery()
            ids = sd._load_tracked_channel_ids()
            assert ids == set()

    def test_load_tracked_ids(self, tmp_path):
        """應正確讀取 channel_id"""
        file = tmp_path / "channels.json"
        data = [
            {"channel_id": "UC_a", "name": "A"},
            {"channel_id": "UC_b", "name": "B"},
            {"name": "沒有ID的"},  # 無 channel_id，應被跳過
        ]
        file.write_text(json.dumps(data), encoding="utf-8")
        with patch("src.reading_agent.source_discovery.CHANNELS_FILE", file):
            sd = SourceDiscovery()
            ids = sd._load_tracked_channel_ids()
            assert ids == {"UC_a", "UC_b"}


# ================================================================== #
#  TestSourceDiscovery_DiscoverIfDue：自動探索觸發測試                    #
# ================================================================== #

class TestSourceDiscoveryDiscoverIfDue:
    """測試 discover_if_due 的自動觸發邏輯"""

    @pytest.mark.asyncio
    async def test_skip_when_not_due(self, tmp_path):
        """尚未到期時應直接回傳空列表"""
        log_file = tmp_path / "log.json"
        log_data = [{
            "timestamp": datetime.now().isoformat(),
            "trigger": "manual",
            "candidates_found": 2,
            "duration_seconds": 5.0,
        }]
        log_file.write_text(json.dumps(log_data), encoding="utf-8")
        with patch("src.reading_agent.source_discovery.DISCOVERY_LOG_FILE", log_file), \
             patch("src.reading_agent.source_discovery.DISCOVERY_INTERVAL_DAYS", 30):
            sd = SourceDiscovery()
            result = await sd.discover_if_due()
            assert result == []

    @pytest.mark.asyncio
    async def test_run_when_due(self, tmp_path):
        """到期時應呼叫 run_discovery"""
        log_file = tmp_path / "log.json"
        old_time = (datetime.now() - timedelta(days=31)).isoformat()
        log_data = [{"timestamp": old_time, "trigger": "manual",
                     "candidates_found": 0, "duration_seconds": 1.0}]
        log_file.write_text(json.dumps(log_data), encoding="utf-8")
        with patch("src.reading_agent.source_discovery.DISCOVERY_LOG_FILE", log_file), \
             patch("src.reading_agent.source_discovery.DISCOVERY_INTERVAL_DAYS", 30):
            sd = SourceDiscovery()
            mock_results = [DiscoveredSource(name="New", url="https://new.com")]
            sd.run_discovery = AsyncMock(return_value=mock_results)
            sd._log_discovery_run = MagicMock()  # 避免寫入檔案
            result = await sd.discover_if_due()
            assert len(result) == 1
            sd.run_discovery.assert_called_once()


# ================================================================== #
#  TestSourceDiscovery_LogDiscoveryRun：記錄寫入測試                     #
# ================================================================== #

class TestSourceDiscoveryLog:
    """測試 _log_discovery_run"""

    def test_log_creates_file(self, tmp_path):
        """應建立 discovery_log.json 並寫入記錄"""
        log_file = tmp_path / "sub" / "log.json"  # 子目錄也要能建立
        with patch("src.reading_agent.source_discovery.DISCOVERY_LOG_FILE", log_file):
            sd = SourceDiscovery()
            sd._log_discovery_run(
                trigger="manual", candidates_found=5, duration=12.3,
            )
            assert log_file.exists()
            with open(log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
            assert len(logs) == 1
            assert logs[0]["trigger"] == "manual"
            assert logs[0]["candidates_found"] == 5

    def test_log_appends_to_existing(self, tmp_path):
        """應追加到現有記錄"""
        log_file = tmp_path / "log.json"
        existing = [{"timestamp": "2026-01-01T00:00:00", "trigger": "manual",
                      "candidates_found": 1, "duration_seconds": 2.0}]
        log_file.write_text(json.dumps(existing), encoding="utf-8")
        with patch("src.reading_agent.source_discovery.DISCOVERY_LOG_FILE", log_file):
            sd = SourceDiscovery()
            sd._log_discovery_run(
                trigger="scheduled", candidates_found=3, duration=8.0,
            )
            with open(log_file, "r", encoding="utf-8") as f:
                logs = json.load(f)
            assert len(logs) == 2
            assert logs[1]["trigger"] == "scheduled"
