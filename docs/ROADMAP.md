# Lotus roadmap

Items deliberately skipped from the first Windows beta, with the reason and the likely path back in.

## Product surface

- **iOS / Android apps** — need store accounts, signing, mobile UI, push/update plumbing, and platform review. Start after Windows beta stabilizes.
- **Mac / Linux desktop builds** — code is Python/PyQt, but scanner paths, updater batch logic, signing, and OS permissions need per-platform passes.
- **Browser app** — needs a backend/API and auth/quota model before it is safe for private scans.

## AI and autonomy

- **Multi-AI fallback providers** — user retracted this for now. Lotus should prove its own Gemini path, memory, and tools first.
- **Self-trained model** — future research item; requires dataset policy, evaluation harness, and compute budget.
- **Voice interface** — Jarvis already owns the voice path; Lotus beta is text-first to avoid duplicating that complexity.
- **Autonomous GitHub remediation** — requires sandboxed execution, branch/PR workflow, tests, and human approval gates.

## Security and sandboxing

- **VirtualBox sandbox** — VirtualBox was not found on the Windows machine during beta setup, so code execution/rewrite automation stays recommend-only. Revisit when a VM is available.
- **Real antivirus engine** — beta uses static heuristics and quarantine only. A real AV/EDR integration or engine partnership is a later phase.
- **Full SOC monitoring** — sensors, alert correlation, and incident workflows belong to the separate Herdr SOC and should be bridged deliberately, not merged accidentally.

## Commercialization

- **Personal $20/month and enterprise $200/month tiers** — need account system, payment processor, tax handling, quota enforcement, license keys, refunds, and terms/privacy pages before launch.
- **Developer access tier** — public repo gives source visibility; a formal developer program needs contribution rules, SLA, and security disclosure policy.

## Quality

- **Automated tests** — beta has compile checks and manual UI validation; add pytest coverage for scanner, updater, db, and AI fallbacks.
- **Telemetry/crash reporting** — deferred for privacy; add opt-in diagnostics later.
