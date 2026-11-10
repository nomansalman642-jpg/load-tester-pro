"""Guarded Locust JSON-API checkout journey for local/staging test systems only.

This template performs writes and calls a test-only payment route. It requires
an exact approved target URL, disposable pre-seeded accounts, explicit test
write/payment-mode flags, and a sandbox-only payment token. Adapt endpoint and
JSON field names to the application's test API before use.
"""
from __future__ import annotations

import itertools
import os
import re
from urllib.parse import quote, urlparse

import gevent
from locust import HttpUser, between, events, task

BASE_URL = os.environ.get("TARGET_BASE_URL", "").rstrip("/")
APPROVED_URL = os.environ.get("APPROVED_TARGET_URL", "").rstrip("/")
AUTHORIZED = os.environ.get("LOAD_TEST_AUTHORIZED") == "YES"
TARGET_ENV = os.environ.get("TARGET_ENV", "").lower()
ALLOW_WRITES = os.environ.get("ALLOW_TEST_WRITES") == "YES"
PAYMENT_TEST_MODE = os.environ.get("PAYMENT_TEST_MODE") == "YES"
USERNAME_TEMPLATE = os.environ.get("TEST_USERNAME_TEMPLATE", "")
TEST_PASSWORD = os.environ.get("TEST_PASSWORD", "")
PAYMENT_TEST_TOKEN = os.environ.get("PAYMENT_TEST_TOKEN", "")
SKU = os.environ.get("CHECKOUT_SKU", "")

if not AUTHORIZED:
    raise RuntimeError("Refusing checkout traffic: LOAD_TEST_AUTHORIZED=YES requires explicit owner approval.")
if not BASE_URL or BASE_URL != APPROVED_URL:
    raise RuntimeError("Refusing checkout traffic: TARGET_BASE_URL must exactly match APPROVED_TARGET_URL.")
parsed_target = urlparse(BASE_URL)
if parsed_target.scheme not in ("http", "https") or not parsed_target.hostname or parsed_target.username or parsed_target.password:
    raise RuntimeError("TARGET_BASE_URL must be a valid http(s) URL without embedded credentials.")
if TARGET_ENV not in ("local", "staging"):
    raise RuntimeError("Checkout flow is allowed only when TARGET_ENV is exactly local or staging.")
if TARGET_ENV == "staging" and parsed_target.scheme != "https":
    raise RuntimeError("Staging checkout tests require HTTPS to protect test credentials.")
if re.search(r"(?:^|[.-])(prod|production|live)(?:[.-]|$)", parsed_target.hostname, re.IGNORECASE):
    raise RuntimeError("Refusing a hostname marked prod/production/live.")
if not ALLOW_WRITES or not PAYMENT_TEST_MODE:
    raise RuntimeError("Checkout writes require ALLOW_TEST_WRITES=YES and PAYMENT_TEST_MODE=YES.")
if not USERNAME_TEMPLATE or "{user_id}" not in USERNAME_TEMPLATE or not TEST_PASSWORD:
    raise RuntimeError("Set a pre-seeded TEST_USERNAME_TEMPLATE containing {user_id} and TEST_PASSWORD.")
if not PAYMENT_TEST_TOKEN or not SKU:
    raise RuntimeError("Set sandbox-only PAYMENT_TEST_TOKEN and CHECKOUT_SKU.")

LOGIN_PATH = os.environ.get("LOGIN_PATH", "/api/auth/login")
PRODUCT_PATH_TEMPLATE = os.environ.get("PRODUCT_PATH_TEMPLATE", "/api/products/{sku}")
CART_PATH = os.environ.get("CART_PATH", "/api/cart/items")
CHECKOUT_PATH = os.environ.get("CHECKOUT_PATH", "/api/checkout")
TEST_PAYMENT_PATH = os.environ.get("TEST_PAYMENT_PATH", "/api/payments/test")
PATHS = (LOGIN_PATH, PRODUCT_PATH_TEMPLATE, CART_PATH, CHECKOUT_PATH, TEST_PAYMENT_PATH)
if any(not p.startswith("/") or p.startswith("//") or re.search(r"\s", p) for p in PATHS):
    raise RuntimeError("Flow endpoints must be relative paths beginning with /.")
if "test" not in TEST_PAYMENT_PATH.lower():
    raise RuntimeError("TEST_PAYMENT_PATH must visibly identify a test-only payment endpoint.")


def enforce_runtime_bounds(environment, **_kwargs):
    runner = environment.runner
    user_count = getattr(runner, "target_user_count", 0) if runner else 0
    if not runner or runner.__class__.__name__ != "LocalRunner":
        raise RuntimeError("Checkout template permits standalone local Locust runs only; distributed workers are blocked.")
    if not isinstance(user_count, int) or not 1 <= user_count <= 10:
        runner.quit()
        raise RuntimeError("Locust user count must be between 1 and 10.")
    runtime_host = (environment.host or BASE_URL).rstrip("/")
    if runtime_host != APPROVED_URL:
        runner.quit()
        raise RuntimeError("Runtime target does not exactly match APPROVED_TARGET_URL.")
    gevent.spawn_later(120, runner.quit)


events.test_start.add_listener(enforce_runtime_bounds)

_USER_IDS = itertools.count(1)


class CheckoutAuthJourney(HttpUser):
    host = BASE_URL
    wait_time = between(1, 2)

    def on_start(self) -> None:
        self.user_id = next(_USER_IDS)
        self.username = USERNAME_TEMPLATE.format(user_id=self.user_id)
        self.auth_headers: dict[str, str] = {"Content-Type": "application/json"}
        self.finished = False

    def _stop(self, response, step: str) -> bool:
        if response.status_code == 429 or response.status_code >= 500:
            response.failure(f"Stop condition at {step}: HTTP {response.status_code}")
            if self.environment.runner:
                self.environment.runner.quit()
            return True
        if response.status_code < 200 or response.status_code >= 400:
            response.failure(f"{step} returned HTTP {response.status_code}")
            self.finished = True
            return True
        response.success()
        return False

    @task
    def checkout_once(self) -> None:
        # One checkout per VU prevents uncontrolled repeated order creation.
        if self.finished:
            self.wait()
            return

        with self.client.post(
            LOGIN_PATH,
            json={"username": self.username, "password": TEST_PASSWORD},
            name="POST auth/login",
            catch_response=True,
            timeout=10,
        ) as response:
            if self._stop(response, "authentication"):
                return
            try:
                payload = response.json()
            except Exception:
                response.failure("Authentication response was not JSON")
                self.finished = True
                return
            token = payload.get("access_token") or payload.get("token")
            if not token:
                response.failure("Authentication response did not contain an access token")
                self.finished = True
                return
            self.auth_headers["Authorization"] = f"Bearer {token}"
        self.wait()

        product_path = PRODUCT_PATH_TEMPLATE.format(sku=quote(SKU, safe=""))
        with self.client.get(product_path, headers=self.auth_headers, name="GET product", catch_response=True, timeout=10) as response:
            if self._stop(response, "product lookup"):
                return
        self.wait()

        with self.client.post(
            CART_PATH,
            json={"sku": SKU, "quantity": 1},
            headers=self.auth_headers,
            name="POST cart item",
            catch_response=True,
            timeout=10,
        ) as response:
            if self._stop(response, "cart update"):
                return
        self.wait()

        with self.client.post(
            CHECKOUT_PATH,
            json={"payment_mode": "test"},
            headers=self.auth_headers,
            name="POST test checkout",
            catch_response=True,
            timeout=10,
        ) as response:
            if self._stop(response, "test checkout"):
                return
            try:
                order_id = response.json().get("order_id")
            except Exception:
                order_id = None
            if not order_id:
                response.failure("Test checkout response did not contain order_id")
                self.finished = True
                return
        self.wait()

        with self.client.post(
            TEST_PAYMENT_PATH,
            json={"order_id": order_id, "payment_token": PAYMENT_TEST_TOKEN, "test_mode": True},
            headers=self.auth_headers,
            name="POST sandbox payment",
            catch_response=True,
            timeout=10,
        ) as response:
            self._stop(response, "sandbox payment")
        self.finished = True
