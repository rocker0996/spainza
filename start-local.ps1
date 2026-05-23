# Start Spainza stack locally (site + API + Postgres on http://localhost:8080)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".env.production")) {
    Write-Host "Missing .env.production. Copy from .env.production.example or ask the team."
    exit 1
}

docker compose `
  --env-file .env.production `
  -f docker-compose.production.yml `
  -f docker-compose.local.yml `
  up -d --build --remove-orphans

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Spainza local stack is starting."
Write-Host "  Site + API:  http://localhost:8080"
Write-Host "  Login:       http://localhost:8080/frontend/login.html"
Write-Host "  LK:          http://localhost:8080/frontend/lk/dashboard.html"
Write-Host ""
Write-Host "Bootstrap logins: see BOOTSTRAP_* in .env.production (not in git)."
Write-Host ""
Write-Host "Status: docker compose --env-file .env.production -f docker-compose.production.yml -f docker-compose.local.yml ps"
Write-Host "Stop:   docker compose --env-file .env.production -f docker-compose.production.yml -f docker-compose.local.yml down"
