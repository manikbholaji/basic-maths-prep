# Run this script to create venv and start the app on Windows (PowerShell)
$python = "C:\Users\PB915\AppData\Local\Programs\Python\Python311\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Python not found at $python. Update this script or run python from command line."
    exit 1
}
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project
$venvPython = Join-Path $project ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    & $python -m venv .venv
    $venvPython = Join-Path $project ".venv\Scripts\python.exe"
}
& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -r requirements.txt
& $venvPython -m streamlit run app/streamlit_app.py
