#!/usr/bin/env python3
"""Summarize k6 JSON output or Locust request-stat JSON as Markdown.

Supported inputs:
- k6 --summary-export JSON
- k6 `--out json=results.json` newline-delimited point records
- Locust `/stats/requests`-style JSON with `stats` and optional `stats_total`
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from urllib.parse import urlsplit


def number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def clean_endpoint(value: Any) -> str:
    text = str(value).strip()
    if "://" in text:
        text = urlsplit(text).path or "/"
    else:
        text = text.split("?", 1)[0].split("#", 1)[0]
    return text[:180]


def redact_error(value: Any) -> str:
    text = str(value).replace("\n", " ").replace("\r", " ")
    text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+", "Bearer [REDACTED]", text)
    text = re.sub(r"(?i)\b(authorization|password|passwd|secret|token|api[_-]?key)\b\s*([:=])\s*[^\s,;&]+", r"\1\2[REDACTED]", text)
    return text[:240]


def markdown_inline(value: Any) -> str:
    return str(value).replace("`", "\\`").replace("\n", " ").replace("\r", " ")


def metric_values(metrics: dict[str, Any], name: str) -> dict[str, Any]:
    metric = metrics.get(name, {})
    if not isinstance(metric, dict):
        return {}
    values = metric.get("values", {})
    return values if isinstance(values, dict) else {}


def make_summary(**kwargs: Any) -> dict[str, Any]:
    defaults = {
        "requests": None, "failures": None, "failure_rate": None, "rps": None,
        "duration_s": None, "p50": None, "p95": None, "p99": None,
        "avg": None, "maximum": None, "endpoints": [], "errors": [],
    }
    defaults.update(kwargs)
    if defaults["failure_rate"] is None and defaults["requests"] and defaults["failures"] is not None:
        defaults["failure_rate"] = defaults["failures"] / defaults["requests"]
    if defaults["rps"] is None and defaults["requests"] and defaults["duration_s"]:
        defaults["rps"] = defaults["requests"] / defaults["duration_s"]
    return defaults


def summarize_k6_summary(data: dict[str, Any]) -> dict[str, Any]:
    metrics = data.get("metrics", {})
    if not isinstance(metrics, dict):
        raise ValueError("k6 summary is missing a metrics object")
    duration_stats = metric_values(metrics, "http_req_duration")
    failed_stats = metric_values(metrics, "http_req_failed")
    requests_stats = metric_values(metrics, "http_reqs")
    request_count = number(requests_stats.get("count"))
    failed_rate = number(failed_stats.get("rate"))
    failures = None
    if request_count is not None and failed_rate is not None:
        failures = round(request_count * failed_rate)
    state = data.get("state", {}) if isinstance(data.get("state"), dict) else {}
    run_ms = number(state.get("testRunDurationMs"))
    run_seconds = run_ms / 1000 if run_ms is not None and run_ms > 0 else None
    rps = number(requests_stats.get("rate"))
    if rps is None and request_count and run_seconds:
        rps = request_count / run_seconds
    endpoints = []
    groups = data.get("root_group", {}).get("groups", {}) if isinstance(data.get("root_group"), dict) else {}
    if isinstance(groups, dict):
        endpoints = sorted(groups.keys())
    return make_summary(
        requests=request_count,
        failures=failures,
        failure_rate=failed_rate,
        rps=rps,
        duration_s=run_seconds,
        p50=number(duration_stats.get("med")),
        p95=number(duration_stats.get("p(95)")),
        p99=number(duration_stats.get("p(99)")),
        avg=number(duration_stats.get("avg")),
        maximum=number(duration_stats.get("max")),
        endpoints=endpoints,
        errors=[],
    )


def parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def percentile_from_histogram(histogram: Any, percentile: float) -> float | None:
    if not isinstance(histogram, dict) or not histogram:
        return None
    bins: list[tuple[float, int]] = []
    for key, count in histogram.items():
        value, occurrences = number(key), number(count)
        if value is not None and occurrences is not None and occurrences > 0:
            bins.append((value, int(occurrences)))
    bins.sort()
    total = sum(count for _, count in bins)
    if total == 0:
        return None
    rank = max(1, math.ceil(percentile * total))
    seen = 0
    for value, count in bins:
        seen += count
        if seen >= rank:
            return value
    return bins[-1][0]


def summarize_locust(data: dict[str, Any]) -> dict[str, Any]:
    stats = data.get("stats", [])
    if isinstance(stats, dict):
        stats = list(stats.values())
    if not isinstance(stats, list):
        stats = []
    total = data.get("stats_total")
    if not isinstance(total, dict):
        total = next((row for row in stats if isinstance(row, dict) and (row.get("name") == "Aggregated" or row.get("type") == "Aggregated")), None)
    rows = [row for row in stats if isinstance(row, dict) and row is not total and row.get("name") != "Aggregated"]
    base = total if isinstance(total, dict) else {}

    requests = number(base.get("num_requests", data.get("total_num_requests")))
    failures = number(base.get("num_failures", data.get("total_num_failures")))
    if requests is None:
        requests = sum(number(row.get("num_requests")) or 0 for row in rows)
    if failures is None:
        failures = sum(number(row.get("num_failures")) or 0 for row in rows)
    if requests == 0 and failures == 0 and not rows and not base:
        requests = failures = None

    hist = base.get("response_times")
    if not isinstance(hist, dict):
        hist = {}
        for row in rows:
            row_hist = row.get("response_times")
            if isinstance(row_hist, dict):
                for key, count in row_hist.items():
                    hist[key] = (number(hist.get(key)) or 0) + (number(count) or 0)
    p50 = number(base.get("response_time_percentile_50", base.get("median_response_time")))
    p95 = number(base.get("response_time_percentile_95")) or percentile_from_histogram(hist, .95)
    p99 = number(base.get("response_time_percentile_99")) or percentile_from_histogram(hist, .99)
    avg = number(base.get("avg_response_time", base.get("average_response_time")))
    maximum = number(base.get("max_response_time"))
    if p50 is None:
        p50 = percentile_from_histogram(hist, .50)
    if avg is None and rows:
        weighted = [(number(row.get("avg_response_time", row.get("average_response_time"))), number(row.get("num_requests")) or 0) for row in rows]
        valid = [(value, weight) for value, weight in weighted if value is not None and weight > 0]
        if valid:
            avg = sum(value * weight for value, weight in valid) / sum(weight for _, weight in valid)
    if maximum is None and rows:
        maxima = [number(row.get("max_response_time")) for row in rows]
        maxima = [value for value in maxima if value is not None]
        maximum = max(maxima) if maxima else None
    duration = number(data.get("duration"))
    start, end = parse_time(data.get("start_time")), parse_time(data.get("end_time"))
    if duration is None and start and end:
        duration = max(0.0, (end - start).total_seconds())
    # Prefer mean throughput from the full test interval; current_rps is only a snapshot.
    rps = requests / duration if requests is not None and duration and duration > 0 else number(data.get("current_rps", base.get("current_rps")))
    endpoints = [clean_endpoint(f"{row.get('method', 'GET')} {row.get('name', '(unnamed)')}") for row in rows]
    raw_errors = data.get("errors", [])
    errors = []
    if isinstance(raw_errors, list):
        for err in raw_errors[:10]:
            if isinstance(err, dict):
                errors.append(redact_error(err.get("error", err.get("name", err))))
            else:
                errors.append(redact_error(err))
    return make_summary(
        requests=requests, failures=failures, rps=rps, duration_s=duration,
        p50=p50, p95=p95, p99=p99, avg=avg, maximum=maximum,
        endpoints=endpoints, errors=errors,
    )


def summarize_k6_jsonl(lines: Iterable[str]) -> dict[str, Any]:
    durations: list[float] = []
    requests = 0
    failures = 0.0
    saw_failure_metric = False
    timestamps: list[datetime] = []
    endpoint_counts: dict[str, int] = {}
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "Point":
            continue
        metric = event.get("metric")
        point = event.get("data", {})
        if not isinstance(point, dict):
            continue
        value = number(point.get("value"))
        if value is None:
            continue
        timestamp = parse_time(point.get("time"))
        if timestamp:
            timestamps.append(timestamp)
        tags = point.get("tags", {}) if isinstance(point.get("tags"), dict) else {}
        if metric == "http_reqs":
            requests += int(value)
            endpoint = tags.get("name", tags.get("url"))
            if endpoint:
                safe_endpoint = clean_endpoint(endpoint)
                endpoint_counts[safe_endpoint] = endpoint_counts.get(safe_endpoint, 0) + int(value)
        elif metric == "http_req_failed":
            failures += value
            saw_failure_metric = True
        elif metric == "http_req_duration":
            durations.append(value)
    durations.sort()
    duration_s = None
    if len(timestamps) > 1:
        duration_s = max(0.0, (max(timestamps) - min(timestamps)).total_seconds())
    def quantile(q: float) -> float | None:
        if not durations:
            return None
        return durations[max(0, math.ceil(q * len(durations)) - 1)]
    return make_summary(
        requests=requests or None,
        failures=round(failures) if saw_failure_metric else None,
        duration_s=duration_s,
        p50=quantile(.50), p95=quantile(.95), p99=quantile(.99),
        avg=sum(durations) / len(durations) if durations else None,
        maximum=max(durations) if durations else None,
        endpoints=sorted(endpoint_counts),
    )


def summarize_file(path: Path, source: str = "auto") -> tuple[str, dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        first = ""
        for line in handle:
            if line.strip():
                first = line
                break
    if not first:
        raise ValueError("Input file is empty")
    try:
        first_obj = json.loads(first)
    except json.JSONDecodeError:
        first_obj = None  # Pretty-printed single-document JSON: parse the full file below.
    if isinstance(first_obj, dict) and first_obj.get("type") == "Point" and source in ("auto", "k6"):
        with path.open(encoding="utf-8") as stream_handle:
            return "k6 JSON-lines", summarize_k6_jsonl(stream_handle)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        if source in ("auto", "k6"):
            with path.open(encoding="utf-8") as stream_handle:
                return "k6 JSON-lines", summarize_k6_jsonl(stream_handle)
        raise ValueError(f"Input is not valid {source} JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object")
    if source in ("auto", "k6") and "metrics" in data:
        return "k6 summary", summarize_k6_summary(data)
    if source in ("auto", "locust") and any(key in data for key in ("stats", "stats_total", "total_num_requests")):
        return "Locust JSON", summarize_locust(data)
    if source == "k6" and isinstance(first_obj, dict) and first_obj.get("type") == "Point":
        with path.open(encoding="utf-8") as stream_handle:
            return "k6 JSON-lines", summarize_k6_jsonl(stream_handle)
    raise ValueError(f"Input does not match the requested {source} format")


def fmt(value: Any, suffix: str = "") -> str:
    if value is None:
        return "N/A"
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        text = f"{int(value):,}"
    else:
        text = f"{value:,.2f}"
    return text + suffix


def render_markdown(source: str, stats: dict[str, Any], filename: str) -> str:
    rate = stats.get("failure_rate")
    rate_text = fmt(rate * 100, "%") if rate is not None else "N/A"
    lines = [
        "# Load Test Summary", "", f"- **Source:** {markdown_inline(source)}", f"- **Input:** `{markdown_inline(filename)}`", "",
        "## Overall", "",
        "| Requests | Failures | Failure rate | Throughput | Duration |",
        "|---:|---:|---:|---:|---:|",
        f"| {fmt(stats.get('requests'))} | {fmt(stats.get('failures'))} | {rate_text} | {fmt(stats.get('rps'), ' req/s')} | {fmt(stats.get('duration_s'), ' s')} |", "",
        "## Latency (ms)", "",
        "| p50 | p95 | p99 | Average | Maximum |", "|---:|---:|---:|---:|---:|",
        f"| {fmt(stats.get('p50'))} | {fmt(stats.get('p95'))} | {fmt(stats.get('p99'))} | {fmt(stats.get('avg'))} | {fmt(stats.get('maximum'))} |", "",
    ]
    endpoints = stats.get("endpoints") or []
    if endpoints:
        lines.extend(["## Endpoints", "", *[f"- `{markdown_inline(endpoint)}`" for endpoint in endpoints[:30]], ""])
    errors = stats.get("errors") or []
    if errors:
        lines.extend(["## Reported errors", "", *[f"- {markdown_inline(error)}" for error in errors[:10]], ""])
    else:
        lines.extend(["## Reported errors", "", "No error detail was present in the input. This does not necessarily mean the test had zero failures; see the failure count above.", ""])
    lines.extend(["> Values not present in the source are shown as `N/A`; this parser does not infer missing measurements.", ""])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="k6 or Locust JSON/JSONL result file")
    parser.add_argument("-f", "--format", choices=("auto", "k6", "locust"), default="auto")
    parser.add_argument("-o", "--output", type=Path, help="Markdown output path (default: stdout)")
    args = parser.parse_args()
    try:
        source, stats = summarize_file(args.input, args.format)
        report = render_markdown(source, stats, args.input.name)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if args.output:
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
