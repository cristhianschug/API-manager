# ADR-003: Acesso ao Firebird via asyncio.to_thread (sem pool)

## Status
Aceito

## Data
2026-08

## Contexto

O driver Firebird usado (`firebirdsql`) é bloqueante. FastAPI é async. Executar operações bloqueantes diretamente no event loop trava todos os requests simultâneos.

Opções avaliadas:

- **`asyncio.to_thread()`** — executa a chamada bloqueante em uma thread do ThreadPoolExecutor padrão; zero dependência extra
- **`databases` library** — abstração async sobre drivers; não suporta Firebird
- **Pool de conexões customizado** — `fdb` (outro driver) tem pool built-in; `firebirdsql` não; implementar é complexo
- **Processos separados** — overhead muito alto para consultas simples

## Decisão

Usar `asyncio.to_thread()` para todas as operações Firebird. Cada request abre uma conexão, executa, fecha. Conexões não são reutilizadas entre requests.

```python
columns, rows = await asyncio.to_thread(_query)
```

Credenciais são cacheadas em memória por 5 minutos (`_creds_cache` em `platform_repository.py`) para evitar decrypt + DB lookup em cada request.

## Por que sem pool

- Firebird limita conexões simultâneas por licença/configuração do servidor do cliente
- Clientes têm instâncias Firebird de ERP legadas com limites baixos (tipicamente 10-20 conexões)
- Pool permanente esgotaria conexões em instâncias ociosas; abre-fecha é mais seguro
- A latência de conexão Firebird (~5ms local) é aceitável para o volume atual

## Consequências

- Sob carga alta, o ThreadPoolExecutor pode saturar; sintoma: requests enfileiram
- Se throughput exigir pool, a abstração está em `dynamic_router.py._query()` — substituível por `fdb` com pool
- Thread safety: `_creds_cache` e `_table_cache` são dicts Python; operações de leitura/escrita são atômicas no CPython (GIL), mas cache miss duplo pode ocorrer em alta concorrência (aceitável — pior caso são dois fetches idênticos)
- Comentado com `# ponytail:` onde o teto é conhecido
