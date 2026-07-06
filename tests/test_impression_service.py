import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from nest_diary_web.memory.impression_service import ImpressionService
from nest_diary_web.models import DiaryEntry, PersonImpression
from nest_diary_web.paths import NestPaths


class ImpressionServiceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.service = ImpressionService(NestPaths(Path(self.tmp.name)))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def write_raw_person(self, impression: PersonImpression) -> None:
        path = self.service._person_path(impression.name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(impression), ensure_ascii=False), encoding="utf-8")

    def test_read_filters_legacy_auto_evidence_noise(self) -> None:
        self.write_raw_person(
            PersonImpression(
                name="小明",
                summary="可靠的旧印象。",
                evidence_dates=["2026-05-01", "2026-06-01", "2026-06-02"],
                notes=(
                    "手动备注。\n"
                    "自动补充证据：该人物出现在 2026-06-01 的日记关联人物中。\n"
                    "自动补充证据：该人物出现在 2026-06-02 的日记关联人物中。"
                ),
            )
        )

        item = self.service.get("小明")

        self.assertEqual(item.evidence_dates, ["2026-05-01"])
        self.assertEqual(item.notes, "手动备注。")

    def test_touch_from_diary_does_not_append_mentions_to_existing_profiles(self) -> None:
        self.service.save(
            PersonImpression(
                name="小明",
                summary="可靠的旧印象。",
                evidence_dates=["2026-05-01"],
                notes="手动备注。",
            )
        )

        touched = self.service.touch_from_diary(
            DiaryEntry(date="2026-07-06", body="今天见到了小明。", people=["小明"]),
            update_existing=True,
        )
        item = self.service.get("小明")

        self.assertEqual(touched, [])
        self.assertEqual(item.evidence_dates, ["2026-05-01"])
        self.assertEqual(item.notes, "手动备注。")

    def test_merge_existing_keeps_old_profile_and_writes_real_update(self) -> None:
        self.write_raw_person(
            PersonImpression(
                name="小明",
                summary="旧印象。",
                traits=["认真"],
                evidence_dates=["2026-05-01", "2026-06-01"],
                notes="自动补充证据：该人物出现在 2026-06-01 的日记关联人物中。",
            )
        )

        saved = self.service.save(
            PersonImpression(
                name="小明",
                summary="更新后的稳定印象。",
                preferences=["喜欢安静沟通"],
                evidence_dates=["2026-07-06"],
            ),
            merge_existing=True,
        )

        self.assertEqual(saved.summary, "更新后的稳定印象。")
        self.assertEqual(saved.traits, ["认真"])
        self.assertEqual(saved.preferences, ["喜欢安静沟通"])
        self.assertEqual(saved.evidence_dates, ["2026-05-01", "2026-07-06"])
        self.assertEqual(saved.notes, "")


if __name__ == "__main__":
    unittest.main()
