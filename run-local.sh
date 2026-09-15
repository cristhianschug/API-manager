#!/bin/bash
# Run Local Development - API + Dashboard

echo "🚀 Iniciando Ambiente Local de Desenvolvimento"
echo ""
echo "=========================================="
echo "  ERP Anexar API + Dashboard"
echo "=========================================="
echo ""

# Setup
cd "$(dirname "$0")"
source venv/Scripts/activate

echo "✅ Ambiente virtual ativado"
echo ""

# Start API in background
echo "🔧 Iniciando API FastAPI..."
python main.py &
API_PID=$!
sleep 3

# Print URLs
echo ""
echo "=========================================="
echo "  SERVIDOR LOCAL PRONTO!"
echo "=========================================="
echo ""
echo "📊 Dashboard:  http://localhost:8000/dashboard.html"
echo "🔌 API:        http://localhost:8000/api/v1/"
echo "🏥 Health:     http://localhost:8000/api/v1/health"
echo ""
echo "Endpoints disponíveis:"
echo "  • GET /api/v1/health"
echo "  • GET /api/v1/clientes"
echo "  • GET /api/v1/produtos"
echo "  • GET /api/v1/pedidos"
echo "  • GET /api/v1/parcelas"
echo "  • GET /api/v1/fornecedores"
echo ""
echo "🔐 Segurança: 20 features ativadas"
echo ""
echo "Digite Ctrl+C para parar"
echo "=========================================="
echo ""

# Keep running
wait $API_PID
