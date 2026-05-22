# Run this script to create venv and start the app on Windows (PowerShell)
$python = "C:\Users\PB915\AppData\Local\Programs\Python\Python311\python.exe"
if (-not (Test-Path $python)) {
    Write-Error "Python not found at $python. Update this script or run python from command line."
    exit 1
}
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project
& $python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app/streamlit_app.py
