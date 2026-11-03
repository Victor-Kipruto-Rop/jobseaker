$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Push-Location $repoRoot
try {
    Write-Host "== Python compile ==" -ForegroundColor Cyan
    python -m compileall -q apps packages tests migrations scripts
    if ($LASTEXITCODE -ne 0) { throw "Python compilation failed." }

    Write-Host "== Python tests ==" -ForegroundColor Cyan
    python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed." }

    Write-Host "== Ruff ==" -ForegroundColor Cyan
    ruff check .
    if ($LASTEXITCODE -ne 0) { throw "Ruff reported issues." }

    Write-Host "== Web TypeScript check ==" -ForegroundColor Cyan
    Push-Location (Join-Path $repoRoot "apps\web")
    try {
        pnpm lint
        if ($LASTEXITCODE -ne 0) { throw "Web TypeScript check failed." }

        Write-Host "== Web production build ==" -ForegroundColor Cyan
        pnpm build
        if ($LASTEXITCODE -ne 0) { throw "Web production build failed." }
    }
    finally {
        Pop-Location
    }

    Write-Host "== Docker Compose validation ==" -ForegroundColor Cyan
    docker compose -f infrastructure/compose/docker-compose.yml config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Docker Compose configuration is invalid." }

    Write-Host "All local static, test, frontend and Compose checks passed." -ForegroundColor Green
}
finally {
    Pop-Location
}
