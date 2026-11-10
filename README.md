# Load Tester Pro

An agent skill for planning and running **authorized, controlled** performance tests against web apps and APIs. It guides an AI coding agent to inspect a project, select representative journeys, establish measurable budgets, run bounded tests, watch service health, and report bottlenecks with evidence.

## Safety first

Use only on systems you own or have explicit permission to test. Prefer local or staging environments. The skill requires an approved target and a hard ceiling for concurrency, request rate, duration, and endpoints before broader tests. It avoids destructive and third-party side effects and stops when error rates or service health deteriorate.

## Install

This repository follows the Agent Skills `SKILL.md` layout. Use your agent's documented skill installer/import flow if available. Otherwise, copy or symlink this repository's `SKILL.md` into the agent's supported skills directory under `load-tester-pro/` (for example, a project-level `.claude/skills/load-tester-pro/` for Claude Code or `.agents/skills/load-tester-pro/` for agents that support that convention). For Codex, Manus, or other agents, use the skill-directory/import mechanism supported by your current agent version; exact discovery paths can vary. Restart or refresh the agent if needed.

## What it does

- Inspects project routes, runtime, test data, and monitoring without exposing secrets.
- Creates a staged plan from a one-user smoke test through an explicitly approved load/stress scenario.
- Prefers existing tools; otherwise suggests tools such as k6 or Locust.
- Reports latency percentiles, throughput, failures, monitoring limits, and prioritized remediation.
- Can add a CI smoke test only when requested and against a dedicated test environment.

## Scope

The skill provides operating instructions to an AI agent; it is not a load generator, hosted testing service, or a guarantee of capacity. Actual test execution depends on the agent's environment, installed tools, target access, and user authorization. Passing results apply only to the tested build, environment, workload, and duration.

## Contributing

Keep test instructions safe by default: require authorization, impose explicit traffic ceilings, avoid destructive actions, and document monitoring gaps. Validate edits to `SKILL.md` before submitting a pull request.

## License

MIT. See [LICENSE](LICENSE).
