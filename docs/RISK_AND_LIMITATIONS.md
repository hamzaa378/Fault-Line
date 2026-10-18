# Design limits and security notes

1. **Not a production security posture.** JWT tokens are stored in browser localStorage for local demo convenience. A real deployment should use HttpOnly SameSite cookies plus CSRF protection and short-lived credentials; protect against XSS and add rate limiting/lockout.
2. **Credentials.** `.env.example` and login placeholders are intentionally demo-only. Change database, JWT and seed passwords before exposing the stack anywhere public. TLS and secure network policy are not configured by Compose.
3. **Schema evolution.** SQLAlchemy `create_all()` creates initial tables but is **not** an upgrade/migration system. Apply Alembic before changing schema in an existing installation.
4. **Correlations.** Incident-suspect scores use timing, matching service, deployment outcome, and matching commit history. They may surface false positives and exclude older or missing deployments. Human confirmation remains required.
5. **External event projection.** Signed GitHub webhooks are ingested into the event stream with metadata minimization. Version 1.1 projects commits supplied in `push` into code_changes and terminal `deployment_status` into deployments; incomplete/truncated push events cannot yield complete history.
6. **Real-time.** The UI polls every 15 seconds. This is near-real-time refresh, not a true WebSocket/SSE push implementation.
7. **Deduplication.** Identity is scoped to project/source/external ID; payload digest protects against conflicting replay. Different external IDs for semantically identical notifications are not merged.
8. **Event storage.** The demonstration keeps events and audit rows without cleanup, retention policies, or archival jobs. Ingestion has no full rate throttling and is not a distributed message queue.
9. **GitHub repository ownership.** A single configured HMAC secret authenticates requests; optional environment-based project and repository bindings are included in v1.1. Per-project webhook secrets, full GitHub App verification and durable repository bindings remain necessary for multi-tenant production installations.
10. **Deployment status.** This ZIP includes a local Docker Compose deployment configuration but no externally deployed URL. Local unit tests do not replace a Compose build/run check.
11. **Date precision.** Historical events with time zones are normalized to UTC. Events that do not include a real occurrence time are recorded at receipt time and cannot be accurately backdated.
12. **Pagination.** Lists currently cap results at 200 (timeline default 150, max 500). Cursor-based pagination and event partitioning are future work.
