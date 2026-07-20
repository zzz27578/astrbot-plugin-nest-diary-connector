import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginPageTest(unittest.TestCase):
    def test_plugin_page_uses_astrbot_bridge(self) -> None:
        index = (ROOT / "pages" / "nest" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "pages" / "nest" / "main.js").read_text(encoding="utf-8")

        self.assertIn("/api/plugin/page/bridge-sdk.js", index)
        self.assertIn('type="module" src="./main.js"', index)
        self.assertIn("AstrBotPluginPage", script)
        self.assertIn("bridge.ready", script)
        self.assertIn('bridge.apiGet("status")', script)
        self.assertNotIn("fetch(", script)

    def test_plugin_page_status_route_is_namespaced(self) -> None:
        source = (ROOT / "main.py").read_text(encoding="utf-8")

        self.assertIn('route = f"/{PLUGIN_NAME}/status"', source)
        self.assertNotIn('"/nest/status"', source)
        self.assertNotIn('"nest/status"', source)
        self.assertIn("from astrbot.api.web import json_response", source)


if __name__ == "__main__":
    unittest.main()