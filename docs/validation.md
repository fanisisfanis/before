# Initial validation · 2026-11-12

Executed in a Linux x86-64 environment using Python 3.12 and PySide6 6.8.3:

- Pytest covering pure rules, invalid imports, redaction, SQLite transactions,
  actual loopback TCP accept/refuse behavior, CLI report export and the Qt
  save → compare → edit → export workflow.
- Fourteen reproducible synthetic evidence scenarios, with required and
  forbidden findings. Results are included in `benchmarks/results.json`.
- Qt rendering at 1190×810 and 960×680, with visual inspection of the initial
  state and diagnostic cards. Screenshots use the labelled synthetic example.
- Ruff lint and format checks, Python compilation, source CLI execution and
  a PyInstaller native Linux build with a headless startup check.
- Portable executable integration with a real temporary command removed from
  a child process's PATH and a real bound-but-not-listening loopback proxy port.
  Both findings were present in its report; no OS settings were modified.

The exact final counts and portable smoke results are recorded in
`VALIDATION.txt` at the repository root after packaging.

Windows native collectors are implemented with winreg and the service control
APIs. They have **not** been run on an actual Windows machine for this delivery.
The included GitHub Actions matrix is ready to execute tests and create a
portable binary on Windows and Ubuntu; no remote workflow run is claimed.

The Linux build has been started and inspected with Qt's offscreen platform in
the supplied Linux environment. There was no interactive test on the user's
Arch desktop, physical Windows PC, real broken VPN, corporate proxy or broad
hardware/device matrix. Synthetic passing cases do not establish general
diagnostic accuracy or superiority to existing tools.

External HTTPS behavior is tested by controlled inputs and local integration;
no assertion about an actual ISP's health is based on those tests.
