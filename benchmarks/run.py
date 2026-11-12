"""Reproducible evidence scenarios; no host settings are changed.

These are deterministic fixtures, not a claim of real-world diagnostic accuracy.
Run actual OS collector and loopback integration tests with pytest separately.
"""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from before.demo import example
from before.engine import analyze
from before.models import Observation


def section(snapshot, name, data, status="ok"):
    return replace(snapshot, sections={**snapshot.sections, name: Observation(status, data)})


def scenarios():
    good, broken, evidence = example()
    yield (
        "unchanged",
        good,
        good,
        {},
        set(),
        {"command_missing", "proxy_changed", "service_disabled"},
    )
    yield "closed-local-proxy", good, broken, evidence, {"local_proxy_unreachable"}, set()
    yield "lost-command", good, broken, {}, {"command_missing"}, {"service_disabled"}
    yield (
        "proxy-change-is-only-hypothesis",
        good,
        broken,
        {},
        {"proxy_changed"},
        {"local_proxy_unreachable"},
    )
    yield (
        "service-stopped-normally",
        good,
        section(good, "services", {"Dnscache": {"state": "stopped", "start": "automatic"}}),
        {},
        set(),
        {"service_disabled"},
    )
    yield (
        "service-disabled",
        good,
        section(good, "services", {"Dnscache": {"state": "stopped", "start": "disabled"}}),
        {},
        {"service_disabled"},
        set(),
    )
    yield (
        "different-machine",
        good,
        replace(broken, machine_id="different"),
        {},
        set(),
        {"command_missing", "proxy_changed", "service_disabled"},
    )
    yield (
        "commands-unreadable",
        good,
        section(broken, "commands", {}, "unavailable"),
        {},
        set(),
        {"command_missing"},
    )
    yield "no-baseline", None, broken, {}, set(), {"proxy_changed", "command_missing"}
    yield (
        "missing-path-folder",
        good,
        section(
            good, "path", {"entries": [{"value": r"C:\missing", "exists": False}], "scope": "test"}
        ),
        {},
        {"missing_path_directories"},
        set(),
    )
    yield (
        "proxy-route-fails-only",
        good,
        good,
        {
            "network": {
                "host": "example.com",
                "dns": "resolved",
                "direct": {"status": "reachable", "http_status": 200},
                "proxy": {"status": "failed", "error": "ConnectionRefusedError"},
            }
        },
        {"proxy_route_failed"},
        {"dns_failed"},
    )
    yield (
        "dns-failure",
        good,
        good,
        {
            "network": {
                "host": "example.com",
                "dns": "failed",
                "direct": {"status": "failed", "error": "gaierror"},
            }
        },
        {"dns_failed", "direct_route_failed"},
        {"proxy_route_failed"},
    )
    yield (
        "site-responds",
        good,
        good,
        {
            "network": {
                "host": "example.com",
                "dns": "resolved",
                "direct": {"status": "reachable", "http_status": 403},
            }
        },
        {"direct_route_ok"},
        {"direct_route_failed"},
    )
    yield (
        "probe-timeout",
        good,
        good,
        {"network": {"host": "example.com", "status": "unavailable", "note": "timeout"}},
        set(),
        {"direct_route_failed", "proxy_route_failed"},
    )


def main():
    results = []
    for name, baseline, current, probes, required, forbidden in scenarios():
        result = analyze(current, baseline, probes=probes)
        actual = {finding.rule for finding in result.findings}
        passed = required <= actual and not forbidden & actual
        # Causal claims from changed proxies/services must remain hypotheses.
        passed = passed and all(
            x.certainty == "hypothesis"
            for x in result.findings
            if x.rule in ("proxy_changed", "service_disabled")
        )
        results.append({"scenario": name, "passed": passed, "findings": sorted(actual)})
        print(f"{'PASS' if passed else 'FAIL'}  {name}")
    output = {
        "kind": "synthetic-evidence-scenarios",
        "total": len(results),
        "passed": sum(item["passed"] for item in results),
        "results": results,
    }
    target = Path(__file__).with_name("results.json")
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n{output['passed']}/{output['total']} synthetic scenarios passed.")
    return 0 if output["passed"] == output["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
