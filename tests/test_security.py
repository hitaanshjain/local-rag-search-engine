import unittest

from fastapi.testclient import TestClient

from app.api import app


class CorsTests(unittest.TestCase):
    def test_only_the_configured_frontend_origin_passes_preflight(self):
        client = TestClient(app)
        headers = {"Access-Control-Request-Method": "POST"}
        allowed = client.options(
            "/chat", headers={**headers, "Origin": "http://localhost:3000"}
        )
        denied = client.options(
            "/chat", headers={**headers, "Origin": "https://example.com"}
        )

        self.assertEqual(allowed.headers.get("access-control-allow-origin"), "http://localhost:3000")
        self.assertNotIn("access-control-allow-origin", denied.headers)


if __name__ == "__main__":
    unittest.main()
