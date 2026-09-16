# OmniRoute AI Gateway Integration

## Overview

Este projeto agora integra **OmniRoute** como gateway de IA, permitindo usar ~1.47B tokens gratuitos/mês de múltiplos provedores (Claude, GPT, Gemini, etc.) através de um único endpoint.

## Arquitetura

```
FastAPI Anexar API
    ↓
AI Routes (/api/v1/ai/*)
    ↓
OmniRoute Client (OpenAI-compatible)
    ↓
OmniRoute Gateway (localhost:20128)
    ↓
352+ AI Providers (free tiers + paid)
```

## Setup

### 1. Instalar OmniRoute globalmente

```bash
npm install -g omniroute
```

### 2. Iniciar OmniRoute

```bash
omniroute
```

Servidor estará disponível em: `http://localhost:20128`

Dashboard: `http://localhost:20128/dashboard/free-tiers`

### 3. Instalar dependências Python

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

No `.env.local`:

```env
OMNIROUTE_URL=http://localhost:20128/v1
OMNIROUTE_MODEL=auto
```

## Endpoints de IA

### POST `/api/v1/ai/summarize`

Resumir texto usando IA.

**Request:**
```json
{
  "text": "Texto longo para resumir...",
  "max_tokens": 200
}
```

**Response:**
```json
{
  "original_length": 1234,
  "summary": "Resumo do texto...",
  "model": "omniroute/auto"
}
```

### POST `/api/v1/ai/generate-description`

Gerar descrição de produto/serviço.

**Request:**
```json
{
  "subject": "Notebook Dell",
  "context": "Produto de entrada, bom custo-benefício",
  "max_tokens": 300
}
```

**Response:**
```json
{
  "subject": "Notebook Dell",
  "description": "Notebook com processador Intel i5, 8GB RAM...",
  "model": "omniroute/auto"
}
```

### POST `/api/v1/ai/analyze`

Analisar dados e responder perguntas.

**Request:**
```json
{
  "data": {
    "total_vendas": 50000,
    "total_clientes": 150,
    "ticket_medio": 333.33
  },
  "query": "Qual é a tendência de vendas?",
  "max_tokens": 400
}
```

**Response:**
```json
{
  "query": "Qual é a tendência de vendas?",
  "analysis": "Com base nos dados, a tendência mostra...",
  "model": "omniroute/auto"
}
```

### GET `/api/v1/ai/status`

Verificar status do gateway OmniRoute.

**Response:**
```json
{
  "status": "ok",
  "gateway": "omniroute",
  "endpoint": "http://localhost:20128/v1"
}
```

## Autenticação

Todos os endpoints de IA requerem:
- **API Key válida** (same as other endpoints)
- **Escopo `ai:write`** (para POST) ou **`ai:read`** (para GET)

Exemplo:
```bash
curl -X POST http://localhost:8000/api/v1/ai/summarize \
  -H "X-API-Key: seu-api-key" \
  -H "Content-Type: application/json" \
  -d '{"text":"Seu texto aqui"}'
```

## Casos de Uso

### 1. Resumir descrição de cliente/pedido

```python
from omniroute_client import summarize_text

cliente_info = "Empresa XYZ, CNPJ 12.345.678/0001-99, especializada em..."
resumo = summarize_text(cliente_info, max_tokens=100)
```

### 2. Gerar descrição de produto

```python
from omniroute_client import generate_description

descricao = generate_description(
    subject="Aparelho de pressão digital",
    context="Produto médico, preciso, portátil"
)
```

### 3. Analisar tendências de vendas

```python
from omniroute_client import analyze_data

dados = {
    "jan": 5000,
    "fev": 5500,
    "mar": 6200,
    "abr": 5800
}
analise = analyze_data(
    str(dados),
    "Qual é a tendência de vendas nos últimos meses?"
)
```

## Limitações e Considerações

### Quotas Gratuitas
- ~1.47B tokens/mês compartilhados entre provedores
- Renovação automática (re-auditada a cada 2 semanas)
- Usar modelo `auto` para fallback automático

### Performance
- **Primeira requisição:** ~2-5s (dependendo do provedor)
- **Requisições subsequentes:** ~1-2s (cache do gateway)
- Recomendado usar com `max_tokens` baixo (200-500)

### Disponibilidade
- Se OmniRoute está fora, endpoints retornam HTTP 503
- Verificar status em `/api/v1/ai/status`

### Dados Sensíveis
- ⚠️ NÃO enviar informações sensíveis (CNPJ completo, senhas) sem encriptação
- OmniRoute processa em local-first por padrão
- Usar HTTPS em produção

## Troubleshooting

### "OmniRoute service error"

1. **Verificar se OmniRoute está rodando:**
   ```bash
   curl http://localhost:20128/dashboard
   ```

2. **Verificar quotas:**
   ```bash
   curl http://localhost:20128/dashboard/free-tiers
   ```

3. **Ver logs do OmniRoute:**
   ```bash
   omniroute --debug
   ```

### "Connection refused"

- OmniRoute não está rodando → `omniroute`
- Verificar porta: `lsof -i :20128` (Mac/Linux) ou `netstat -ano | findstr :20128` (Windows)

### Quotas esgotadas

- Esperar renovação (2 semanas)
- Adicionar API keys de provedores pagos no OmniRoute
- Usar provedores específicos em vez de `auto`

## Roadmap

- [ ] Cache de respostas de IA
- [ ] Rate limiting por tenant
- [ ] Logging de custos por tenant
- [ ] Suporte a modelos de visão (image analysis)
- [ ] Webhooks para processamento assíncrono

## Documentação

- OmniRoute: https://omniroute.online
- OpenAI Python SDK: https://github.com/openai/openai-python
- FastAPI: https://fastapi.tiangolo.com/
