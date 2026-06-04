param(
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name ParaComment `
    app/main.py
