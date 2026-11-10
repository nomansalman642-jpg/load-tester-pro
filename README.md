# Load Tester Pro

An agent skill for validating critical web app/API user journeys and running **authorized, controlled** load tests. It guides an AI coding agent to inspect a project, verify the end-to-end flow at low volume, then replay that journey with bounded traffic, monitor service health, and report bottlenecks with evidence.

## Safety first

Use only on systems you own or have explicit permission to test. Prefer local or staging environments. The skill requires an approved target and a hard ceiling for concurrency, request rate, duration, and endpoints before broader tests. It avoids destructive and third-party side effects and stops when error rates or service health deteriorate.

## Install

This repository follows the Agent Skills `SKILL.md` layout and includes copies in these requested adapter directories:

- `.claude/skills/load-tester-pro/SKILL.md`
- `.claudecode/skills/load-tester-pro/SKILL.md`
- `.codex/skills/load-tester-pro/SKILL.md`
- `.manus/skills/load-tester-pro/SKILL.md`
- `.opencode/skills/load-tester-pro/SKILL.md`
- `.cline/skills/load-tester-pro/SKILL.md`
- `.ai-agent/skills/load-tester-pro/SKILL.md`

Use the skill import/discovery method supported by your current agent version; the custom `.claudecode`, `.manus`, and `.ai-agent` paths are repository packaging conventions and may need manual import. If your agent uses a different documented location, copy the root `SKILL.md` there. Restart or refresh the agent if needed. All bundled copies should match the root `SKILL.md`.

## Example: invoke with Claude Code

Install the skill bundle inside the application repository you want to test. Claude Code's project skill path is shown below; copy the whole bundle so its `scripts/` resources stay beside `SKILL.md`:

```bash
mkdir -p /path/to/my-app/.claude/skills/load-tester-pro
cp SKILL.md /path/to/my-app/.claude/skills/load-tester-pro/
cp -R scripts /path/to/my-app/.claude/skills/load-tester-pro/
cd /path/to/my-app
claude
```

In Claude Code, invoke the skill explicitly (or describe the task and allow skill matching):

```text
/load-tester-pro
Inspect this app's product-search journey. First verify the flow functionally with a test account. Then, only on my local app at http://127.0.0.1:8000, run the one-user 30-second GET-only smoke scenario for / and /health. Stop on errors and report p95, p99, throughput, and any monitoring gaps. Ask me before increasing the load.
```

Start Claude Code from the target project root so it can inspect the app code. Confirm that the skill is discovered before attempting any traffic.

## Example: invoke with Manus

Install `SKILL.md` as the `load-tester-pro` skill using the skill import/add flow available in your Manus version. Keep the accompanying `scripts/` directory in the same skill bundle. If your Manus import flow accepts only a single Markdown file, clone this repository into the task workspace as well so the agent can access the scripts. Then ask Manus:

```text
Use the load-tester-pro skill on this project. Map and functionally verify the sign-in-to-search user flow using only a test account. Do not test production. The approved target is my local app at http://127.0.0.1:8000; run only one VU for 30 seconds against the safe GET paths / and /health. Do not increase load without asking. Report functional checks separately from load metrics.
```

Manus skill import screens and supported paths can vary by version; use the skill import mechanism available in your account and ensure the resource folder is accessible.

## Run the bundled load-test scripts

The templates issue **GET requests only** and are deliberately bounded. Set `FLOW_PATHS` to actual, safe relative paths for your app; the default `/,/health` is only an example. The scripts do not perform login, writes, payments, or external messaging. Install k6 or Locust in the environment where the approved local/staging app is reachable.

After the owner explicitly approves the exact target and test scope, a one-user, 30-second k6 smoke run is:

```bash
LOAD_TEST_AUTHORIZED=YES \
TARGET_BASE_URL=http://127.0.0.1:8000 \
APPROVED_TARGET_URL=http://127.0.0.1:8000 \
FLOW_PATHS='/,/health' \
bash scripts/run-k6.sh
```

For an explicitly approved five-user, one-minute test within the built-in ceiling:

```bash
LOAD_TEST_AUTHORIZED=YES TARGET_BASE_URL=http://127.0.0.1:8000 \
APPROVED_TARGET_URL=http://127.0.0.1:8000 \
FLOW_PATHS='/,/products' VUS=5 DURATION=60s bash scripts/run-k6.sh
```

Alternatively, create a Python virtual environment, install Locust, and run its guarded launcher:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install locust
LOAD_TEST_AUTHORIZED=YES TARGET_BASE_URL=http://127.0.0.1:8000 \
APPROVED_TARGET_URL=http://127.0.0.1:8000 \
FLOW_PATHS='/,/products' USERS=1 RUN_TIME=30s bash scripts/run-locust.sh
```

The launchers require `TARGET_BASE_URL` to match `APPROVED_TARGET_URL` exactly; they reject missing authorization, non-HTTP(S) targets, embedded URL credentials, more than 10 users, and durations over 120 seconds. Locust templates additionally check the runtime host, reject distributed runs, enforce a 10-user maximum, and stop after 120 seconds even when called directly. k6 aborts when its HTTP failure-rate threshold is exceeded; Locust quits on HTTP 429 or 5xx. These safeguards are not a substitute for explicit authorization or monitoring. Never run these examples against a URL you do not own or have permission to test. Do not put passwords/tokens in the URL or commit them.

## Custom checkout and authentication flow

`scripts/locust/checkout_auth_flow.py` demonstrates a JSON-API journey: authenticate a unique pre-seeded test user, read a product, add it to a test cart, create a test checkout, and call a **test-only** payment endpoint. This flow performs writes. Do not use it against production, live payments, real customer data, or an external payment processor. Before use, customize its endpoint paths and payloads for the app's test API and verify that the payment endpoint is a mock/sandbox route.

Use only an explicitly approved local/staging URL, dedicated disposable accounts, and credentials injected from a secret manager or the environment (never commit or print them). Each simulated user needs a unique pre-seeded account matching `TEST_USERNAME_TEMPLATE`, such as `lt-user-{user_id}@example.test`.

```bash
# TEST_PASSWORD and PAYMENT_TEST_TOKEN must already be supplied securely.
LOAD_TEST_AUTHORIZED=YES \
TARGET_ENV=staging \
TARGET_BASE_URL=https://staging.example.test \
APPROVED_TARGET_URL=https://staging.example.test \
ALLOW_TEST_WRITES=YES \
PAYMENT_TEST_MODE=YES \
LOCUST_TEMPLATE=checkout-auth \
TEST_USERNAME_TEMPLATE='lt-user-{user_id}@example.test' \
TEST_PASSWORD="$TEST_PASSWORD" \
PAYMENT_TEST_TOKEN="$PAYMENT_TEST_TOKEN" \
CHECKOUT_SKU=demo-sku \
USERS=2 RUN_TIME=30s \
bash scripts/run-locust.sh
```

Checkout mode refuses targets that do not exactly match the approved URL, environments other than `local`/`staging`, hostnames marked `prod`/`production`/`live`, missing test-write or payment-test flags, absent sandbox credentials, and payment paths that do not identify a test endpoint. The flow creates at most one checkout per virtual user per run. Review the template and the application's sandbox configuration before enabling it.

## Turn raw JSON results into a Markdown report

For k6, export an aggregate summary or newline-delimited JSON points. The guarded launcher accepts `SUMMARY_FILE` to save the aggregate JSON:

```bash
LOAD_TEST_AUTHORIZED=YES \
TARGET_BASE_URL=http://127.0.0.1:8000 \
APPROVED_TARGET_URL=http://127.0.0.1:8000 \
FLOW_PATHS='/,/health' SUMMARY_FILE=results/k6-summary.json \
bash scripts/run-k6.sh
python scripts/summarize_results.py results/k6-summary.json --output results/k6-report.md
```

For Locust, give the parser a compatible request-stat JSON export (for example, a saved response from `/stats/requests`):

```bash
python scripts/summarize_results.py results/locust-stats.json --format locust --output results/locust-report.md
```

The parser also accepts k6 JSON-lines output and auto-detects supported formats. It reports requests, failures, throughput, latency percentiles, endpoints, and available error details. Metrics absent from the source are shown as `N/A`, not guessed. Review the source format and monitoring data before using the summary to make capacity claims.

## GitHub Actions validation

`.github/workflows/validate-skill.yml` runs on every push and pull request. It validates skill frontmatter, checks that all seven agent bundles and their scripts match the canonical files, checks Python/shell/JavaScript syntax, and runs unit tests for the report parser and safety guardrails. This is static/unit validation: it does not send traffic to an app or prove that a target can handle load.

Run the same unit suite locally with:

```bash
python -m unittest discover -s tests -v
```

## What it does

- Inspects project routes, runtime, test data, and monitoring without exposing secrets.
- Verifies critical user flows step by step with functional assertions before load testing.
- Creates a staged plan from a one-user smoke test through an explicitly approved load/stress scenario.
- Uses the validated critical journey as a realistic, paced load scenario when safe.
- Prefers existing tools; otherwise suggests tools such as k6 or Locust.
- Includes a guarded Locust authentication/checkout test-mode template and a k6/Locust JSON-to-Markdown report parser.
- Unit tests verify authorization, exact target allowlisting, load ceilings, and checkout test-mode gates without sending network traffic.
- Reports latency percentiles, throughput, failures, monitoring limits, and prioritized remediation.
- Can add a CI smoke test only when requested and against a dedicated test environment.

## Scope

The skill provides operating instructions to an AI agent; it is not a load generator, hosted testing service, or a guarantee of capacity. Actual test execution depends on the agent's environment, installed tools, target access, and user authorization. Passing results apply only to the tested build, environment, workload, and duration.

## Contributing

Keep test instructions safe by default: require authorization, impose explicit traffic ceilings, avoid destructive actions, and document monitoring gaps. Validate edits to `SKILL.md` before submitting a pull request.

## License

MIT. See [LICENSE](LICENSE).
