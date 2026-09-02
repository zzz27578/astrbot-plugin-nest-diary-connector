from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

from main import NestDiaryConnectorPlugin, PLUGIN_NAME


class FakeCronManager:
    """最小化模拟 AstrBot CronJobManager 的任务查询、删除和创建。"""

    def __init__(self, jobs: list[SimpleNamespace] | None = None) -> None:
        self.jobs = list(jobs or [])
        self.list_job_types: list[str | None] = []
        self.deleted_ids: list[str] = []
        self.added_specs: list[dict] = []

    async def list_jobs(self, job_type: str | None = None):
        self.list_job_types.append(job_type)
        if job_type is None:
            return list(self.jobs)
        return [job for job in self.jobs if getattr(job, "job_type", None) == job_type]

    async def delete_job(self, job_id: str) -> None:
        self.deleted_ids.append(str(job_id))
        self.jobs = [job for job in self.jobs if str(getattr(job, "job_id", "")) != str(job_id)]

    async def add_active_job(self, **kwargs):
        self.added_specs.append(kwargs)
        job = SimpleNamespace(
            id=len(self.jobs) + 1,
            job_id=f"created-{len(self.jobs) + 1}",
            name=kwargs["name"],
            description=kwargs.get("description"),
            payload=kwargs["payload"],
            cron_expression=kwargs["cron_expression"],
            job_type="active_agent",
            enabled=True,
            run_once=kwargs.get("run_once", False),
        )
        self.jobs.append(job)
        return job


def job(
    *,
    job_id: str,
    name: str = "nest_diary_daily_default",
    payload: dict | None = None,
    cron_expression: str = "0 3 * * *",
    enabled: bool = True,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=999,
        job_id=job_id,
        name=name,
        description=f"{PLUGIN_NAME}:daily_archive:default",
        payload=payload or {"managed_by": PLUGIN_NAME},
        cron_expression=cron_expression,
        job_type="active_agent",
        enabled=enabled,
        run_once=False,
    )


def plugin_with_spec(spec: dict) -> NestDiaryConnectorPlugin:
    plugin = object.__new__(NestDiaryConnectorPlugin)
    plugin.context = SimpleNamespace()
    plugin._future_task_sync_lock = asyncio.Lock()
    plugin._desired_future_jobs = lambda: {spec["name"]: spec}
    return plugin


class FutureTaskSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = {
            "name": "nest_diary_daily_default",
            "cron_expression": "0 3 * * *",
            "payload": {"managed_by": PLUGIN_NAME, "notebook_id": "default"},
            "run_once": False,
            "description": f"{PLUGIN_NAME}:daily_archive:default",
        }

    def test_queries_all_jobs_and_reuses_existing_active_agent_job(self) -> None:
        manager = FakeCronManager(
            [job(job_id="uuid-1", payload=self.spec["payload"])]
        )
        plugin = plugin_with_spec(self.spec)
        plugin.context.cron_manager = manager

        asyncio.run(plugin._sync_future_tasks())
        asyncio.run(plugin._sync_future_tasks())

        self.assertEqual(manager.list_job_types, [None, None])
        self.assertEqual(len(manager.jobs), 1)
        self.assertEqual(manager.deleted_ids, [])
        self.assertEqual(len(manager.added_specs), 0)

    def test_cleans_all_historical_duplicates_and_creates_one(self) -> None:
        manager = FakeCronManager(
            [
                job(job_id="uuid-1", payload=self.spec["payload"]),
                job(job_id="uuid-2", payload=self.spec["payload"]),
                job(job_id="uuid-3", payload=self.spec["payload"]),
            ]
        )
        plugin = plugin_with_spec(self.spec)
        plugin.context.cron_manager = manager

        asyncio.run(plugin._sync_future_tasks())

        self.assertEqual(manager.deleted_ids, ["uuid-1", "uuid-2", "uuid-3"])
        self.assertEqual(len(manager.added_specs), 1)
        self.assertEqual(len(manager.jobs), 1)
        self.assertEqual(manager.jobs[0].name, self.spec["name"])

    def test_deletes_by_public_job_id_not_database_integer_id(self) -> None:
        existing = job(job_id="public-uuid", payload={"managed_by": PLUGIN_NAME, "notebook_id": "old"})
        manager = FakeCronManager([existing])
        plugin = plugin_with_spec(self.spec)
        plugin.context.cron_manager = manager

        asyncio.run(plugin._sync_future_tasks())

        self.assertEqual(manager.deleted_ids, ["public-uuid"])
        self.assertNotIn("999", manager.deleted_ids)
        self.assertEqual(len(manager.jobs), 1)
        self.assertEqual(manager.jobs[0].payload, self.spec["payload"])

    def test_replaces_disabled_managed_job(self) -> None:
        manager = FakeCronManager(
            [job(job_id="uuid-disabled", payload=self.spec["payload"], enabled=False)]
        )
        plugin = plugin_with_spec(self.spec)
        plugin.context.cron_manager = manager

        asyncio.run(plugin._sync_future_tasks())

        self.assertEqual(manager.deleted_ids, ["uuid-disabled"])
        self.assertEqual(len(manager.added_specs), 1)
        self.assertTrue(manager.jobs[0].enabled)


if __name__ == "__main__":
    unittest.main()
