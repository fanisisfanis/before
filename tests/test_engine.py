from dataclasses import replace

import pytest

from before.demo import example
from before.engine import analyze, compare
from before.models import Observation


def with_section(snapshot, name, data, status="ok"):
    return replace(snapshot, sections={**snapshot.sections, name: Observation(status, data)})


def rules(analysis):
    return {item.rule for item in analysis.findings}


def test_realistic_proxy_and_path_regressions_are_distinguished():
    baseline, current, probes = example()
    result = analyze(current, baseline, probes=probes)
    assert len(result.changes) == 4
    assert rules(result) == {"local_proxy_unreachable", "proxy_changed", "command_missing"}
    assert next(x for x in result.findings if x.rule == "proxy_changed").certainty == "hypothesis"
    assert (
        next(x for x in result.findings if x.rule == "local_proxy_unreachable").certainty == "fact"
    )


def test_unchanged_snapshot_does_not_invent_a_problem():
    baseline, _, _ = example()
    result = analyze(baseline, baseline)
    assert result.changes == []
    assert result.findings == []


def test_cross_machine_diff_does_not_claim_command_regression():
    baseline, current, _ = example()
    result = analyze(replace(current, machine_id="another-pc"), baseline)
    assert len(result.changes) == 4
    assert "command_missing" not in rules(result)
    assert "proxy_changed" not in rules(result)
    assert any("разным установкам" in x for x in result.limitations)


def test_unavailable_is_unknown_and_never_a_deleted_setting():
    baseline, current, _ = example()
    current = with_section(current, "path", {}, "unavailable")
    current = with_section(current, "commands", {}, "unavailable")
    result = analyze(current, baseline)
    assert all(change.section not in ("path", "commands") for change in result.changes)
    assert "command_missing" not in rules(result)
    assert any("PATH" in x and "недоступно" in x for x in result.limitations)


def test_command_not_previously_observed_does_not_count_as_regression():
    baseline, current, _ = example()
    current = with_section(
        current, "commands", {**current.sections["commands"].data, "custom": None}
    )
    result = analyze(current, baseline)
    assert not any(change.subject == "custom" for change in result.changes)
    explicit = analyze(current, baseline, "command", "custom")
    assert "command_missing" in rules(explicit)
    assert not any("В рабочем снимке" in text for f in explicit.findings for text in f.evidence)


def test_path_order_change_is_visible():
    baseline, _, _ = example()
    entries = baseline.sections["path"].data["entries"]
    current = with_section(baseline, "path", {"entries": list(reversed(entries)), "scope": "test"})
    changes = compare(baseline, current)
    assert len(changes) == 1
    assert changes[0].subject == "Порядок / повторения PATH"


def test_missing_path_directory_records_disappearance():
    baseline, _, _ = example()
    entries = [{**x, "exists": False} for x in baseline.sections["path"].data["entries"]]
    current = with_section(baseline, "path", {"entries": entries, "scope": "test"})
    assert len(compare(baseline, current)) == 3
    assert "missing_path_directories" in rules(analyze(current, baseline))


def test_benign_service_stop_does_not_claim_causality():
    baseline, _, _ = example()
    current = with_section(
        baseline, "services", {"Dnscache": {"state": "stopped", "start": "automatic"}}
    )
    assert len(compare(baseline, current)) == 1
    assert "service_disabled" not in rules(analyze(current, baseline))


def test_disabled_service_is_a_hypothesis():
    baseline, _, _ = example()
    current = with_section(
        baseline, "services", {"Dnscache": {"state": "stopped", "start": "disabled"}}
    )
    finding = next(x for x in analyze(current, baseline).findings if x.rule == "service_disabled")
    assert finding.certainty == "hypothesis"


def test_new_collector_coverage_is_not_a_new_windows_proxy_setting():
    baseline, current, _ = example()
    baseline = with_section(baseline, "proxy", {"environment": {}, "windows": None})
    assert not [x for x in compare(baseline, current) if x.section == "proxy"]


def test_internet_filter_keeps_path_changes_but_only_network_findings():
    baseline, current, probes = example()
    result = analyze(current, baseline, "internet", probes=probes)
    assert any(x.section == "path" for x in result.changes)
    assert "command_missing" not in rules(result)


def test_same_target_route_comparison_uses_evidence():
    _, current, _ = example()
    probes = {
        "network": {
            "host": "example.com",
            "dns": "resolved",
            "direct": {"status": "reachable", "http_status": 200},
            "proxy": {"status": "failed", "error": "ConnectionRefusedError"},
        }
    }
    finding = next(
        x for x in analyze(current, probes=probes).findings if x.rule == "proxy_route_failed"
    )
    assert finding.certainty == "fact"
    assert "example.com" in " ".join(finding.evidence)


@pytest.mark.parametrize("status", ["failed", "unavailable"])
def test_one_failed_route_does_not_claim_isp_failure(status):
    _, current, _ = example()
    result = analyze(
        current, probes={"network": {"host": "example.com", "direct": {"status": status}}}
    )
    assert not any("провайдер" in x.title.lower() for x in result.findings)


def test_no_baseline_discloses_missing_history():
    _, current, _ = example()
    assert any("историю" in x for x in analyze(current).limitations)
