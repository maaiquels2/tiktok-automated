$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível criar o ambiente Python.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar as dependências Python.' }
Push-Location -LiteralPath frontend
try {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar a interface.' }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar a interface.' }
} finally { Pop-Location }
Write-Host 'Pronto. Abra iniciar.vbs para iniciar a Fábrica TikTok.'
