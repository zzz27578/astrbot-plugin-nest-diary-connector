from __future__ import annotations

import importlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class ModuleUninstallApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.previous_data_dir = os.environ.get("NEST_DATA_DIR")
        os.environ["NEST_DATA_DIR"] = cls.temp_dir.name
        cls.web = importlib.import_module("nest_diary_web.main")
        cls.client = TestClient(cls.web.app)
        cls.client.cookies.set("nest_session", cls.web.web_auth.create_session_token())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()
        if cls.previous_data_dir is None:
            os.environ.pop("NEST_DATA_DIR", None)
        else:
            os.environ["NEST_DATA_DIR"] = cls.previous_data_dir
        cls.temp_dir.cleanup()

    def install_module_fixture(self, module_id: str, *, split_frontend: bool = False) -> tuple[Path, Path | None]:
        module_dir = self.web.paths.modules_dir / module_id
        data_dir = module_dir / "data" / "store"
        data_dir.mkdir(parents=True)
        (data_dir / "records.json").write_text('{"kept": true}', encoding="utf-8")
        manifest = {
            "id": module_id,
            "name": module_id,
            "type": "module",
            "runtime": "webui",
            "page": {"entry": "page.js", "export": "mount"},
            "nav": {"label": module_id, "icon": "modules"},
            "store": True,
        }
        (module_dir / "module.json").write_text(json.dumps(manifest), encoding="utf-8")
        (module_dir / "page.js").write_text("export function mount() {}", encoding="utf-8")

        frontend_dir = None
        if split_frontend:
            frontend_dir = self.web._custom_webui_root() / "modules" / module_id
            frontend_dir.mkdir(parents=True)
            (frontend_dir / "module.json").write_text(json.dumps(manifest), encoding="utf-8")
            (frontend_dir / "page.js").write_text("export function mount() {}", encoding="utf-8")

        settings = self.web.service_settings.load()
        settings.enabled_custom_modules = [*settings.enabled_custom_modules, module_id]
        settings.enabled_custom_extensions = [*settings.enabled_custom_extensions, module_id]
        settings.enabled_appearance_modules = [*settings.enabled_appearance_modules, module_id]
        settings.hidden_module_nav_ids = [*settings.hidden_module_nav_ids, module_id]
        settings.active_frontend_style = module_id
        self.web.service_settings.save(settings)
        return module_dir, frontend_dir

    def test_keep_data_removes_module_files_and_catalog_entry(self) -> None:
        module_id = "keep-data-module"
        module_dir, _ = self.install_module_fixture(module_id)

        response = self.client.post(
            "/api/ui/modules/uninstall",
            json={"module_id": module_id, "keep_data": True},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue((module_dir / "data" / "store" / "records.json").is_file())
        self.assertEqual({item.name for item in module_dir.iterdir()}, {"data"})
        self.assertNotIn(module_id, [item["id"] for item in payload["module_catalog"]["custom"]])
        self.assertNotIn(module_id, payload["settings"]["enabled_custom_modules"])
        self.assertNotIn(module_id, payload["settings"]["enabled_custom_extensions"])
        self.assertNotIn(module_id, payload["settings"]["enabled_appearance_modules"])
        self.assertNotIn(module_id, payload["settings"]["hidden_module_nav_ids"])
        self.assertEqual(payload["settings"]["active_frontend_style"], "default")
        backup_dir = Path(payload["backup_dir"])
        self.assertTrue((backup_dir / "module" / "page.js").is_file())
        self.assertIn(str(module_dir / "data"), payload["kept_paths"])

    def test_full_uninstall_removes_split_module_and_uses_distinct_backups(self) -> None:
        module_id = "split-module"
        module_dir, frontend_dir = self.install_module_fixture(module_id, split_frontend=True)
        self.assertIsNotNone(frontend_dir)

        response = self.client.post(
            "/api/ui/modules/uninstall",
            json={"module_id": module_id, "keep_data": False},
        )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertFalse(module_dir.exists())
        self.assertFalse(frontend_dir.exists())
        backup_dir = Path(payload["backup_dir"])
        self.assertTrue((backup_dir / "module" / "page.js").is_file())
        self.assertTrue((backup_dir / "frontend-module" / "page.js").is_file())

    def test_official_module_cannot_be_uninstalled(self) -> None:
        response = self.client.post(
            "/api/ui/modules/uninstall",
            json={"module_id": "diary", "keep_data": False},
        )

        self.assertEqual(response.status_code, 409)
        self.assertTrue(self.web.paths.module_dir("diary").exists())


if __name__ == "__main__":
    unittest.main()
