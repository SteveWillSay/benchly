# Builds the portable single-file Benchly.exe into dist\
Set-Location $PSScriptRoot
& ".venv\Scripts\pyinstaller.exe" `
    --noconfirm --clean --onefile --windowed `
    --name Benchly `
    --icon "assets\icon.ico" `
    --version-file "version_info.txt" `
    --add-data "ui;ui" `
    --add-data "assets\icon.ico;assets" `
    app.py
Write-Host "`nPortable build: $PSScriptRoot\dist\Benchly.exe"
