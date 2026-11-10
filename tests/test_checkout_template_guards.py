"""Test checkout-template import guards with a stub Locust module; no network calls."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scripts/locust/checkout_auth_flow.py"


class CheckoutTemplateGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        stub = Path(self.temp.name) / "locust.py"
        stub.write_text(
            "class HttpUser: pass\n"
            "def between(*args): return None\n"
            "def task(fn): return fn\n"
            "class _Hook:\n"
            "    def add_listener(self, fn): return fn\n"
            "class _Events:\n"
            "    test_start = _Hook()\n"
            "events = _Events()\n",
            encoding="utf-8",
        )
        (Path(self.temp.name) / "gevent.py").write_text("def spawn_later(*args, **kwargs): return None\n", encoding="utf-8")
        self.env = os.environ.copy()
        self.env["PYTHONPATH"] = self.temp.name + os.pathsep + self.env.get("PYTHONPATH", "")
        self.env.update(
            {
                "LOAD_TEST_AUTHORIZED": "YES",
                "TARGET_BASE_URL": "https://staging.example.test",
                "APPROVED_TARGET_URL": "https://staging.example.test",
                "TARGET_ENV": "staging",
                "ALLOW_TEST_WRITES": "YES",
                "PAYMENT_TEST_MODE": "YES",
                "TEST_USERNAME_TEMPLATE": "lt-user-{user_id}@example.test",
                "TEST_PASSWORD": "unit-test-placeholder",
                "PAYMENT_TEST_TOKEN": "sandbox-placeholder",
                "CHECKOUT_SKU": "sample-sku",
            }
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_template(self, template: Path = TEMPLATE) -> subprocess.CompletedProcess[str]:
        self.env["TEST_TEMPLATE_PATH"] = str(template)
        code = (
            "import os, runpy\n"
            "namespace = runpy.run_path(os.environ['TEST_TEMPLATE_PATH'])\n"
            "class LocalRunner:\n"
            "    target_user_count = int(os.environ.get('FAKE_USERS', '1'))\n"
            "    def quit(self): pass\n"
            "class Environment:\n"
            "    runner = LocalRunner()\n"
            "    host = os.environ.get('FAKE_RUNTIME_HOST', os.environ.get('TARGET_BASE_URL', ''))\n"
            "namespace['enforce_runtime_bounds'](Environment())\n"
        )
        return subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env=self.env,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )

    def test_all_required_staging_guards_allow_template_loading(self) -> None:
        result = self.run_template()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_mismatched_unapproved_target_is_blocked(self) -> None:
        self.env["TARGET_BASE_URL"] = "https://other.example.test"
        result = self.run_template()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("APPROVED_TARGET_URL", result.stderr)

    def test_production_marked_host_is_blocked_even_if_allowlisted(self) -> None:
        self.env["TARGET_BASE_URL"] = "https://prod.example.test"
        self.env["APPROVED_TARGET_URL"] = self.env["TARGET_BASE_URL"]
        result = self.run_template()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prod/production/live", result.stderr)

    def test_checkout_requires_payment_test_mode(self) -> None:
        self.env["PAYMENT_TEST_MODE"] = "NO"
        result = self.run_template()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("PAYMENT_TEST_MODE=YES", result.stderr)

    def test_checkout_requires_local_or_staging_environment(self) -> None:
        self.env["TARGET_ENV"] = "production"
        result = self.run_template()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("local or staging", result.stderr)

    def test_staging_checkout_requires_https(self) -> None:
        self.env["TARGET_BASE_URL"] = "http://staging.example.test"
        self.env["APPROVED_TARGET_URL"] = self.env["TARGET_BASE_URL"]
        result = self.run_template()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("require HTTPS", result.stderr)

    def test_checkout_template_blocks_more_than_ten_users_at_runtime(self) -> None:
        self.env["FAKE_USERS"] = "11"
        result = self.run_template()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("between 1 and 10", result.stderr)

    def test_checkout_template_blocks_runtime_host_override(self) -> None:
        self.env["FAKE_RUNTIME_HOST"] = "https://unapproved.example.test"
        result = self.run_template()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Runtime target", result.stderr)

    def test_read_only_locust_template_blocks_direct_high_user_count(self) -> None:
        self.env["FAKE_USERS"] = "11"
        result = self.run_template(ROOT / "scripts/locust/locustfile.py")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("between 1 and 10", result.stderr)


if __name__ == "__main__":
    unittest.main()
