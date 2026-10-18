# Stage 16 — GitHub integration (v1.1)

Start here after the existing Docker Compose project and database are already running.

## Confirmed already, from local user verification

- Docker Compose API + DB healthy; Next.js returns 200.
- Incident concurrency: six simultaneous updates -> one accepted, five 409; persisted revision 2, one audit record.
- Concurrent event ingestion: six deliveries -> one created, five duplicates; exactly one PostgreSQL row.
- 10 initial backend tests pass; Sam's role restrictions tested manually.

This v1.1 extension **does not require a schema migration** and preserves the Docker volume. Unit/HTTP-level integration tests increased from 10 to 14 in the development environment. Docker rebuild and real delivery must still be verified on the user's machine.

## Protect the existing DB and update the app

1. Run from `C:\Users\hamza\Downloads\Faultline_v1\Faultline_Fullstack`.
2. Generate a database backup inside the container, then `docker cp` to an external `.dump` file:

```powershell
docker compose exec -T db pg_dump -U faultline -d faultline -Fc -f /tmp/faultline_pre_v2.dump
$dbContainer = (docker compose ps -q db).Trim()
docker cp "${dbContainer}:/tmp/faultline_pre_v2.dump" "..\faultline_pre_v2.dump"
```

3. Expand the v1.1 distribution from its parent folder; it contains `Faultline_Fullstack` as top-level. It **does not include `.env`**. Or copy the changed files manually.
4. Edit `.env` in the existing project folder:

```dotenv
GITHUB_WEBHOOK_SECRET=REPLACE_WITH_RANDOM_GENERATED_SECRET
GITHUB_PROJECT_ID=YOUR_EXISTING_ORBIT_COMMERCE_PROJECT_UUID
GITHUB_ALLOWED_REPOSITORIES=example/faultline-demo
GITHUB_DEFAULT_SERVICE=checkout-api
```

In PowerShell generate a random value:

```powershell
-join (1..4 | ForEach-Object { [guid]::NewGuid().ToString("N") })
```

Use a real GitHub owner/repo instead of `example/faultline-demo` when you are ready to connect GitHub. Do **not** put `.env` or secret values in Git.

5. Rebuild and restart just the API, keeping the named PostgreSQL volume:

```powershell
docker compose config --quiet
docker compose up -d --build api
Invoke-RestMethod http://localhost:8000/health
```

Expected API version `1.1.0` (this project's v2 development checkpoint).

## Run signed local integration verification

After choosing the repo in `.env`, run from the project root:

```powershell
.\scripts\github_webhook_smoke.ps1 -ProjectId YOUR_PROJECT_UUID -Repo example/faultline-demo
```

If execution policy prevents the script, use a temporary process-scoped override:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

The script reads the secret from `.env` without printing it. It sends a signed push event, replays it, attempts a conflicting replay, sends an invalid signature, and sends a successful deployment status. It expects `200`/`200`/`409`/`401`/`200` respectively and verifies automatic creation of one commit and one deployment. Run it again with another random SHA/delivery and inspect the project dashboard and PostgreSQL tables.

## Receive real webhooks from GitHub without exposing the entire API

1. Choose/create a repository you control and set `GITHUB_ALLOWED_REPOSITORIES=OWNER/REPO` in `.env`. Recreate the API container (`docker compose up -d --force-recreate api`). Do not expose a demo login to the internet.
2. Start the restricted local relay in a dedicated PowerShell terminal:

```powershell
python .\scripts\webhook_gateway.py --project-id YOUR_PROJECT_UUID
```

3. Start an HTTPS tunnel pointing **only** at port `8765`, not `8000` or `3000`. Example if you installed ngrok and configured its account/token: `ngrok http 8765`.
4. In your GitHub repository: **Settings -> Webhooks -> Add webhook**. Payload URL: `https://YOUR-TUNNEL-HOST/api/webhooks/github/YOUR_PROJECT_UUID`; content type `application/json`; paste the exact secret from `.env`; select **Pushes**, **Deployments**, and **Deployment statuses**. GitHub sends a signed `ping` on registration.
5. Inspect **Recent Deliveries** in GitHub. HTTP 200 is expected for valid signed requests; 401 for invalid signatures; 403 for unapproved repos; 409 if an existing delivery ID is reused with different signed content. The event is visible in Faultline's timeline.
6. Push a small test commit. For a deployment status demonstration, use a workflow that actually creates GitHub deployments and statuses, or use the local smoke script. Ordinary push alone does not create a deployment.
7. Stop the temporary tunnel and gateway after testing. Keep the application restricted to localhost. Never commit or post the webhook secret.

## v1.1 guarantees and limits

- Signed raw bytes verified with HMAC-SHA256 before accepting an event.
- Optional project UUID and repository allowlist prevent most accidental cross-workspace routing. Both should be set for tunnel use.
- GitHub delivery ID+body digest prevents duplicate delivery projection and detects conflicting delivery replay.
- Verified push commits (present in payload) project into `code_changes` using a PostgreSQL/SQLite `ON CONFLICT DO NOTHING` uniqueness guard for SHA.
- Verified terminal deployment-status `success`, `failure`, `error` projects into `deployments` with its status timestamp. Pending or in-progress statuses remain timeline-only.
- No incidents are automatically created; deployment-cause scores remain heuristic, not causal claims.
- GitHub may truncate a push's commit list and can omit file lists in some events. This version imports only the metadata actually present in the signed webhook. Do not claim complete commit history.
- Different genuine deployment-status deliveries can create separate historical rows. Per-GitHub-deployment lifecycle consolidation needs a future schema migration and deliberate business rules.
- The single shared secret and project/repo environment restrictions suit a one-project demo, not multi-tenant SaaS. Rate limits, authentication hardening, and per-project webhook credentials remain production work.
- The gateway is a demo-only restricted router, not a production reverse proxy or denial-of-service protection.

## Review gate before calling this fully verified

- Original backend regression suite + new GitHub integration tests pass.
- Locally rebuilt API health `1.1.0`; original six incident and existing event records remain.
- Signed push, duplicate, conflict, invalid signature, deployment statuses tested against user's real PostgreSQL.
- Verified GitHub recent delivery from a repository the user controls.
- Final README/DECISIONS and deployment notes updated with test evidence.
