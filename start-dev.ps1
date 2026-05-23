# Local dev without Docker: full Flask app + SQLite (backend/app.py)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example"
}

Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if (-not $line -or $line.StartsWith("#")) { return }
    $parts = $line -split "=", 2
    if ($parts.Count -eq 2) {
        Set-Item -Path ("env:" + $parts[0].Trim()) -Value $parts[1].Trim()
    }
}

python -m pip install -r requirements.txt -q
Write-Host "Starting dev server at http://127.0.0.1:5000"
python run_server.py
