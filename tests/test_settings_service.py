import tempfile
import unittest
from pathlib import Path

from nest_diary_web.models import ServiceUiSettings
from nest_diary_web.paths import NestPaths
from nest_diary_web.settings_service import ServiceSettingsStore


class ServiceSettingsMigrationTest(unittest.TestCase):
    LEGACY_PROMPT = (
        "写完日记后，请依据你的角色设定和当天日记内容判断："
        "这篇日记是否提供了关于某个人的稳定新证据。"
        "如果有，请先读取旧人物印象，再按变化更新 name、identity、summary、traits、hobbies、interests、preferences、relationship、affinity、special_comment、evidence_dates、confidence、notes；"
        "summary 写稳定总结，special_comment 写带有主观判断的特殊点评。"
        "如果没有稳定变化，不要硬写。"
    )

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = ServiceSettingsStore(NestPaths(Path(self.tmp.name)))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_legacy_impression_prompt_is_upgraded(self) -> None:
        settings = self.store._normalize(ServiceUiSettings(impression_prompt=self.LEGACY_PROMPT))

        self.assertIn("qq_id 为唯一身份主键", settings.impression_prompt)
        self.assertIn("完整、稳定的总体总结", settings.impression_prompt)
        self.assertNotEqual(settings.impression_prompt, self.LEGACY_PROMPT)

    def test_custom_impression_prompt_is_preserved(self) -> None:
        settings = self.store._normalize(ServiceUiSettings(impression_prompt="我的自定义印象规范"))

        self.assertEqual(settings.impression_prompt, "我的自定义印象规范")


if __name__ == "__main__":
    unittest.main()