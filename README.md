# Faultline · Who Broke the Build?

**A full-stack, evidence-first deployment and incident investigation platform.** Built for CodeChef-VIT's Promotional Cycle 2026–27 Full-Stack challenge (page 10 of the brief).

The task's hard parts are out-of-order events, duplicated notifications, incomplete deployment history, and several teammates editing the same incident. Faultline treats those as data-integrity problems, not merely UI states. It preserves an append-only evidence stream, tracks occurrence and receipt timestamps independently, and refuses conflicting writes.

## Run locally with Docker (recommended)

Install Docker Desktop and enable Docker Compose. From the repository root:

```powershell
Copy-Item .env.example .env
# Edit .env as needed
# Build and start the complete stack
docker compose up --build -d
# Show startup status
docker compose ps
```

- **Web app:** http://localhost:3000
- **Interactive API docs:** http://localhost:8000/docs
- **API health:** http://localhost:8000/health
- **PostgreSQL:** internal Docker network with persistent volume `postgres_data`.

Demo accounts are seeded on initial startup (and not duplicated on subsequent starts):

| Email | Password | Role |
|---|---|---|
| `alex@faultline.dev` | value of `SEED_PASSWORD` (default `DemoPassword123!`) | Workspace owner |
| `sam@faultline.dev` | same demo password | Responder |

Open the app and sign in as Alex. The dashboard contains sample deployments, two related timeout incidents, a delayed monitor event, and team notes. The login page pre-fills local demo credentials. Do not reuse them outside your machine.

To stop: `docker compose down`. **Warning:** `docker compose down -v` deletes the database volume and all records.

## Technology

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 15, React 19, TypeScript, hand-crafted CSS | Typed, responsive, interactive dashboard |
| Backend | FastAPI, Python | Clear REST validation, OpenAPI, fast implementation |
| Database | PostgreSQL 16 + SQLAlchemy | Transactions, unique constraints, optimistic version checks |
| Auth | JWT + Argon2id + project roles | Authenticated operations and role boundaries |
| Containers | Docker Compose | Reproducible web / API / database stack |
| Tests | Pytest + HTTPX TestClient | Request-level acceptance scenarios |
| CI | GitHub Actions | Backend tests plus frontend typecheck/build |

## Features matched to the task

| Brief requirement | Implementation |
|---|---|
| Create and manage software projects | Workspaces, membership table, project selection and creation |
| Record deployments, code changes and incidents | Dedicated REST endpoints and frontend forms |
| Maintain per-project event timeline | Append-only event table; chronological ordering |
| Associate incidents with suspect deployments | Explainable ranked candidates + explicit human-linked associations |
| Severity, status, assignee and resolution | Editable incident drawer with mandatory resolution notes |
| Multiple team contributors | Append-only notes, role permissions, optimistic-lock state changes |
| Summary dashboard and recurring issues | Metrics, incident status, recurring normalized title signatures |
| Duplicate, delayed, conflicting events | Event identity constraints, content digest, dual-clock timeline, HTTP 409 conflicts |

### Bonus / original extensions

- **Signed GitHub webhooks (v1.1):** HMAC-SHA256 verification, project/repository allowlists, stable delivery ID deduplication, automatic commit imports from `push`, and terminal deployment records from `deployment_status`. See `docs/GITHUB_WEBHOOK_STAGE16.md`.
- **Four project roles:** owner, maintainer, responder, viewer enforced by backend authorization.
- **Full action audit:** actor, action, before/after details and immutable incident notes.
- **Transparent deployment lead scoring:** relative timing, affected service, deployment state and matching commit. Each score includes reasons and warns against causal assumptions.
- **Time-machine replay:** a dual-clock slider reconstructs which events are visible at an earlier point.
- **Investigation export:** generates a Markdown case report with suspect evidence and team notes.
- **Data-integrity demonstration:** sample backdated notifications plus automatic conflict responses make edge cases visible to reviewers.

**Scope note:** The UI refreshes every 15 seconds, not via realtime push. GitHub events must be signed and bound to the intended project/repository when exposed. An actual internet deployment is not provided. See `docs/RISK_AND_LIMITATIONS.md`.

## Architecture and workflow

See the [rendered Mermaid diagrams](docs/DIAGRAMS.md) on GitHub, or inspect the editable source files:

- [`docs/architecture.mmd`](docs/architecture.mmd): components, boundaries, sources.
- [`docs/schema.mmd`](docs/schema.mmd): database ER diagram and table relationships.
- [`docs/workflow.mmd`](docs/workflow.mmd): retries, event ordering and optimistic updates.

**Core invariant A:** An external event has one identity: `(project_id, source, external_id)`. Exact repeated data returns `duplicate=true`, but the same identity with different content returns HTTP 409. The DB unique constraint is the final source of truth.

**Core invariant B:** The timeline never confuses `occurred_at` with server-generated `received_at`. A delayed event can enter today but appear before yesterday's deployment in occurrence order.

**Core invariant C:** Incident state changes require the caller's last observed `version`. A stale update cannot overwrite newer status/severity/assignment decisions. Independent notes append without changing that version.

## API entry points

- `POST /api/auth/register`, `POST /api/auth/login`, `GET /api/auth/me`
- `GET /api/projects`, `POST /api/projects`, `GET /api/projects/{id}`
- `GET/POST /api/projects/{id}/members`
- `GET/POST /api/projects/{id}/deployments`
- `GET/POST /api/projects/{id}/changes`
- `GET/POST /api/projects/{id}/incidents`, `PATCH /api/projects/{id}/incidents/{incident_id}`
- `GET/POST .../incidents/{incident_id}/updates`, `GET/POST .../links`, `GET .../suspects`
- `GET /api/projects/{id}/dashboard`, `GET /api/projects/{id}/events?order=occurred|received`
- `POST /api/projects/{id}/events/ingest`, `GET /api/projects/{id}/audit`
- `POST /api/webhooks/github/{id}` (signature, project/repository binding and delivery dedupe; see Stage 16 guide)

PowerShell examples are in [`docs/API_EXAMPLES.md`](docs/API_EXAMPLES.md).

## Local development without Docker

You can run the API with a throwaway SQLite DB for quick development. PostgreSQL is the intended deployment database.

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SEED_DEMO='true'
$env:JWT_SECRET='a-local-only-long-random-secret'
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
$env:NEXT_PUBLIC_API_URL='http://localhost:8000'
npm run dev
```

Tests:

```powershell
cd backend
python -m pytest -q
```

The frontend can be checked with `npm run typecheck` and `npm run build`. The GitHub workflow runs both suites on new commits.

## Submission guidance

Push the **contents of this folder** to a public GitHub repository after reviewing secrets, running your own Docker build, and validating the walkthrough. The recruiter requires a repo with a README, working frontend and backend, database and workflow diagrams, and a clear explanation of limitations. All are organized here. Use [`docs/TESTING.md`](docs/TESTING.md) for the demo; adapt [`DECISIONS.md`](DECISIONS.md) into your personal technical explanation, as the task sheet encourages.

## Repository structure

```text
backend/app/          Domain models, auth, event ingestion, scoring, API, demo seed
backend/tests/        HTTP-level regression scenarios
frontend/src/app/     Next.js routes, dashboard, login, custom styling
frontend/src/components/   Incident investigator and CRUD forms
docs/                 ERD, architecture, workflow, verification, examples, limitations
scripts/              Reproducible scenario demonstrating core edge cases
.github/workflows/    Verification job
compose.yaml          Local three-service deployment
.env.example          Dev environment template (safe to commit)
DECISIONS.md          Technical trade-off notes to personalize
```

**This is a technical demonstration, not a production incident management service.** See known limitations before deploying.

## Stage 16: GitHub webhook setup and verification

See **[`docs/GITHUB_WEBHOOK_STAGE16.md`](docs/GITHUB_WEBHOOK_STAGE16.md)** for an existing-data-safe upgrade, Windows PowerShell signed smoke test, and webhook-only HTTPS tunnel procedure. The live PostgreSQL volume is not changed by this release.
