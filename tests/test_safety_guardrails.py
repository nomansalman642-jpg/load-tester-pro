"""Unit tests for load-test launcher safety gates; never contacts a target."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SafetyGuardrailTests(unittest.TestCase):
    def run_launcher(self, name: str, overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for key in (
            "LOAD_TEST_AUTHORIZED", "TARGET_BASE_URL", "APPROVED_TARGET_URL",
            "VUS", "DURATION", "THINK_SECONDS", "USERS", "SPAWN_RATE", "RUN_TIME",
        ):
            env.pop(key, None)
        env.update(overrides)
        return subprocess.run(
            ["bash", str(ROOT / "scripts" / name)],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=5,
        )

    def base(self) -> dict[str, str]:
        return {
            "LOAD_TEST_AUTHORIZED": "YES",
            "TARGET_BASE_URL": "https://staging.example.test",
            "APPROVED_TARGET_URL": "https://staging.example.test",
        }

    def test_k6_blocks_missing_authorization(self) -> None:
        env = self.base()
        env.pop("LOAD_TEST_AUTHORIZED")
        result = self.run_launcher("run-k6.sh", env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LOAD_TEST_AUTHORIZED", result.stderr)

    def test_locust_blocks_missing_authorization(self) -> None:
        env = self.base()
        env.pop("LOAD_TEST_AUTHORIZED")
        result = self.run_launcher("run-locust.sh", env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("LOAD_TEST_AUTHORIZED", result.stderr)

    def test_k6_blocks_target_not_in_exact_allowlist(self) -> None:
        env = self.base()
        env["TARGET_BASE_URL"] = "https://prod.example.test"
        result = self.run_launcher("run-k6.sh", env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not exactly match APPROVED_TARGET_URL", result.stderr)

    def test_locust_blocks_target_not_in_exact_allowlist(self) -> None:
        env = self.base()
        env["TARGET_BASE_URL"] = "https://prod.example.test"
        result = self.run_launcher("run-locust.sh", env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not exactly match APPROVED_TARGET_URL", result.stderr)

    def test_k6_blocks_more_than_ten_users(self) -> None:
        env = self.base()
        env["VUS"] = "11"
        result = self.run_launcher("run-k6.sh", env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("VUS must be", result.stderr)

    def test_locust_blocks_more_than_ten_users(self) -> None:
        env = self.base()
        env["USERS"] = "11"
        result = self.run_launcher("run-locust.sh", env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("USERS must be", result.stderr)

    def test_k6_blocks_durations_over_two_minutes(self) -> None:
        env = self.base()
        env["DURATION"] = "121s"
        result = self.run_launcher("run-k6.sh", env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("DURATION must be", result.stderr)

    def test_locust_blocks_durations_over_two_minutes(self) -> None:
        env = self.base()
        env["RUN_TIME"] = "3m"
        result = self.run_launcher("run-locust.sh", env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("RUN_TIME must be", result.stderr)

    def test_k6_blocks_embedded_url_credentials(self) -> None:
        env = self.base()
        env["TARGET_BASE_URL"] = "https://user:pass@staging.example.test"
        env["APPROVED_TARGET_URL"] = env["TARGET_BASE_URL"]
        result = self.run_launcher("run-k6.sh", env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("embedded credentials", result.stderr)


if __name__ == "__main__":
    unittest.main()
