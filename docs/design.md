# A small diagnostic application

The product has one loop: save a known-good state, compare, inspect evidence,
export a report. It has no permanent background agent, external backend or model.

## Boundaries

`collect.py` reads bounded OS state. Missing permissions become an unavailable
observation. `models.py` defines the versioned snapshot and validates imports.
`store.py` keeps snapshots in SQLite, using a random local installation ID to
distinguish same-installation comparisons from foreign ones.

`engine.py` compares only data observed on both sides. It does not call OS APIs,
execute programs or send network requests. Findings use a stable rule ID and
carry a certainty label, evidence, explanation and next steps.

`probes.py` checks configured loopback proxy endpoints. Optional external HTTPS
checks run in a child process with a 12-second parent deadline. Direct and
proxied requests use the same chosen hostname. `no_proxy`, unsupported SOCKS,
PAC and bypass configurations are explicitly accounted for; unsupported paths
are not presented as tested.

`app.py` runs collectors and probes through a Qt background worker. User input
is never interpolated into a shell. The command checker accepts only a basename
and searches absolute PATH entries without executing the result. Current
directory entries, shell aliases and functions are outside its coverage.

`report.py` creates previewable Markdown. The user may edit it before export;
HTML is an escaped, self-contained rendering with a restrictive content security
policy. Raw snapshots and diagnostic reports are separate on purpose.

## Why a fact is not a root cause

"A TCP connection to this configured loopback proxy port did not succeed" is
an observation. "The proxy setting changed since the working snapshot" is
another observation. "This explains why that browser is broken" remains a
hypothesis because the browser may use another configuration or the failure
may be unrelated.

An HTTP response, including a denial response, establishes reachability of an
HTTP endpoint along the tested route. It does not establish that the intended
content works, authentication succeeds or every app follows the same route.

## Deliberate exclusions

No automatic repair is shipped in 0.1.0. A reliable write/verify/undo transaction
needs separate coverage for conflicts, permissions, process inheritance and
concurrent edits. No general root-cause claims, invented confidence percentages,
continuous filesystem tracing or third-party installers are included.

The architecture leaves repair out of the diagnostic engine. If introduced
later, a repair must validate the exact current state, persist an undo journal
before writing, change one documented setting and repeat a relevant check.
