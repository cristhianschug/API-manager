# MCP — manual de conexão, configuração e instalação

O servidor MCP (Model Context Protocol) da plataforma expõe os dados de **um cliente**, limitado
ao que **uma API key** pode ler, para qualquer IA/agente compatível com MCP (Claude Desktop,
Claude Code, Cursor, Cline, Continue, Windsurf, agentes próprios).

- **Endpoint:** `http(s)://<host>:8002/mcp/sse` — transporte SSE
- **Autenticação:** header `X-API-Key: sk_live_...` (a mesma key da API REST)
- **Fallback** para clientes que não enviam headers: `?api_key=sk_live_...` na URL
  (evite: a chave aparece em logs de proxy)

Não há SQL em nenhum momento: as ferramentas chamam os **endpoints da API** que a key pode ler,
guiadas pelo **mapeamento do banco** feito no painel.

---

## 1. Pré-requisitos (painel admin)

1. Cliente cadastrado e com **Mapeamento = Mapeado** (roda sozinho no cadastro; se necessário, **Sincronizar mapeamento**).
2. Uma **API key** para o uso da IA, com as permissões desejadas:
   - `Todas as tabelas` (`*`) → a IA vê todos os endpoints `/api/v1/data/*` do cliente
   - ou tabelas específicas (`dyn:TABELA`) → só essas
   - recursos ERP (`clientes`, `pedidos`, …) → endpoints `/api/v1/<recurso>` e `/summary`
3. Copie a key no momento da criação (ela não é exibida de novo).

Teste rápido antes de configurar a IA:

```bash
curl -H "X-API-Key: sk_live_XXXX" http://localhost:8002/api/v1/data
```

---

## 2. Ferramentas disponíveis

| Tool | O que faz | Quando a IA usa |
|---|---|---|
| `list_endpoints` | Catálogo de endpoints permitidos para a key, com propósito, colunas, filtros e relacionamentos (do mapeamento) | Primeiro passo de qualquer análise |
| `query_endpoint` | Consulta um endpoint do catálogo (`path`, `params.limit`, `params.offset`). Cache de 2 min | Buscar dados de uma tabela/recurso |
| `ask` | Pergunta em linguagem natural: a plataforma escolhe os endpoints, consulta e devolve narrativa + dados. Aceita `history` | Resposta pronta, com contexto de conversa |
| `get_schema` | Snapshot bruto do catálogo Firebird (tabelas, procedures, triggers) | Exploração técnica |
| `analyze_data` | Análise por IA de dados fornecidos, com o schema como contexto | Dados que o agente já tem em mãos |
| `list_clientes`, `get_cliente`, `list_produtos`, … | Recursos ERP fixos — só aparecem se a key tiver o escopo | Consultas diretas ao ERP |

Recurso: `schema://firebird` — resumo textual do catálogo.

---

## 3. Configuração por cliente MCP

Substitua `HOST` pelo endereço da API (`localhost:8002` em dev; `https://api.seudominio.com.br` em produção) e `SK` pela API key.

### Claude Code (CLI)

```bash
claude mcp add --transport sse anexar http://HOST/mcp/sse --header "X-API-Key: SK"
```

Verifique com `claude mcp list`. Dentro da sessão: `/mcp` mostra as ferramentas.

### Claude Desktop

Claude Desktop conecta a servidores remotos por **stdio**; use a ponte `mcp-remote` (requer Node.js 18+).
Arquivo: Windows `%APPDATA%\Claude\claude_desktop_config.json` · macOS `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "anexar": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "http://HOST/mcp/sse", "--header", "X-API-Key:SK"]
    }
  }
}
```

Reinicie o Claude Desktop. O ícone de ferramentas mostra `anexar`.

> Em planos com **Integrações personalizadas** (Team/Enterprise), é possível adicionar a URL
> `https://HOST/mcp/sse?api_key=SK` diretamente em Configurações → Integrações, sem `mcp-remote`.

### Cursor

`.cursor/mcp.json` no projeto (ou `~/.cursor/mcp.json` global):

```json
{
  "mcpServers": {
    "anexar": {
      "url": "http://HOST/mcp/sse",
      "headers": { "X-API-Key": "SK" }
    }
  }
}
```

### Cline / Roo Code (VS Code)

MCP Servers → Configure → adicionar:

```json
{
  "mcpServers": {
    "anexar": {
      "url": "http://HOST/mcp/sse",
      "headers": { "X-API-Key": "SK" },
      "transportType": "sse"
    }
  }
}
```

### Continue

`~/.continue/config.yaml`:

```yaml
mcpServers:
  - name: anexar
    type: sse
    url: http://HOST/mcp/sse
    requestOptions:
      headers:
        X-API-Key: SK
```

### Windsurf

`~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "anexar": { "serverUrl": "http://HOST/mcp/sse", "headers": { "X-API-Key": "SK" } }
  }
}
```

### Agente próprio (Python, SDK oficial `mcp`)

```python
import asyncio
from mcp import ClientSession
from mcp.client.sse import sse_client

async def main():
    async with sse_client("http://HOST/mcp/sse", headers={"X-API-Key": "SK"}) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = await s.list_tools()
            print([t.name for t in tools.tools])
            res = await s.call_tool("ask", {"question": "Quais os 5 clientes com mais pedidos?"})
            print(res.content[0].text)

asyncio.run(main())
```

---

## 4. Fluxo típico de uma conversa

1. A IA chama `list_endpoints` → recebe o catálogo com propósitos e colunas.
2. Para a pergunta do usuário, chama `ask` (ou `query_endpoint` em endpoints específicos).
3. A plataforma consulta os endpoints permitidos, cacheia por 2 min e devolve narrativa + dados + quais endpoints foram usados.
4. Perguntas seguintes reaproveitam o cache e o `history`.

---

## 5. Problemas comuns

| Sintoma | Causa | Ação |
|---|---|---|
| `401 X-API-Key header obrigatorio` | Cliente MCP não enviou o header | Use a configuração com `headers`; ou `?api_key=` |
| `401 API key invalida ou revogada` | Key revogada/expirada ou digitada errado | Gere/rotacione a key no painel |
| `503 Banco de dados do cliente indisponivel` | API não alcança o Firebird do cliente | Ver host/porta em Clientes → painel; firewall/VPN |
| Ferramentas `list_*` não aparecem | Key sem escopo ERP | Marque `clientes`, `pedidos`… na key |
| `list_endpoints` vazio | Key sem `*` nem `dyn:*` e sem recursos ERP | Edite permissões / crie nova key |
| `ask` responde "não identifiquei quais dados consultar" | Mapeamento incompleto ou pergunta fora do domínio | Sincronizar mapeamento; reformular |
| Conexão cai após alguns segundos atrás de proxy | Buffer/timeout do SSE | nginx: `proxy_buffering off; proxy_read_timeout 3600s;` em `/mcp/` (ver DEPLOY.md) |

---

## 6. Segurança

- A key define **quem o MCP é**: use uma key própria para IA, com o mínimo de tabelas necessário; revogue no painel para cortar o acesso.
- Tabelas dinâmicas são **somente leitura** por construção.
- Toda consulta feita pelo MCP passa pelos mesmos endpoints e pela mesma checagem de escopo da API REST — nada é exposto "por dentro".
- Em produção use **HTTPS**; a key trafega no header.
