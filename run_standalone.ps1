# SPDX-License-Identifier: MPL-2.0

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$solarisRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $solarisRoot
$pythonExe = Join-Path $repoRoot "backend\python312-embed\python.exe"
$backendScript = Join-Path $solarisRoot "run_web.py"
$frontendDir = Join-Path $solarisRoot "frontend"
$npmCmd = Get-Command "npm.cmd" -ErrorAction Stop
$healthUrl = "http://127.0.0.1:8766/api/health"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Embedded Python runtime not found at $pythonExe"
}

if (-not (Test-Path -LiteralPath $backendScript)) {
    throw "Solaris backend launcher not found at $backendScript"
}

if (-not (Test-Path -LiteralPath $frontendDir)) {
    throw "Solaris frontend directory not found at $frontendDir"
}

Write-Host "Starting Solaris web backend..." -ForegroundColor Cyan
$backend = Start-Job -Name "solaris-web" -ScriptBlock {
    param(
        [string]$PythonExe,
        [string]$BackendScript,
        [string]$RepoRoot
    )

    Set-Location $RepoRoot
    & $PythonExe $BackendScript 2>&1
} -ArgumentList $pythonExe, $backendScript, $repoRoot

$healthy = $false
$backendOutput = ""
for ($attempt = 0; $attempt -lt 60; $attempt++) {
    Start-Sleep -Milliseconds 500

    $backend = Get-Job -Id $backend.Id
    if ($backend.State -in @("Completed", "Failed", "Stopped")) {
        $backendOutput = Receive-Job -Job $backend -Keep | Out-String
        throw "Solaris backend exited early. Job state: $($backend.State)`n$backendOutput"
    }

    try {
        $health = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2
        $healthOk = $false
        if ($null -ne $health.PSObject.Properties["ok"]) {
            $healthOk = [bool]$health.ok
        } elseif ($null -ne $health.PSObject.Properties["status"]) {
            $healthOk = ($health.status -eq "ok")
        }
        if ($healthOk) {
            $healthy = $true
            break
        }
    } catch {
        continue
    }
}

if (-not $healthy) {
    try {
        $backendOutput = Receive-Job -Job $backend -Keep | Out-String
        if ($backend.State -eq "Running") {
            Stop-Job -Job $backend | Out-Null
        }
    } catch {
    }
    throw "Solaris backend did not become healthy at $healthUrl.`n$backendOutput"
}

Write-Host "Solaris backend is healthy on http://127.0.0.1:8766" -ForegroundColor Green
Write-Host "Starting Solaris frontend dev server..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the frontend. The backend will be cleaned up automatically." -ForegroundColor DarkGray

try {
    Push-Location $frontendDir
    & $npmCmd.Source run dev
} finally {
    Pop-Location
    if ($null -ne $backend) {
        try {
            $backend = Get-Job -Id $backend.Id -ErrorAction SilentlyContinue
            if ($null -ne $backend -and $backend.State -eq "Running") {
                Write-Host "Stopping Solaris backend..." -ForegroundColor Yellow
                Stop-Job -Job $backend | Out-Null
            }
            if ($null -ne $backend) {
                Remove-Job -Job $backend -Force | Out-Null
            }
        } catch {
        }
    }
}
