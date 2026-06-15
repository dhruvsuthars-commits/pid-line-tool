Push-Location -Path "$PSScriptRoot\pid-line-tool"
if (-Not (Test-Path ".\venv\Scripts\Activate.ps1")) {
    Write-Error "Virtual environment not found at .\venv\Scripts\Activate.ps1"
    Pop-Location
    exit 1
}
. .\venv\Scripts\Activate.ps1
python app.py
Pop-Location
