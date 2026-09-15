# Anexar ERP API v1.0

FastAPI + SQLAlchemy + Firebird - Read-Only REST API para Anexar ERP

---

## 🚀 Quick Start

### Local Development

```bash
# 1. Clone repo
git clone https://github.com/seu-user/api-anexar.git
cd api-anexar

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create .env.local (copy from .env.example)
cp .env.example .env.local
# Edit with your Firebird credentials

# 4. Run development server
python main.py
# ou
uvicorn main:app --reload

# 5. Test
curl http://localhost:8000/api/v1/health
```

### Docker Development

```bash
# Build image
docker build -t api-anexar:dev .

# Run container
docker-compose up -d

# Logs
docker logs -f anexar-api-dev

# Stop
docker-compose down
```

---

## 🧪 Testing

### Run All Tests

```bash
# Simple run
pytest

# With verbose output
pytest -v

# With coverage report
pytest --cov=. --cov-report=html

# Specific test file
pytest test_endpoints.py

# Specific test class
pytest test_endpoints.py::TestClientes

# Specific test
pytest test_endpoints.py::TestClientes::test_list_clientes_empty
```

### Test Coverage

```bash
# Generate coverage report
pytest --cov=. --cov-report=html --cov-report=term

# Open HTML report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

---

## 📚 API Endpoints

### Health Check
- `GET /api/v1/health` - Server status

### Clientes
- `GET /api/v1/clientes` - List all clientes
- `GET /api/v1/clientes/{id}` - Get cliente by ID

### Produtos
- `GET /api/v1/produtos` - List all produtos
- `GET /api/v1/produtos/{id}` - Get produto by ID

### Pedidos
- `GET /api/v1/pedidos` - List all pedidos
- `GET /api/v1/pedidos/{id}` - Get pedido by ID

### Parcelas
- `GET /api/v1/parcelas` - List all parcelas

### Fornecedores
- `GET /api/v1/fornecedores` - List all fornecedores
- `GET /api/v1/fornecedores/{id}` - Get fornecedor by ID

---

## 🔐 Security Features

- ✅ Data masking (CPF, email, telefone)
- ✅ SQL injection prevention (ORM parametrized)
- ✅ Tenant isolation (database-level)
- ✅ CORS enabled
- ✅ Read-only API (no writes)
- ✅ Container isolation (Docker)

---

## 📁 Project Structure

```
api-anexar/
├── main.py                 # FastAPI application
├── database.py             # Firebird connection
├── models.py               # SQLAlchemy models
├── schemas.py              # Pydantic DTOs
├── conftest.py             # Pytest configuration
├── test_endpoints.py       # Integration tests
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container definition
├── docker-compose.yml      # Docker orchestration
├── .env.example            # Environment template
├── .gitignore              # Git ignore rules
├── pytest.ini              # Pytest config
└── README.md               # This file
```

---

## 🔧 Environment Variables

```bash
# Database
DB_HOST=45.177.152.52
DB_PORT=40051
DB_NAME=/firebird/data/clientes/8060-TESTE-MCP-FIREBIRD/b43dbc709d1d226dcef550439169f5bb/DBANEXAR_ANEXO.FDB
DB_USER=CLI_8060_B43DBC
DB_PASSWORD=06224baf3b147d04

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-here

# API
API_TITLE=Anexar ERP API
API_VERSION=1.0.0
ENVIRONMENT=development
LOG_LEVEL=INFO
```

---

## 📊 Test Coverage

Current test suite includes:

- **Health Check:** 1 test
- **Clientes:** 6 tests (list, filter, detail, masking, 404)
- **Produtos:** 3 tests (list, detail, data)
- **Pedidos:** 3 tests (list, detail, join)
- **Parcelas:** 2 tests (list, data)
- **Fornecedores:** 2 tests (list, data)
- **Error Handling:** 2 tests (validation)

**Total: 19 tests**

---

## 🚀 Production Deployment

### Prerequisites

```bash
# Check port availability
lsof -i :9000  # Should be empty

# Check Docker
docker ps

# Check Firebird
telnet localhost 3050
```

### Deploy Steps

```bash
# 1. SSH to server
ssh anexo_tecnologia@45.177.152.60

# 2. Clone repo
cd /home/anexar_deploy
git clone https://github.com/seu-user/api-anexar.git
cd api-anexar

# 3. Setup environment
nano .env.prod  # Configure for production

# 4. Build image
docker build -t api-anexar:1.0 .

# 5. Run container
docker-compose -f docker-compose.prod.yml up -d

# 6. Verify
curl http://localhost:9000/api/v1/health

# 7. Setup Nginx (reverse proxy)
# See DEPLOYMENT_SAFETY.md for details
```

### Monitoring

```bash
# Logs
docker logs -f anexar-api-prod

# Resources
docker stats anexar-api-prod

# Health check
curl http://localhost:9000/api/v1/health

# Performance
top  # Check other services
```

### Rollback

```bash
# Stop container
docker-compose -f docker-compose.prod.yml down

# Remove image
docker rmi api-anexar:1.0

# Remove folder
rm -rf /home/anexar_deploy/api-anexar

# Restart other services
systemctl restart nginx
```

---

## 📝 Documentation

- [DEPLOYMENT_SAFETY.md](DEPLOYMENT_SAFETY.md) - Isolation & safety plan
- [FRAMEWORK_DECISION.md](FRAMEWORK_DECISION.md) - Tech stack rationale
- [00_DECISION_LOG.md](00_DECISION_LOG.md) - Architectural decisions

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

MIT

---

## 👨‍💻 Support

For issues, questions or suggestions:
1. Check existing issues
2. Create a new issue with details
3. Contact: anexo.desenvolvimento@gmail.com

---

**Version:** 1.0.0  
**Status:** Production Ready  
**Last Updated:** 2026-09-15
