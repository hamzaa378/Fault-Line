# Verification and demonstration

## Automated checks

```bash
cd backend
python -m pip install -r requirements.txt
python -m pytest -q
```

Backend tests cover:

- Project membership isolation and role enforcement.
- Incident creation, change and deployment records, suspect ranking.
- Resolution requirements and optimistic-lock rejection of stale revisions (`409`).
- Append-only incident notes without changing the incident revision.
- Replayed external events accepted once, conflicting reused IDs rejected.
- Late event shown differently under occurrence-order versus arrival-order.
- HMAC verification of GitHub webhooks, bad-signature rejection, delivery deduplication, project and repository binding, commit imports, deployment-status imports, and suspect-score integration.

The local suite uses SQLite solely as a disposable test database. Docker Compose uses PostgreSQL, the recommended deployment DB. A previous user-run PostgreSQL test used six simultaneous incident PATCH requests (1 HTTP 200, 5 HTTP 409, persisted version 2, 1 audit record), plus six simultaneous duplicate event ingestions (1 created, 5 duplicates, exactly 1 PostgreSQL row). This is limited empirical testing, not a broad load benchmark. The new v1.1 GitHub projection tests run against disposable SQLite until the user runs the signed webhook smoke against their PostgreSQL container.

## Guided demo (two to three minutes)

1. `docker compose up --build` and open `http://localhost:3000`.
2. Sign in with the pre-filled demo credentials.
3. Open the dashboard: inspect incidents, deployments and recurring signatures.
4. Click **Checkout requests timing out**. Review its explainable ranked deployment leads; add a human investigation note and associate a candidate deployment.
5. Try updating status in two browser sessions with the same incident revision. One save succeeds, the stale save receives `409` and prompts a refresh.
6. Open **Event timeline**. Switch between **Event time** and **Arrival time**. Find the **Delayed gateway timeout alert** and its **DELAYED ARRIVAL** indicator.
7. Choose **Replay history** and move the slider to see the evidence set up to that point.
8. Export an incident investigation report in Markdown.
9. Optionally run `python scripts/demo_scenario.py` from the repository root (requires `requests`).

## Remaining checks before calling it production ready

- Build and launch the two Docker images on a machine with Docker.
- Open the UI in at least two browsers and perform the manual flow above.
- Repeat PostgreSQL multi-client race checks after deployment, then use real GitHub deliveries and verify projections against PostgreSQL.
- Add schema migrations, secure cookie sessions, rate limiting, and verified GitHub repository binding.
