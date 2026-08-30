[CmdletBinding()]
param(
    [string]$PythonExecutable = "python",
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-ReleaseStep {
    param([string]$Name, [scriptblock]$Command)
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

$frontendRoot = Join-Path $repoRoot "frontend"

Push-Location $repoRoot
try {
    Invoke-ReleaseStep "Check unstaged whitespace errors" {
        git diff --check
    }

    Invoke-ReleaseStep "Check staged whitespace errors" {
        git diff --cached --check
    }

    if ($InstallDependencies) {
        Invoke-ReleaseStep "Install backend development dependencies" {
            & $PythonExecutable -m pip install -r backend/requirements-dev.txt
        }

        Push-Location $frontendRoot
        try {
            Invoke-ReleaseStep "Install frontend dependencies" {
                npm ci
            }
        }
        finally {
            Pop-Location
        }
    }

    Invoke-ReleaseStep "Run backend tests" {
        & $PythonExecutable -m pytest backend/tests -q
    }

    Push-Location $frontendRoot
    try {
        Invoke-ReleaseStep "Run frontend tests" {
            npm test -- --run
        }

        Invoke-ReleaseStep "Build frontend" {
            npm run build
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    Pop-Location
}

Write-Host "Local-only release verification complete; no remote or deployment action was performed." -ForegroundColor Green
