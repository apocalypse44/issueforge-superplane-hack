# Run IssueForge using the project venv (Windows PowerShell)
$Python = Join-Path $PSScriptRoot "venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "venv not found. Create it: python -m venv venv; .\venv\Scripts\pip install -r requirements.txt"
    exit 1
}
& $Python (Join-Path $PSScriptRoot "run_local.py") @args
exit $LASTEXITCODE
