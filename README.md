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

## What it does

- Inspects project routes, runtime, test data, and monitoring without exposing secrets.
- Verifies critical user flows step by step with functional assertions before load testing.
- Creates a staged plan from a one-user smoke test through an explicitly approved load/stress scenario.
- Uses the validated critical journey as a realistic, paced load scenario when safe.
- Prefers existing tools; otherwise suggests tools such as k6 or Locust.
- Reports latency percentiles, throughput, failures, monitoring limits, and prioritized remediation.
- Can add a CI smoke test only when requested and against a dedicated test environment.

## Scope

The skill provides operating instructions to an AI agent; it is not a load generator, hosted testing service, or a guarantee of capacity. Actual test execution depends on the agent's environment, installed tools, target access, and user authorization. Passing results apply only to the tested build, environment, workload, and duration.

## Contributing

Keep test instructions safe by default: require authorization, impose explicit traffic ceilings, avoid destructive actions, and document monitoring gaps. Validate edits to `SKILL.md` before submitting a pull request.

## License

MIT. See [LICENSE](LICENSE).
