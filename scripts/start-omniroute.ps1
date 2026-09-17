# Inicia OmniRoute gateway (porta 20128) se ainda não estiver rodando
$port = 20128
$running = netstat -ano | Select-String ":$port\s"

if ($running) {
    Write-Host "OmniRoute ja esta rodando na porta $port"
    exit 0
}

$omniroute = "C:\Users\Cristhian Schug\AppData\Roaming\npm\omniroute.cmd"

if (-not (Test-Path $omniroute)) {
    Write-Error "omniroute.cmd nao encontrado em: $omniroute"
    exit 1
}

Write-Host "Iniciando OmniRoute..."
Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c `"$omniroute`"" `
    -WindowStyle Minimized `
    -WorkingDirectory "C:\Users\Cristhian Schug"

# Aguarda ate 15s para confirmar subida
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep 1
    $check = netstat -ano | Select-String ":$port\s"
    if ($check) {
        Write-Host "OmniRoute UP em http://localhost:$port"
        exit 0
    }
}

Write-Warning "OmniRoute nao respondeu em 15s - verifique manualmente"
