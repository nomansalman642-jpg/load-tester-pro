---
name: load-tester-pro
description: Test web app/API user journeys end to end, then design and run authorized, controlled load tests, find bottlenecks, and report results. Use after building or before deploying to verify app flows and assess performance, latency, errors, and concurrency.
---

# Load Tester Pro

Assess performance only for systems the user owns or is explicitly authorized to test. Start with project inspection and a conservative smoke test; increase load only within a confirmed scope and agreed limits. Prefer a staging/local environment. Never aim traffic at an arbitrary third-party target.

## Safety gates

1. Identify the exact base URL/environment and confirm the user has authority to test it. If the target is production, shared, or third-party, ask for explicit authorization and a safe test window before sending traffic.
2. Inspect for rate limits, provider quotas, autoscaling costs, data writes, emails/SMS, payment actions, and other side effects. Never exercise real checkout, destructive operations, account creation at scale, or external messaging. Use seeded test accounts and isolated data; prefer read-only routes.
3. Define a hard ceiling before execution: virtual users/concurrency, request rate, duration, and allowed endpoints. If the user has not specified a scope, propose a small smoke test (1 VU, at most 1 minute, low request rate) and ask before running any broader test. Do not silently escalate.
4. Stop immediately on sustained 5xx errors, unexpected writes/side effects, service degradation, rate-limit responses, resource exhaustion, or user request. Do not attempt denial-of-service, evasion, distributed traffic, or bypassing protections.
5. If the agent cannot safely execute traffic from its environment, generate scripts/instructions and ask the user to run them in the target's approved environment instead.

## Workflow

### 1. Discover the application

Inspect repository docs, package/build manifests, routes/controllers, authentication, data model, deployment configuration, and existing tests. Do not expose or print secrets. Identify framework, run commands, local/staging URLs, health endpoint, representative read-only user journeys, and any existing observability. Do not assume a homepage test represents the application.

Summarize discovered endpoints and risks. Mark unknowns explicitly. Ask only for missing information needed to establish safe target, authorization, or test ceiling.

### 2. Validate the user flow

Map the requested or critical journey into observable steps (for example: landing page → sign-in with a test account → search → submit a test form → verify the resulting state). For each step, define a success assertion: expected page/element, status, response schema, or safe persisted test record. Check navigation, session handling, validation, loading/error states, and that the flow reaches its intended outcome. Never infer that the app works merely because its homepage loads.

Prefer the project's existing end-to-end test framework (such as Playwright or Cypress). If none exists, use a browser-capable tool for a small functional walkthrough or create a minimal maintainable test when appropriate. Run the flow with a single test user first. Use synthetic data and isolated test accounts; do not trigger real payments, emails/SMS, destructive actions, or production side effects. Report blocked steps and distinguish app failures from test/setup problems.

After the journey passes functionally, translate the same critical path into a bounded load scenario. Preserve step order, authentication/session correlation, realistic pacing, and checks at each critical step. Avoid sharing one mutable account/state among concurrent users; use isolated or parameterized test identities where writes are approved. If a flow includes unsafe side effects, test only a safe read-only equivalent or stop and ask for a test-mode setup.

### 3. Agree performance budgets

Ask for or propose measurable goals: throughput, p50/p95/p99 latency, error rate, test duration, and resource limits. Keep user-provided targets distinct from suggested defaults. A reasonable starter gate for a simple API is p95 < 1 s and HTTP failure rate < 1%, but these are examples, not universal SLOs. Record test environment, build/revision, date, data set, and monitoring source.

### 4. Select a tool and model a realistic scenario

Prefer a tool already installed or used by the project. Otherwise, choose a maintainable option such as k6 (JavaScript) or Locust (Python); explain installation needs before adding dependencies. Use realistic think time, pacing, ramp-up, and workload mix. Avoid unbounded loops and uncontrolled arrival rates. Use unique test data when writes are explicitly approved. Handle tokens/cookies securely and correlate dynamic IDs; never hard-code credentials or commit secrets.

A practical staged plan is:

- Smoke: 1 VU, brief run, verify script and response correctness.
- Baseline: small expected traffic with gradual ramp-up.
- Load: agreed normal peak, bounded duration.
- Stress or spike: only when explicitly approved, with a hard ceiling and monitoring/stop conditions.

Do not treat a generic 50-user, 5-minute test as safe for every app.

### Bundled execution scripts

The skill bundle includes `scripts/k6/user-flow.js`, `scripts/locust/locustfile.py`, and guarded launchers `scripts/run-k6.sh` / `scripts/run-locust.sh`. Adapt `FLOW_PATHS` to the validated, safe GET steps in the user's journey; templates are read-only and do not perform login, writes, payments, or external messaging. Keep real credentials out of command history and repository files.

After the exact target, authorization, endpoints, and test ceiling are approved, begin with defaults (1 user, 30 seconds). For example:

```bash
LOAD_TEST_AUTHORIZED=YES TARGET_BASE_URL=http://127.0.0.1:8000 FLOW_PATHS='/,/health' bash scripts/run-k6.sh
# Or, if Locust is installed:
LOAD_TEST_AUTHORIZED=YES TARGET_BASE_URL=http://127.0.0.1:8000 FLOW_PATHS='/,/health' bash scripts/run-locust.sh
```

The launchers require explicit authorization, limit concurrency to 10 users and duration to 120 seconds, and pace requests. Set `VUS`/`USERS`, `DURATION`/`RUN_TIME`, and `FLOW_PATHS` only within the confirmed envelope. The k6 template aborts when its error-rate threshold is exceeded; Locust stops on HTTP 429 or 5xx. Do not bypass these bounds or run a wider test without renewed approval. If a journey needs authentication or writes, adapt it only for an isolated test environment and use test-only identities/data; never hard-code secrets.

### 5. Establish baseline and monitor

Run one-user smoke first. Confirm expected status codes and response checks, then capture latency percentiles and error rate. Before larger tests, ensure CPU, memory, database connections/latency, and relevant provider quotas can be observed. Where metrics are unavailable, state the limitation and do not claim root-cause certainty.

### 6. Execute within the approved envelope

Use only the confirmed host and paths. Enforce concurrency, rate, and duration ceilings in the script/tool itself. Keep traffic gradual and bounded. Avoid running tests in parallel unless explicitly approved and safe. Record command, tool/version, configuration, start/end time, and test revision. Stop on any safety trigger.

### 7. Analyze and report

Report total requests, throughput, p50/p95/p99, error count/rate, status distribution, timeouts, and resource metrics when available. Compare results to agreed budgets. Separate observations from hypotheses; correlate slow endpoints with server/database metrics before naming a cause. Identify the first bottleneck, likely impact, confidence, and prioritized remediation. Recommend a retest after changes.

Use this concise report structure:

1. Scope and authorization (target/environment, endpoints, ceiling, duration)
2. User-flow steps and functional pass/fail results
3. Load scenario and tool/configuration
4. Results versus budgets, failures, and bottleneck evidence (or monitoring gaps)
5. Prioritized fixes and retest plan

### 8. Optional CI smoke test

Only add CI configuration when requested. Keep CI tests short and low-load against a dedicated test environment. Store credentials in the CI secret manager, never in repository files. Set explicit thresholds and prevent a test from targeting production by default. Do not trigger deployment or modify infrastructure without approval.

## Implementation notes

- Treat test accounts/data as disposable; avoid cleanup that could delete real data.
- Keep generated scripts and reports out of source control unless requested; never include tokens, cookies, private hostnames, or personal data in reports.
- For browser-heavy experiences, use browser automation for functional flow validation, but prefer protocol-level tools for repeatable load. Do not launch hundreds of real browsers by default.
- Validate the full critical user journey at low volume before using it as a load scenario; report functional correctness separately from performance.
- Explain that a passing test proves only the tested build, environment, workload, and duration; it does not guarantee future capacity.
