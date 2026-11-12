# Evidence scenario suite

Run `python benchmarks/run.py`. It writes `results.json` next to the script and
returns a nonzero exit code on failure.

The fourteen scenarios cover unchanged state, a closed local proxy, a lost
command, proxy changes without active evidence, a normally stopped service,
a disabled service, comparison across machines, unreadable command data,
missing history, missing PATH directories, divergent direct/proxy routes,
DNS failure, an HTTP response and a timed-out probe.

Inputs are deterministic synthetic snapshots and probe results. Each scenario
lists required and forbidden findings. Proxy changes and disabled services must
remain hypotheses. The suite does not modify OS settings or contact the network.

This suite measures consistency with those specified cases. It does **not**
measure the frequency of those failures in the wild, sensitivity to arbitrary
Windows failures, comparative performance against another product, or the
correctness of native OS APIs. Pytest additionally exercises actual loopback
TCP sockets, real local storage and GUI/CLI integration.

Contributions should include a reproducible case, the observed evidence, an
expected conclusion and a nearby benign case where that conclusion is not
justified. A passing new rule must not merely hide ambiguous data.
