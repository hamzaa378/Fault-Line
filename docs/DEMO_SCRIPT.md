# Faultline presentation walkthrough (about 2 minutes)

**0–20 seconds: Start with the problem.** “A deployment breaks production, but nobody knows which change preceded the incident. Notifications arrive late, and teams update the same record at once. Faultline preserves that evidence instead of guessing.” Show the dashboard: currently open SEV1, latest releases and recurring incident pattern.

**20–50 seconds: Explainable investigation.** Open “Checkout requests timing out.” Show the deployment candidate score, matched service and commit, and timing explanation. Emphasize it is a lead, not proof. Associate the candidate with the incident, then append a note.

**50–80 seconds: Show the twist.** Switch Event timeline between Event time and Arrival time. Find the delayed alert. Explain `occurred_at` and `received_at`. Enable Replay history and scrub backward. A late message alters the reconstruction without rewriting any event.

**80–100 seconds: Technical integrity.** Explain two rules: unique `(project, source, external_id)` blocks retries; a versioned atomic update rejects stale concurrent edits with HTTP 409. Point to `backend/tests/test_workflows.py` and the action audit log.

**100–120 seconds: Deliverables and next steps.** Show the architecture and ER diagrams in `docs/DIAGRAMS.md`, Docker Compose, GitHub Actions and exported incident case report. Be explicit that real-time push and a hosted production deployment are not claimed. Close by explaining what you would improve first: a PostgreSQL race benchmark and secure production session management.

Avoid claiming the app proves which developer caused a production failure. The product shows evidence and protects data integrity while keeping a human in control of causality decisions.
