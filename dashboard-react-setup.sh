#!/bin/bash
# Setup Dashboard React

echo "=== Criando projeto React ==="

# Criar pasta
mkdir -p dashboard
cd dashboard

# Criar estrutura básica
cat > package.json << 'EOF'
{
  "name": "anexar-api-dashboard",
  "version": "1.0.0",
  "description": "Dashboard para ERP Anexar API",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "axios": "^1.6.0",
    "recharts": "^2.10.0"
  },
  "scripts": {
    "start": "python -m http.server 3000",
    "build": "echo 'Build ready'"
  }
}
EOF

echo "✅ Dashboard estrutura criada em ./dashboard"
