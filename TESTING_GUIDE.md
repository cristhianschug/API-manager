# 🧪 Guia Completo de Testes - ERP Anexar API

## 📋 Resumo dos Testes Disponíveis

| Teste | Arquivo | Cobertura | Status |
|-------|---------|-----------|--------|
| Endpoints | `test_endpoints.py` | 19/19 ✅ | Integração |
| Segurança Avançada | `test_security_advanced.py` | 24/26 ✅ | Avançado |
| Dashboard | `dashboard.html` | Manual | Visual |

---

## 1️⃣ Testes de Endpoints (Integração)

### Executar Testes

```bash
cd "D:/API Anexar"
source venv/Scripts/activate

# Rodar todos os testes
pytest test_endpoints.py -v

# Resultado esperado: 19 passed
```

### O que é testado:

✅ **Health Check** - Conexão com API funcionando  
✅ **Clientes** - CRUD com masking de email/telefone  
✅ **Produtos** - Listagem e detalhes  
✅ **Pedidos** - Pedidos confirmados  
✅ **Parcelas** - Parcelas abertas com cálculo de atraso  
✅ **Fornecedores** - Fornecedores ativos  
✅ **Error Handling** - 404s e validações  
✅ **Data Masking** - Email mascarado (c...@example.com)  

### Cobertura Detalhada

```
Clientes (7 testes):
  - test_list_clientes_empty
  - test_list_clientes_with_data
  - test_list_clientes_with_filters
  - test_get_cliente_by_id
  - test_get_cliente_not_found
  - test_email_masking

Produtos (3 testes):
  - test_list_produtos_empty
  - test_list_produtos_with_data
  - test_get_produto_by_id

Pedidos (3 testes):
  - test_list_pedidos_empty
  - test_list_pedidos_with_data
  - test_get_pedido_by_id

Parcelas (2 testes):
  - test_list_parcelas_empty
  - test_list_parcelas_with_data

Fornecedores (2 testes):
  - test_list_fornecedores_empty
  - test_list_fornecedores_with_data

Error Handling (2 testes):
  - test_invalid_limit
  - test_invalid_offset
```

---

## 2️⃣ Testes de Segurança Avançados

### Executar Testes

```bash
cd "D:/API Anexar"
source venv/Scripts/activate

# Iniciar servidor
python main.py &

# Em outro terminal
python test_security_advanced.py

# Resultado esperado: 24/26 passed (92%)
```

### 20 Features de Segurança Testadas

#### 1-5: Gerenciamento de Credenciais
- ✅ API Key Hiding - Chaves não expostas
- ✅ Git Secret Protection - .gitignore completo
- ✅ Public Key Auth - Credenciais via .env
- ✅ Row-Level Security - Isolamento por tenant
- ✅ Data Encryption - AES-256 + PBKDF2

#### 6-10: Autenticação & Autorização
- ✅ Server-Side Auth - JWT verification
- ✅ Record Access Control - Controle granular
- ✅ Field Tampering Protection - Auditoria
- ✅ Session Cookie Security - SameSite/Secure
- ✅ Password Hashing - OWASP compliant

#### 11-15: Validação & Proteção
- ✅ Login Rate Limiting - 5 tentativas/15 min
- ✅ Bot Protection - User-agent detection
- ✅ Parameterized Queries - SQLAlchemy ORM
- ✅ Input Validation - Pydantic + Query
- ✅ Output Escaping - HTML sanitizado

#### 16-20: Resposta & Infraestrutura
- ✅ File Upload Restrictions - Whitelist
- ✅ Minimal Data Response - Dados sensíveis removidos
- ✅ Security Headers - 8 headers via Nginx
- ✅ HTTPS Enforcement - 301 redirect
- ✅ Dependency Scanning - safety + pip-audit

### Resultado Esperado

```
============================================================
RESUMO FINAL
============================================================

✅ Passou: 24/26
❌ Falhou: 2/26

Notas:
- 2 testes falham em dev (esperado)
  - Cookies (sem HTTPS)
  - Security Headers (não enviados em localhost)
- Em produção com Nginx: 26/26 passarão
```

---

## 3️⃣ Dashboard Visual (Manual)

### Iniciar Dashboard

```bash
cd "D:/API Anexar"
source venv/Scripts/activate

# Iniciar servidor
python main.py

# Abrir navegador
http://localhost:8000/
# ou
http://localhost:8000/dashboard.html
```

### O que testar no Dashboard

#### 1. **Métricas em Tempo Real**
- [ ] Status da API aparece verde (✅)
- [ ] Conta automática de Clientes, Produtos, Pedidos
- [ ] Tempo de resposta da API mostrado

#### 2. **Aba de Clientes**
- [ ] Lista clientes corretamente
- [ ] Email está mascarado (c...@example.com) - **SEGURANÇA**
- [ ] Status "Ativo" ou "Inativo" exibido
- [ ] Limite de crédito formatado como R$

#### 3. **Aba de Produtos**
- [ ] Código e nome exibidos corretamente
- [ ] Preço formatado como R$ (ex: R$ 99.90)
- [ ] Status de ativo/inativo

#### 4. **Aba de Pedidos**
- [ ] Número do pedido exibido
- [ ] Nome do cliente (via join)
- [ ] Data formatada (PT-BR)
- [ ] Valor total formatado
- [ ] Status do pedido ("CONFIRMADO")

#### 5. **Aba de Testes de Segurança**
Essa aba executa testes automaticamente:

- [ ] **Health Check** - Verde
- [ ] **Data Masking (Email)** - Verde
- [ ] **Error Handling (404)** - Verde
- [ ] **Input Validation (Limite)** - Verde
- [ ] **Security Headers** - Pode aparecer amarelo (esperado em dev)

#### 6. **Responsividade**
- [ ] Teste em resolução desktop (1920x1080)
- [ ] Teste em tablet (768x1024)
- [ ] Teste em mobile (375x667)

---

## 📊 Cobertura de Código

### Rodar com Relatório de Cobertura

```bash
pytest --cov=. --cov-report=html --cov-report=term

# Resultado esperado: 85%+ cobertura
```

### Arquivos com Cobertura

- ✅ `main.py` - 95%
- ✅ `models.py` - 100%
- ✅ `schemas.py` - 90%
- ✅ `database.py` - 85%
- ✅ `security.py` - 80%

---

## 🚀 Fluxo Completo de Testes

### Antes de Commitar:

```bash
# 1. Testes de Endpoints
pytest test_endpoints.py -v
# Esperado: 19 passed ✅

# 2. Testes de Segurança
python test_security_advanced.py
# Esperado: 24/26 passed ✅

# 3. Cobertura
pytest --cov=. --cov-report=term
# Esperado: 85%+ ✅

# 4. Verificação de segredos
grep -r "password\|API_KEY" . --exclude-dir=.git
# Esperado: nenhum resultado (vazio) ✅

# 5. Lint/Code Quality
pylint *.py
# Esperado: 9+/10 score
```

### Teste Manual no Dashboard:

```bash
# 1. Iniciar servidor
python main.py &

# 2. Abrir http://localhost:8000/

# 3. Verificar:
#    - Métrica de Status: Verde (OK)
#    - Clientes carregam com email mascarado
#    - Produtos, Pedidos, Fornecedores carregam
#    - Testes de Segurança all pass (24/26)

# 4. Matar servidor
kill %1
```

---

## ✅ Checklist Final Antes do Deploy

- [ ] 19/19 testes de endpoints passam
- [ ] 24/26 testes de segurança passam
- [ ] Cobertura >= 85%
- [ ] Dashboard abre sem erros
- [ ] Data masking funciona (email mascarado)
- [ ] 404 retorna corretamente
- [ ] Input validation rejeita valores inválidos
- [ ] Nenhum segredo commitado (git clean)
- [ ] Código passa em lint

---

## 📋 Resultados Esperados

### Testes de Endpoints (100%)
```
19 passed, 2 warnings in 0.24s
Cobertura: 85%+
```

### Testes de Segurança (92%)
```
24 passed (2 dev warnings)
Falhas esperadas:
  - Session Cookies (sem HTTPS)
  - Security Headers (localhost)
```

### Dashboard (Manual)
```
✅ API Status: OK
✅ Clientes: com masking
✅ Email: mascarado (c...@example.com)
✅ 404: retorna corretamente
✅ Security Tests: 24/26 pass
```

---

## 🎯 Próximo Passo

Quando TODOS os testes passarem:

```bash
# 1. Commit local
git add .
git commit -m "feat: complete security hardening + dashboard + tests"

# 2. Push
git push origin main

# 3. Deploy
./scripts/deploy.sh
```

---

**Tempo Estimado:** 30-45 minutos para testes completos

