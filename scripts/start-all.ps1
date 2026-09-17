# Inicia todos os servicos Anexar: OmniRoute + API
param([int]$ApiPort = 8000)

Write-Host "=== Anexar Services Startup ==="

# 1. OmniRoute
& "$PSScriptRoot\start-omniroute.ps1"

# 2. API (com delay para dar tempo ao OmniRoute)
Start-Sleep 3
& "$PSScriptRoot\start-api.ps1" -Port $ApiPort

Write-Host ""
Write-Host "Servicos disponiveis:"
Write-Host "  API Anexar  : http://localhost:$ApiPort"
Write-Host "  Admin panel : http://localhost:$ApiPort/admin"
Write-Host "  OmniRoute   : http://localhost:20128/dashboard/free-tiers"
