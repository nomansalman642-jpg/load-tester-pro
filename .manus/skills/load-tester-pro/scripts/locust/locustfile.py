"""Safe-by-default read-only user-flow template for Locust.

Configure only owner-approved targets and relative GET paths via environment.
"""
import os
import re

import gevent
from locust import HttpUser, between, events, task

BASE_URL = os.environ.get("TARGET_BASE_URL", "").rstrip("/")
APPROVED_URL = os.environ.get("APPROVED_TARGET_URL", "").rstrip("/")
AUTHORIZED = os.environ.get("LOAD_TEST_AUTHORIZED") == "YES"
RAW_PATHS = os.environ.get("FLOW_PATHS", "/,/health")

if not AUTHORIZED:
    raise RuntimeError(
        "Refusing to send traffic: set LOAD_TEST_AUTHORIZED=YES only after "
        "the owner has approved this exact target and test scope."
    )
if not BASE_URL or BASE_URL != APPROVED_URL:
    raise RuntimeError("Refusing to send traffic: TARGET_BASE_URL must exactly match APPROVED_TARGET_URL.")
if not re.match(r"^https?://[^/?#\s]+(?:/[^?#\s]*)?$", BASE_URL) or "@" in BASE_URL.split("//", 1)[-1]:
    raise RuntimeError("Set TARGET_BASE_URL to an http(s) origin/path without embedded credentials.")

FLOW_PATHS = [path.strip() for path in RAW_PATHS.split(",") if path.strip()]
if not FLOW_PATHS or any(
    not path.startswith("/") or path.startswith("//") or re.search(r"\s", path)
    for path in FLOW_PATHS
):
    raise RuntimeError("FLOW_PATHS must be comma-separated relative paths beginning with /; GET requests only.")


def enforce_runtime_bounds(environment, **_kwargs):
    runner = environment.runner
    user_count = getattr(runner, "target_user_count", 0) if runner else 0
    if not runner or runner.__class__.__name__ != "LocalRunner":
        raise RuntimeError("This template permits standalone local Locust runs only; distributed workers are blocked.")
    if not isinstance(user_count, int) or not 1 <= user_count <= 10:
        runner.quit()
        raise RuntimeError("Locust user count must be between 1 and 10.")
    runtime_host = (environment.host or BASE_URL).rstrip("/")
    if runtime_host != APPROVED_URL:
        runner.quit()
        raise RuntimeError("Runtime target does not exactly match APPROVED_TARGET_URL.")
    gevent.spawn_later(120, runner.quit)


events.test_start.add_listener(enforce_runtime_bounds)


class UserJourney(HttpUser):
    host = BASE_URL
    # One to two seconds of idle time after each step/flow.
    wait_time = between(1, 2)

    @task
    def run_read_only_journey(self):
        for path in FLOW_PATHS:
            with self.client.get(path, name=f"GET {path}", catch_response=True, timeout=10) as response:
                if response.status_code == 429 or response.status_code >= 500:
                    response.failure(f"Stop condition: GET {path} returned HTTP {response.status_code}")
                    if self.environment.runner:
                        self.environment.runner.quit()
                    return
                if not 200 <= response.status_code < 400:
                    response.failure(f"GET {path} returned HTTP {response.status_code}")
                else:
                    response.success()
            # Honor the configured wait interval between journey steps.
            self.wait()
