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

    def test_touch_from_diary_never_creates_name_only_placeholder(self) -> None:
        touched = self.service.touch_from_diary(
            DiaryEntry(date="2026-07-17", body="今天提到了老爸。", people=["老爸"]),
            allow_new_people=True,
            update_existing=True,
            min_confidence=3,
        )

        self.assertEqual(touched, [])
        self.assertIsNone(self.service.get("老爸"))

    def test_service_restart_purges_legacy_empty_auto_candidates(self) -> None:
        self.write_raw_person(
            PersonImpression(
                name="老爸",
                summary=self.service._auto_summary("老爸", "2026-07-17", 3),
                evidence_dates=["2026-07-17"],
            )
        )

        restarted = ImpressionService(self.service.paths)

        self.assertIsNone(restarted.get("老爸"))

    def test_unified_new_nickname_without_qq_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires qq_id"):
            self.service.save(
                PersonImpression(name="新昵称", summary="没有 QQ，不能用于统一人物建档。"),
                identity_strategy="unified",
                merge_existing=True,
            )
    def test_unified_qq_update_rewrites_original_summary_and_removes_auto_candidate(self) -> None:
        self.service.save(
            PersonImpression(
                name="白熊不知道",
                summary="旧的总体总结。",
                qq_id="10001",
                traits=["可靠"],
                evidence_dates=["2026-07-06"],
            )
        )
        self.write_raw_person(
            PersonImpression(
                name="老爸",
                summary=self.service._auto_summary("老爸", "2026-07-17", 3),
                evidence_dates=["2026-07-17"],
                confidence=3,
            )
        )

        saved = self.service.save(
            PersonImpression(
                name="老爸",
                summary="结合新证据重写后的完整总体总结。",
                qq_id="10001",
                preferences=["重视家人"],
                evidence_dates=["2026-07-20"],
                confidence=4,
            ),
            identity_strategy="unified",
            merge_existing=True,
        )

        self.assertEqual(saved.name, "白熊不知道")
        self.assertEqual(saved.summary, "结合新证据重写后的完整总体总结。")
        self.assertNotIn("【老爸】", saved.summary)
        self.assertEqual(saved.traits, ["可靠"])
        self.assertEqual(saved.preferences, ["重视家人"])
        self.assertEqual(saved.evidence_dates, ["2026-07-06", "2026-07-20"])
        self.assertIn("历史昵称：老爸", saved.notes)
        self.assertIsNone(self.service.get("老爸"))
        self.assertEqual(self.service.get("白熊不知道").summary, saved.summary)
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
