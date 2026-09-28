import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


class ComposeIsolationTests(unittest.TestCase):
    def test_normal_stack_keeps_app_services_on_internal_network(self):
        config = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
        self.assertTrue(config["networks"]["app"]["internal"])
        self.assertNotIn("setup", config["networks"])

        services = config["services"]
        for name in ("frontend", "backend", "ollama"):
            with self.subTest(service=name):
                self.assertEqual(services[name]["networks"], ["app"])
                self.assertNotIn("ports", services[name])

        gateway = services["gateway"]
        self.assertEqual(set(gateway["networks"]), {"app", "ingress"})
        self.assertEqual(
            gateway["ports"],
            [
                "127.0.0.1:3000:80",
                "127.0.0.1:8000:8000",
                "127.0.0.1:11434:11434",
            ],
        )
        self.assertIn("NET_ADMIN", gateway["cap_add"])
        self.assertEqual(gateway["dns"], ["127.0.0.1"])
        script = (ROOT / "frontend" / "gateway-entrypoint.sh").read_text(encoding="utf-8")
        self.assertLess(script.index("ip route del default"), script.index("exec nginx"))
        proxy = (ROOT / "frontend" / "gateway.conf").read_text(encoding="utf-8")
        self.assertIn("location /api/", proxy)
        self.assertIn("proxy_pass http://backend:8000/;", proxy)
        self.assertIn("proxy_buffering off;", proxy)

    def test_setup_override_exposes_only_ollama_temporarily(self):
        setup = yaml.safe_load((ROOT / "docker-compose.setup.yml").read_text(encoding="utf-8"))
        self.assertEqual(set(setup["services"]), {"ollama"})
        self.assertEqual(set(setup["services"]["ollama"]["networks"]), {"app", "setup"})
        self.assertIn("setup", setup["networks"])


if __name__ == "__main__":
    unittest.main()
