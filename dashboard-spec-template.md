# Especificação de Dashboard — Plataforma Anexar
> **Como usar este documento:** As seções marcadas com 🔒 são padrões obrigatórios da plataforma — leia, siga, não altere. As seções marcadas com ✏️ devem ser preenchidas pelo solicitante antes de enviar a IA criar o dashboard.

---

## 🔒 1. Contexto da Plataforma

A Plataforma Anexar é uma API multi-tenant conectada a bancos Firebird de clientes. Cada cliente tem seu próprio banco com estrutura potencialmente diferente. O sistema de **conectores** resolve isso: o dashboard nunca sabe de onde vêm os dados — ele declara o que precisa (query_ids) e a plataforma decide qual rota responde isso para cada cliente autenticado.

**Endpoint único do dashboard:**
```
POST {API_BASE}/api/v1/connectors/{CONNECTOR_ID}/execute
Headers:
  X-API-Key: {API_KEY}
```
Retorna: `{ "summary": {...}, "list": [...], "trend": [...] }` — apenas os query_ids com bindings ativos.

**O dashboard NUNCA chama rotas da API diretamente.** Sempre via `/connectors/{id}/execute`.

---

## 🔒 2. Stack Técnico

### Linguagem e formato de entrega
- **HTML5 + CSS3 + JavaScript ES2022 (vanilla)** — padrão obrigatório, a menos que a seção ✏️ D especifique outro framework.
- Entrega em arquivo único `index.html` ou estrutura `index.html + app.js + styles.css`.
- Sem build step obrigatório — deve rodar com `open index.html` ou qualquer servidor estático.

### Bibliotecas permitidas (apenas via CDN cdnjs.cloudflare.com ou cdn.jsdelivr.net)

| Biblioteca       | Versão   | CDN slug                                       | Uso permitido              |
|------------------|----------|------------------------------------------------|----------------------------|
| Chart.js         | 4.4.4    | `chart.js/4.4.4/chart.umd.min.js`             | Gráficos                   |
| Alpine.js        | 3.14.1   | `alpinejs/3.14.1/dist/cdn.min.js`             | Reatividade simples (opt.) |
| Day.js           | 1.11.13  | `dayjs/1.11.13/dayjs.min.js`                  | Formatação de datas        |

**Proibido:** jQuery, lodash, moment.js, axios, qualquer biblioteca que faça chamadas para servidores externos, qualquer CDN fora dos permitidos acima.

### Estilo
- CSS custom properties (tokens) para todas as cores — nunca literal inline.
- Dark mode via `@media (prefers-color-scheme: dark)` + `[data-theme="dark"]`.
- Mobile-first: funciona a partir de 320px de largura.
- Fonte: Google Fonts permitido via `<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=...">`.

---

## 🔒 3. Segurança

### API Key
- **Nunca hardcode** a API key no código-fonte ou em comentários.
- Leitura de config em ordem de prioridade:
  1. `window.ANEXAR_CONFIG.apiKey` (injetado pelo servidor em produção)
  2. `localStorage.getItem('anexar_api_key')`
  3. Input do usuário na primeira abertura, salvo em localStorage com `try/catch`
- A key nunca deve aparecer em URL, título de aba, ou elemento visível da UI.
- Exibir apenas os últimos 4 caracteres quando precisar mostrar a key ao usuário.

### Configuração mínima obrigatória
```javascript
const CONFIG = {
  apiBase:     (window.ANEXAR_CONFIG?.apiBase)     ?? 'http://localhost:8000',
  connectorId: (window.ANEXAR_CONFIG?.connectorId) ?? 0,
  apiKey:      (window.ANEXAR_CONFIG?.apiKey)      ?? (() => {
    try { return localStorage.getItem('anexar_api_key') || ''; } catch { return ''; }
  })(),
};
```

### CORS
- Em desenvolvimento: o servidor FastAPI já permite `localhost`.
- Em produção: o domínio do dashboard deve estar na lista de origens permitidas da API.

### Dados em localStorage
Permitido armazenar: API key, preferências de UI (tema, filtros ativos).  
Proibido armazenar: dados de clientes, registros do banco, tokens além da API key.

---

## 🔒 4. Integração com o Conector

### Função de fetch padrão
O dashboard deve implementar esta função base e usá-la para toda comunicação com a plataforma:

```javascript
async function executeConnector(extraParams = {}) {
  if (!CONFIG.apiKey) throw new Error('API key não configurada.');
  const res = await fetch(
    `${CONFIG.apiBase}/api/v1/connectors/${CONFIG.connectorId}/execute`,
    {
      method: 'POST',
      headers: {
        'X-API-Key': CONFIG.apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(extraParams),
    }
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}
```

### Resposta parcial
A resposta pode conter apenas alguns query_ids. O dashboard deve:
- Verificar se o campo existe antes de renderizar: `if (data.summary) renderSummary(data.summary);`
- Nunca assumir que todos os query_ids estarão presentes
- Tratar `{"error": N, "detail": "..."}` em qualquer query_id como erro daquele componente específico (não da tela toda)

### Refresh automático
- Intervalo mínimo: 60 segundos (não sobrecarregar a API).
- Parar o intervalo quando a aba estiver em background (`document.addEventListener('visibilitychange', ...)`).
- Usar `clearInterval` ao desmontar/recarregar.

---

## 🔒 5. Estados Obrigatórios da UI

Todo bloco que exibe dados deve implementar os 4 estados abaixo. Sem exceção.

| Estado    | Quando ocorre                              | O que mostrar                                          |
|-----------|--------------------------------------------|--------------------------------------------------------|
| `loading` | Aguardando resposta da API                 | Skeleton ou spinner; não bloquear a tela inteira       |
| `data`    | Dados recebidos com sucesso               | Renderização normal                                    |
| `empty`   | Array vazio ou todos os valores zero       | Ícone + mensagem explicativa + sugestão de ação        |
| `error`   | Erro de rede, HTTP não-2xx, binding falhou | Mensagem amigável + botão "Tentar novamente"; sem stack trace exposto |

**KPI cards com valor zero não são estado de erro** — são dados válidos. Mostre o zero.

---

## 🔒 6. Infraestrutura e Deploy

### Desenvolvimento local
```bash
# Qualquer um destes serve:
python -m http.server 3000
npx serve .
# Ou abrir index.html direto no browser
```

### Estrutura de arquivos recomendada
```
dashboard-{nome}/
├── index.html          # entrada principal
├── app.js              # lógica (opcional — pode estar inline no HTML)
├── styles.css          # estilos customizados
├── config.example.js   # template de config SEM keys reais
├── .gitignore          # incluir: config.js, *.env
└── README.md           # instruções de setup e variáveis necessárias
```

### Variáveis de ambiente para produção
```
ANEXAR_API_BASE=https://api.seudominio.com
ANEXAR_CONNECTOR_ID=1
ANEXAR_API_KEY=ak_...   # injetada pelo servidor, nunca no código
```

---

## 🔒 7. Testes Obrigatórios Antes de Entregar

A IA deve rodar ou documentar como rodar cada item abaixo:

- [ ] Execute retorna `200` com API key válida
- [ ] Execute retorna erro tratado (não trava a tela) com API key inválida ou expirada
- [ ] Estado `loading` visível na carga inicial
- [ ] Estado `empty` exibido quando API retorna array vazio
- [ ] Estado `error` exibido quando execute retorna `{"error": 500}`
- [ ] Nenhum `console.error` na carga inicial com dados válidos
- [ ] API key não aparece em nenhum elemento da UI, URL ou título
- [ ] Layout funciona em 320px de largura (mobile)
- [ ] Layout funciona em 1280px de largura (desktop)
- [ ] Refresh automático não gera requests quando aba está em background
- [ ] Dados numéricos com separadores regionais corretos (`pt-BR`)

---

## 🔒 8. Formatação de Dados

Use sempre o locale `pt-BR`:

```javascript
// Números inteiros
n.toLocaleString('pt-BR')                       // 1.234.567

// Moeda
n.toLocaleString('pt-BR', { style:'currency', currency:'BRL' })  // R$ 1.234,56

// Data
new Date(iso).toLocaleDateString('pt-BR')       // 17/09/2026

// Data e hora
new Date(iso).toLocaleString('pt-BR')           // 17/09/2026, 10:30:00

// Percentual
(n / 100).toLocaleString('pt-BR', { style:'percent', minimumFractionDigits:1 })
```

---

## ✏️ Seção A — Identidade do Dashboard

> Preencha antes de enviar para a IA.

**Nome do conector na Plataforma Anexar:**
```
[ex: painel-atendimentos]
```

**Nome exibido no dashboard:**
```
[ex: Painel de Atendimentos]
```

**Propósito — o que este dashboard faz e para quem:**
```
[ex: Permite ao gestor de suporte acompanhar o volume, status e tempo de resposta
dos atendimentos abertos, identificando gargalos e prioridades.]
```

**Usuário principal:**
```
[ex: Gerente de atendimento ao cliente]
```

**Frequência de uso esperada:**
```
[ ] Tempo real (atualizar a cada 60s)
[ ] Operacional (atualizar a cada 5 min)
[ ] Analítico (carregar uma vez, refresh manual)
```

---

## ✏️ Seção B — Dados e Consultas

> Liste o que o dashboard precisa exibir. A IA vai mapear para os query_ids corretos.

### KPI Cards
> Liste cada card que deve aparecer no topo do dashboard.

| Card | Dado esperado | Campo do `summary` | Destaque visual |
|------|---------------|--------------------|-----------------|
| [ex: Total de atendimentos] | [Número inteiro] | [`total`] | [Neutro] |
| [ex: Em aberto] | [Número inteiro] | [`abertos`] | [Amarelo se > 10] |
| [ex: Fechados hoje] | [Número inteiro] | [`fechados`] | [Verde] |
| | | | |

### Tabela principal (`list`)
**Colunas visíveis:**
```
[ex: ID, Data de abertura, Título, Status, Responsável]
```

**Ordenação padrão:**
```
[ex: Data de abertura decrescente]
```

**Filtros que o usuário pode aplicar:**
```
[ex: Status (dropdown), Período (date range)]
```

### Gráfico temporal (`trend`) — se necessário
```
[ ] Não preciso de gráfico
[ ] Linha — evolução de: [campo] ao longo de: [período]
[ ] Barra — comparativo de: [campo] por: [agrupamento]
[ ] Pizza — distribuição de: [campo]
```

### Feed de atividade recente (`recentes`) — se necessário
```
[ ] Não preciso
[ ] Sim — mostrar os últimos [N] registros com: [campos]
```

---

## ✏️ Seção C — Estética

> Descreva o visual desejado. Seja específico — a IA vai usar exatamente isto.

**Tema padrão:**
```
[ ] Claro
[ ] Escuro
[ ] Seguir o sistema operacional do usuário
```

**Paleta de cores:**
```
[ex: Fundo: azul marinho escuro #0d1b2a
     Superfície dos cards: #1b2a3b
     Acento principal: laranja #f4722b
     Texto principal: branco #e8e8e8
     OK/positivo: verde #3fb950
     Alerta: amarelo #d29922
     Erro/crítico: vermelho #f85149]
```

**Tipografia:**
```
[ex: Títulos e KPIs: Inter Bold
     Corpo e tabelas: Inter Regular
     Dados numéricos: JetBrains Mono (alinhamento tabular)]
```

**Densidade de informação:**
```
[ ] Compacto — máximo de dados visíveis sem scroll
[ ] Balanceado — confortável para leitura rápida
[ ] Espaçado — foco em poucos dados com destaque visual
```

**Referência visual:**
```
[Cole um link, descreva um produto que admira, ou escreva livremente:
 ex: "parecido com o Vercel dashboard — fundo escuro, tipografia limpa,
 KPIs grandes no topo, tabela abaixo, sem excessos decorativos"]
```

**Presença de gráficos:**
```
[ ] Nenhum
[ ] Discretos — pequenos, complementares
[ ] Destaque — gráficos são parte central da leitura
```

---

## ✏️ Seção D — Comportamentos Especiais

> Use esta seção para qualquer coisa que não coube nas seções acima.

```
[ex: Ao clicar em uma linha da tabela, abrir um painel lateral com o detalhe
do atendimento (query_id: detail, rota: /api/v1/atendimentos/{id}).

Botão de exportar a tabela como CSV (apenas os dados já carregados, sem
chamada adicional à API).

Cards de KPI com indicador de tendência: seta para cima/baixo comparando
com o mesmo período anterior — se o dado vier no summary, usar; caso contrário omitir.]
```

**Framework alternativo (se não for vanilla JS):**
```
[ ] Vanilla JS (padrão — não preencher)
[ ] React 18
[ ] Vue 3
[ ] Outro: _______________
```

---

## 🔒 9. Checklist Final para a IA

Antes de entregar o código, a IA deve confirmar:

- [ ] `CONFIG` lê API key e connectorId de variáveis de ambiente / localStorage (nunca hardcoded)
- [ ] Toda chamada à API usa a função `executeConnector()` da Seção 4
- [ ] Todos os componentes de dados têm os 4 estados (loading / data / empty / error)
- [ ] Nenhuma biblioteca fora da lista da Seção 2 foi usada
- [ ] Formatação de números e datas usa `pt-BR`
- [ ] Mobile funciona em 320px
- [ ] Sem `console.error` em fluxo normal
- [ ] `.gitignore` cobre arquivos com keys reais
- [ ] `README.md` explica como configurar e rodar
