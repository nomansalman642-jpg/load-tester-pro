"""Unit tests for the k6/Locust JSON-to-Markdown report parser."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("summarize_results", ROOT / "scripts/summarize_results.py")
assert SPEC and SPEC.loader
summarizer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(summarizer)


class SummarizeResultsTests(unittest.TestCase):
    def test_k6_summary_export(self) -> None:
        data = {
            "state": {"testRunDurationMs": 10_000},
            "metrics": {
                "http_reqs": {"values": {"count": 20}},
                "http_req_failed": {"values": {"rate": 0.05}},
                "iterations": {"values": {"rate": 9.0}},
                "http_req_duration": {"values": {"avg": 120.0, "med": 90.0, "p(95)": 250.0, "p(99)": 400.0, "max": 500.0}},
            },
        }
        result = summarizer.summarize_k6_summary(data)
        self.assertEqual(result["requests"], 20)
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["failure_rate"], 0.05)
        self.assertEqual(result["duration_s"], 10)
        self.assertEqual(result["rps"], 2)
        self.assertEqual(result["p95"], 250)

    def test_k6_json_lines(self) -> None:
        lines = [
            '{"type":"Point","metric":"http_reqs","data":{"time":"2026-01-01T00:00:00Z","value":1,"tags":{"name":"GET /catalog"}}}',
            '{"type":"Point","metric":"http_req_failed","data":{"time":"2026-01-01T00:00:00Z","value":0}}',
            '{"type":"Point","metric":"http_req_duration","data":{"time":"2026-01-01T00:00:00Z","value":100}}',
            '{"type":"Point","metric":"http_reqs","data":{"time":"2026-01-01T00:00:02Z","value":1,"tags":{"name":"GET /catalog"}}}',
            '{"type":"Point","metric":"http_req_failed","data":{"time":"2026-01-01T00:00:02Z","value":1}}',
            '{"type":"Point","metric":"http_req_duration","data":{"time":"2026-01-01T00:00:02Z","value":300}}',
        ]
        result = summarizer.summarize_k6_jsonl(lines)
        self.assertEqual(result["requests"], 2)
        self.assertEqual(result["failures"], 1)
        self.assertEqual(result["failure_rate"], 0.5)
        self.assertEqual(result["duration_s"], 2)
        self.assertIn("GET /catalog", result["endpoints"])

    def test_locust_request_stats(self) -> None:
        data = {
            "current_rps": 99.0,
            "duration": 30,
            "stats_total": {
                "num_requests": 120,
                "num_failures": 3,
                "avg_response_time": 80.0,
                "max_response_time": 900.0,
                "response_time_percentile_50": 50.0,
                "response_times": {"50": 60, "150": 55, "500": 4, "900": 1},
            },
            "stats": [{"method": "GET", "name": "/catalog", "num_requests": 120, "num_failures": 3}],
            "errors": [{"error": "HTTP 503"}],
        }
        result = summarizer.summarize_locust(data)
        self.assertEqual(result["requests"], 120)
        self.assertEqual(result["failures"], 3)
        self.assertEqual(result["failure_rate"], 0.025)
        self.assertEqual(result["p50"], 50)
        self.assertEqual(result["p95"], 150)
        self.assertEqual(result["p99"], 500)
        self.assertEqual(result["rps"], 4)
        self.assertEqual(result["errors"], ["HTTP 503"])

    def test_markdown_reports_missing_values_without_guessing(self) -> None:
        report = summarizer.render_markdown("k6", summarizer.make_summary(requests=0), "empty.json")
        self.assertIn("# Load Test Summary", report)
        self.assertIn("N/A", report)
        self.assertIn("does not infer missing measurements", report)

    def test_report_sanitizes_sensitive_error_text_and_url_queries(self) -> None:
        cleaned = summarizer.redact_error("HTTP 401 password=hunter2 token=secret Bearer abc123")
        self.assertNotIn("hunter2", cleaned)
        self.assertNotIn("secret", cleaned)
        self.assertNotIn("abc123", cleaned)
        self.assertEqual(summarizer.clean_endpoint("https://host.test/api/items?token=secret"), "/api/items")

    def test_file_auto_detection_for_pretty_json_and_json_lines(self) -> None:
        k6_data = {
            "metrics": {
                "http_reqs": {"values": {"count": 5}},
                "http_req_failed": {"values": {"rate": 0}},
                "http_req_duration": {"values": {"med": 12, "p(95)": 20, "p(99)": 24}},
            }
        }
        locust_data = {"stats_total": {"num_requests": 4, "num_failures": 0}, "stats": []}
        with tempfile.TemporaryDirectory() as tmp:
            k6_file = Path(tmp) / "summary.json"
            k6_file.write_text(json.dumps(k6_data, indent=2), encoding="utf-8")
            kind, summary = summarizer.summarize_file(k6_file)
            self.assertEqual(kind, "k6 summary")
            self.assertEqual(summary["requests"], 5)

            locust_file = Path(tmp) / "locust.json"
            locust_file.write_text(json.dumps(locust_data, indent=2), encoding="utf-8")
            kind, summary = summarizer.summarize_file(locust_file)
            self.assertEqual(kind, "Locust JSON")
            self.assertEqual(summary["requests"], 4)

            jsonl_file = Path(tmp) / "points.jsonl"
            jsonl_file.write_text(
                '{"type":"Point","metric":"http_reqs","data":{"time":"2026-01-01T00:00:00Z","value":1}}\n',
                encoding="utf-8",
            )
            kind, summary = summarizer.summarize_file(jsonl_file)
            self.assertEqual(kind, "k6 JSON-lines")
            self.assertEqual(summary["requests"], 1)


if __name__ == "__main__":
    unittest.main()
