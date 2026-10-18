<#
  Run from Faultline_Fullstack root in Windows PowerShell 5.1+.
  Uses the GitHub webhook secret from .env, without printing the secret.
  Sends signed events to the locally running API and asserts the results.
#>
param(
    [Parameter(Mandatory=$true)][string]$ProjectId,
    [string]$Repo = 'example/faultline-demo',
    [string]$BaseUrl = 'http://localhost:8000'
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path '.env')) { throw 'Run this from the Faultline_Fullstack directory containing .env.' }
$line = Get-Content '.env' | Where-Object { $_ -match '^GITHUB_WEBHOOK_SECRET=' } | Select-Object -Last 1
if (-not $line) { throw 'GITHUB_WEBHOOK_SECRET is absent from .env.' }
$secret = $line.Substring('GITHUB_WEBHOOK_SECRET='.Length).Trim().Trim('"').Trim("'")
if (-not $secret) { throw 'GITHUB_WEBHOOK_SECRET is empty in .env.' }
$base = $BaseUrl.TrimEnd('/')
$endpoint = "$base/api/webhooks/github/$ProjectId"

function Send-SignedEvent {
    param([hashtable]$Payload, [string]$EventName, [string]$DeliveryId, [bool]$BadSignature = $false)
    $raw = ConvertTo-Json -InputObject $Payload -Depth 20 -Compress
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($raw)
    $key = [System.Text.Encoding]::UTF8.GetBytes($secret)
    $hmac = [System.Security.Cryptography.HMACSHA256]::new($key)
    try { $digest = [BitConverter]::ToString($hmac.ComputeHash($bytes)).Replace('-','').ToLowerInvariant() }
    finally { $hmac.Dispose() }
    $sig = if ($BadSignature) { 'sha256=invalid-signature' } else { 'sha256=' + $digest }
    $headers = @{'X-Hub-Signature-256'=$sig; 'X-GitHub-Event'=$EventName; 'X-GitHub-Delivery'=$DeliveryId}
    try {
        $response = Invoke-WebRequest -Uri $endpoint -Method POST -ContentType 'application/json' `
            -Headers $headers -Body $bytes -UseBasicParsing -ErrorAction Stop
        return [pscustomobject]@{ HTTP=[int]$response.StatusCode; Data=($response.Content | ConvertFrom-Json) }
    }
    catch {
        $code = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 }
        return [pscustomobject]@{ HTTP=$code; Data=$null }
    }
}
function Assert-Outcome {
    param([string]$Name, [bool]$Ok, [string]$Observed)
    if ($Ok) { Write-Host "PASS: $Name - $Observed" }
    else { throw "FAIL: $Name - $Observed" }
}

$run = [guid]::NewGuid().ToString('N')
$sha = $run + '12345678'
$moment = [DateTimeOffset]::UtcNow
$push = @{
    repository=@{full_name=$Repo}
    ref='refs/heads/main'
    after=$sha
    head_commit=@{timestamp=$moment.AddMinutes(-15).ToString('o')}
    commits=@(@{id=$sha;message='Smoke test commit: checkout fix';
        timestamp=$moment.AddMinutes(-15).ToString('o');author=@{name='Local QA'};
        added=@('checkout/retry.py');modified=@('checkout/test_retry.py');removed=@()})
}
$pushId = [guid]::NewGuid().ToString()
$first = Send-SignedEvent -Payload $push -EventName 'push' -DeliveryId $pushId
Assert-Outcome 'Signed push creates commit' ($first.HTTP -eq 200 -and $first.Data.new_changes -eq 1 -and $first.Data.duplicate -eq $false) "HTTP $($first.HTTP), changes=$($first.Data.new_changes)"
$replayed = Send-SignedEvent -Payload $push -EventName 'push' -DeliveryId $pushId
Assert-Outcome 'Replay returns same event' ($replayed.HTTP -eq 200 -and $replayed.Data.duplicate -eq $true -and $replayed.Data.event_id -eq $first.Data.event_id) "HTTP $($replayed.HTTP), duplicate=$($replayed.Data.duplicate)"
$altered = $push.Clone(); $altered.ref = 'refs/heads/changed'
$conflict = Send-SignedEvent -Payload $altered -EventName 'push' -DeliveryId $pushId
Assert-Outcome 'Conflicting replay blocked' ($conflict.HTTP -eq 409) "HTTP $($conflict.HTTP)"
$forged = Send-SignedEvent -Payload $push -EventName 'push' -DeliveryId ([guid]::NewGuid().ToString()) -BadSignature $true
Assert-Outcome 'Invalid signature blocked' ($forged.HTTP -eq 401) "HTTP $($forged.HTTP)"

$deployment = @{id=$moment.ToUnixTimeMilliseconds(); sha=$sha; ref="v-local-$($run.Substring(0,8))";
                environment='production'; payload=@{service='checkout-api'};
                created_at=$moment.AddMinutes(-10).ToString('o')}
$status = @{repository=@{full_name=$Repo}; deployment=$deployment;
            deployment_status=@{state='success'; created_at=$moment.AddMinutes(-5).ToString('o')}}
$release = Send-SignedEvent -Payload $status -EventName 'deployment_status' -DeliveryId ([guid]::NewGuid().ToString())
Assert-Outcome 'Deployment status creates record' ($release.HTTP -eq 200 -and $release.Data.new_deployments -eq 1) "HTTP $($release.HTTP), deployments=$($release.Data.new_deployments)"
Write-Host 'ALL WEBHOOK SMOKE TESTS PASSED. Verify changes and deployments in the Faultline dashboard.'
