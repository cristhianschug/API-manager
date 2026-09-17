# Inicia a API Anexar (FastAPI + uvicorn) se ainda nao estiver rodando
param(
    [int]$Port = 8000
)

$running = netstat -ano | Select-String ":$Port\s.*LISTENING"
if ($running) {
    Write-Host "API ja esta rodando na porta $Port"
    exit 0
}

$apiDir = "D:\API Anexar"
$python  = Join-Path $apiDir "venv\Scripts\python.exe"

# Fallback para python do PATH se venv nao existir
if (-not (Test-Path $python)) {
    $python = (Get-Command python -ErrorAction SilentlyContinue).Source
}

if (-not $python) {
    Write-Error "Python nao encontrado"
    exit 1
}

Write-Host "Iniciando API Anexar na porta $Port..."
Start-Process -FilePath $python `
    -ArgumentList "-m uvicorn main:app --host 0.0.0.0 --port $Port --reload" `
    -WorkingDirectory $apiDir `
    -WindowStyle Minimized

Write-Host "API iniciada (aguarde ~5s para startup completo)"
