# API quick reference

All `/api/projects/...` routes require a bearer token. Open <http://localhost:8000/docs> for interactive REST/OpenAPI documentation including validation models.

## Obtain a token (PowerShell)

```powershell
$body = @{email='alex@faultline.dev'; password='DemoPassword123!'} | ConvertTo-Json
$login = Invoke-RestMethod -Uri http://localhost:8000/api/auth/login -Method POST -ContentType 'application/json' -Body $body
$headers = @{Authorization = "Bearer $($login.access_token)"}
$projects = Invoke-RestMethod -Uri http://localhost:8000/api/projects -Headers $headers
$pid = $projects[0].id
```

## Add an incident

```powershell
$incident = @{title='API latency spike'; service='checkout-api'; severity='SEV2'; description='P95 response exceeded 2 s'; first_seen_at=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/projects/$pid/incidents" -Headers $headers -Method POST -Body $incident -ContentType 'application/json'
```

## Fetch the incident investigation leads

```powershell
$incidents = Invoke-RestMethod -Uri "http://localhost:8000/api/projects/$pid/incidents" -Headers $headers
$iid = $incidents[0].id
Invoke-RestMethod -Uri "http://localhost:8000/api/projects/$pid/incidents/$iid/suspects" -Headers $headers
```

## See the two histories

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/projects/$pid/events?order=occurred" -Headers $headers
Invoke-RestMethod -Uri "http://localhost:8000/api/projects/$pid/events?order=received" -Headers $headers
```

## Ingest an event idempotently

```powershell
$event = @{source='monitor';external_id='external-alert-100';type='alert';summary='Queue depth exceeded threshold';occurred_at=[DateTime]::UtcNow.AddMinutes(-45).ToString('o');details=@{queue='billing'}} | ConvertTo-Json
Invoke-RestMethod -Uri "http://localhost:8000/api/projects/$pid/events/ingest" -Headers $headers -Method POST -Body $event -ContentType 'application/json'
```

Sending the same payload twice returns `duplicate: true` with the same event ID. Reusing a `(project_id, source, external_id)` with different content returns HTTP 409. All received timestamps are server generated.

## GitHub webhook integration

1. Set `GITHUB_WEBHOOK_SECRET` in `.env` and restart the API.
2. In GitHub, configure a webhook with content type `application/json` and a matching secret. Use the URL `https://YOUR-HOST/api/webhooks/github/PROJECT_ID` (GitHub cannot call your private localhost directly).
3. Select `push`, `deployment`, and `deployment_status` event kinds.
4. The API verifies `X-Hub-Signature-256` using HMAC-SHA256 and deduplicates by GitHub delivery ID.

In v1.1 the integration creates **timeline evidence plus bounded commit and terminal deployment-status projections**. See `GITHUB_WEBHOOK_STAGE16.md` for repository/project binding, test requests, limited payload behavior, and safe tunnel setup. Per-project secrets are future work.
