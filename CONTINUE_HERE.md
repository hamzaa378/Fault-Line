# Faultline v1 · Continuation and handover

**Start here when continuing this project in another chat, with another developer, or on another machine.**

## 1. Source brief and implementation boundary

CodeChef-VIT 2026–27 task `Who Broke the Build?` (the Full-Stack section on page 10 of the supplied 21-page PDF). The required features are projects, deployments, code changes, incidents, timeline, associations, severity/status/assignment/resolution, multi-contributor notes, dashboard, and duplicate/delayed/conflicting event handling. Expected required submissions: full frontend/backend, schema and workflow diagrams, APIs, README and architecture. Bonuses include GitHub webhook integration, realtime updates, RBAC, deduplication/auditing, cause-link detection and deployment.

Version 1 implemented the core product, webhook, RBAC, audit log, incident leads, timeline replay and investigation export. **Unimplemented bonuses** include true realtime push (UI refreshes every 15s) and hosted deployment. No modifications to unrelated projects.

## 2. Service topology and credentials

- **Web:** Next.js / React / TypeScript (port 3000), browser talks to `http://localhost:8000`.
- **API:** Python / FastAPI / SQLAlchemy / Argon2id / JWT (port 8000).
- **DB:** PostgreSQL 16 in Compose, persistent `postgres_data`. SQLite allowed for independent tests and fast local API development, not target deployment.
- `.env.example` to `.env`; Docker Compose sets DB URL, JWT secret, optional HMAC secret, demo seed flag.
- Demo seeded owner `alex@faultline.dev` and responder `sam@faultline.dev`. Both use `SEED_PASSWORD` (default local demo password `DemoPassword123!`). Rotate all secrets before public use.

## 3. Files and module responsibilities

- `compose.yaml`: PostgreSQL, API and Next app with healthy DB/API startup order.
- `backend/app/db.py`: SQLAlchemy engine, session, dependency.
- `backend/app/models.py`: ten relational tables, indexes, unique constraints.
- `backend/app/schemas.py`: input/output types; UTC normalization and validation.
- `backend/app/auth.py`: Argon2 hashes, JWT and project permission rules.
- `backend/app/events.py`: append-only events, event fingerprints, external identity and audit helper.
- `backend/app/insights.py`: ranked suspect deployments with documented scoring reasons and recurring incident grouping.
- `backend/app/main.py`: REST routes, atomic incident revision updates, event ingestion and verified GitHub webhook endpoint.
- `backend/app/seed.py`: deterministic, idempotent Orbit Commerce demo narrative.
- `backend/tests/`: request-level tests for integrity, RBAC, incidents, replay, webhook signatures, cross-project isolation.
- `frontend/src/lib/api.ts`: strongly typed API client and shared models.
- `frontend/src/app/page.tsx`: main product shell, overview, tables, dual-clock timeline and replay slider, team and audit screens.
- `frontend/src/app/login/page.tsx`: local-demo login and registration.
- `frontend/src/components/CreateModal.tsx`: validated forms for workspaces, incidents, deployments, code changes, memberships, external events.
- `frontend/src/components/IncidentPanel.tsx`: evidence, links, team notes, conflict-aware incident changes, Markdown case export.
- `frontend/src/app/globals.css`: visual design, responsive breakpoints and forms.
- `docs/DIAGRAMS.md`: GitHub-renderable Mermaid architecture, ERD and workflow.
- `docs/schema_postgresql.sql`: generated PostgreSQL initial DDL from SQLAlchemy model metadata.
- `docs/API_EXAMPLES.md`: sample PowerShell requests and webhook setup.
- `docs/TESTING.md`: automated and manual verification flows.
- `docs/RISK_AND_LIMITATIONS.md`: constraints and security hardening.
- `docs/DEMO_SCRIPT.md`: a short interview-grade walkthrough.
- `DECISIONS.md`: trade-off facts to rewrite in your own words.
- `scripts/demo_scenario.py`: deterministic style scenario runner with unique IDs, duplicated and delayed events.
- `.github/workflows/verify.yml`: tests and frontend build pipeline.

## 4. Exact commands

Windows PowerShell (from project root):

```powershell
Copy-Item .env.example .env
# For demo keep SEED_PASSWORD, change other secrets
# Docker Desktop must be running
docker compose up --build -d
docker compose ps
# Browse http://localhost:3000 and http://localhost:8000/docs
```

Standalone API tests:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest -q
```

Standalone frontend:

```powershell
cd frontend
npm install
npm run typecheck
npm run build
npm run dev
```

## 5. Verification at v1 checkpoint

- **10 backend Pytest cases: PASS** in the available Python environment (SQLite test DB). Test suite includes auth/access, role restrictions, idempotency/conflict, double timeline clocks, incident CAS updates, notes, GitHub HMAC and cross-project isolation.
- **Backend startup smoke: PASS**: seeded workspace, login, dashboard (4 incidents, 3 active, 3 deployments), suspect endpoint using temporary SQLite database.
- **Frontend static syntax: PASS**: TypeScript compiler `transpileModule()` parsed six TS/TSX files without syntax errors. CSS parser checked 334 rules, 0 errors.
- **Frontend dependency installation/build: NOT RUN**: this runtime cannot resolve `registry.npmjs.org` (EAI_AGAIN). This is an environment blocker, not proof of code compilation.
- **Docker Compose run / PostgreSQL integration: NOT RUN**: Docker CLI/daemon is not installed in this runtime. Do not claim deployment success or verified Postgres concurrency.
- **Hosted live deployment: NOT DONE**.

## 6. Current known limitations and high-priority backlog

1. On an Internet-connected PC, install Node dependencies, run `npm run typecheck` and `npm run build`. Fix any compatibility issues found by a real Next.js build. Run Docker Compose on Windows and smoke test the REST/React user journey end-to-end.
2. Run a **PostgreSQL two-writer race test** for simultaneous incident state update and duplicate event ingestion to verify uniqueness and optimistic locking under actual DB concurrency.
3. Add migrations (Alembic) before introducing database alterations; `Base.metadata.create_all` is only initial-create.
4. Strengthen production security: HttpOnly cookies, CSRF, rate limiting, credential rotation, HMAC per-project and trusted repository binding, HTTPS.
5. Map validated GitHub commit/deployment webhook payloads into actual domain records, not just immutable timeline evidence.
6. Add SSE/WebSocket realtime if schedule permits. Currently the app auto-refreshes every 15 seconds.
7. Add integration tests with browser automation (Playwright) and record a short product demonstration video.
8. Consider pagination/index-aware streaming for larger projects. Current capped list endpoints suffice for a technical demo.

## 7. What not to break during continuation

- Never silently overwrite incident revisions. Preserve the API `expected_version` protocol.
- Do not collapse occurrence time and arrival time into one timestamp.
- Do not replace database enforced uniqueness with only an in-memory deduplication set.
- Suspect scoring is an investigation heuristic. The UI and reports must not label ranked releases as proven root causes.
- Preserve all existing response structures unless frontend and tests are updated together.
- Keep `.env` out of Git and distribution archives; keep `.env.example` only.

**Suggested v2 starting point:** First run the frontend typecheck and Docker Compose acceptance tests on the user's Windows machine. Do not add speculative features before verifying the full stack can run locally.
