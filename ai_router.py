"""
Roteador de IA: pergunta em linguagem natural → endpoint(s) da API → resposta narrativa.

A IA NUNCA gera SQL. Ela recebe o catálogo de endpoints permitidos para a API key
(tabelas expostas + recursos ERP, com colunas tipadas e semântica do schema_context) e devolve
QUAIS endpoints chamar e com QUAIS parâmetros estruturados (count, filters, order_by, group_by/agg).
O backend valida tudo (dynamic_router.build_query), executa em processo com a mesma checagem de
escopo da rota HTTP, cacheia o resultado e pede à IA a narrativa final.
"""
import asyncio
import datetime as _dt
import json
import logging
import re
import time
from typing import Any, Optional

from fastapi import HTTPException

import repository as erp
from dynamic_router import fetch_table, get_table_columns
from omniroute_client import query_ai
from platform_repository import (
    list_exposed_tables, get_schema_context,
    add_ai_memory, list_ai_memory, find_ai_lesson, update_ai_memory,
)

log = logging.getLogger(__name__)

_MAX_CALLS = 3
_CACHE_TTL = 120.0
_CATALOG_LIMIT = 30
_COLS_PER_TABLE = 45
# ponytail: cache em memória por processo; Redis se multi-worker
_cache: dict[str, tuple[float, Any]] = {}

# Recursos ERP fixos: (list_fn, summary_fn, descrição)
_ERP = {
    'clientes':         (erp.list_clientes,        erp.summary_clientes,        'Clientes do ERP (razão social, CNPJ, contato)'),
    'produtos':         (erp.list_produtos,        erp.summary_produtos,        'Produtos e estoque'),
    'pedidos':          (erp.list_pedidos,         erp.summary_pedidos,         'Pedidos de venda'),
    'parcelas':         (erp.list_parcelas,        erp.summary_parcelas,        'Parcelas financeiras (contas a receber)'),
    'fornecedores':     (erp.list_fornecedores,    erp.summary_fornecedores,    'Fornecedores'),
    'atendimentos':     (erp.list_atendimentos,    erp.summary_atendimentos,    'Atendimentos ao cliente'),
    'ordens_servico':   (erp.list_ordens_servico,  erp.summary_ordens_servico,  'Ordens de serviço'),
    'ordens_prestacao': (erp.list_ordens_prestacao, erp.summary_ordens_prestacao, 'Ordens de prestação de serviço'),
}
_ERP_PATH = {'ordens_servico': 'ordens-servico', 'ordens_prestacao': 'ordens-prestacao'}
_QUERY_KEYS = ('fields', 'filters', 'order_by', 'order', 'count', 'group_by', 'agg')


def _can_read(scopes: dict, resource: str) -> bool:
    return bool(scopes.get(resource, {}).get('read'))


def _can_read_table(scopes: dict, table_name: str) -> bool:
    return _can_read(scopes, f"dyn:{table_name.upper()}") or _can_read(scopes, '*')


# ── Catálogo ────────────────────────────────────────────────────────────────

def build_catalog(client_id: int, scopes: dict) -> list[dict]:
    """Endpoints que ESTA api key pode chamar, com colunas tipadas e semântica do mapeamento."""
    ctx = get_schema_context(client_id) or {}
    typed = get_table_columns(client_id)
    catalog = []
    for t in list_exposed_tables(client_id):
        if not t['enabled'] or not _can_read_table(scopes, t['table_name']):
            continue
        sem = ctx.get(t['table_name'], {}) or {}
        cols = typed.get(t['table_name'].upper(), {})
        if t.get('columns'):  # whitelist de colunas da tabela exposta
            cols = {c: cols.get(c.upper(), '') for c in t['columns']}
        meaning = sem.get('columns') or {}
        # prioriza: PK, colunas com significado mapeado, datas e numéricos (úteis para filtro/agregação)
        def prio(c):
            ty = cols[c].upper()
            return (c != (t.get('pk_column') or ''), c not in meaning,
                    not any(k in ty for k in ('DATE', 'TIME', 'INT', 'NUMERIC', 'DECIMAL', 'DOUBLE', 'FLOAT', 'INT64', 'LONG', 'SHORT')))
        ordered = sorted(cols, key=prio)[:_COLS_PER_TABLE]
        catalog.append({
            'path': f"/api/v1/data/{t['slug']}",
            'table': t['table_name'],
            'purpose': sem.get('purpose', ''),
            'pk': t.get('pk_column'),
            'columns': {c: cols[c] for c in ordered},
            'column_meaning': meaning,
            'enum_values': sem.get('filters', {}),
            'joins': sem.get('joins', {}),
        })
    for res, (_l, _s, desc) in _ERP.items():
        if _can_read(scopes, res):
            p = _ERP_PATH.get(res, res)
            catalog.append({'path': f"/api/v1/{p}", 'purpose': desc + ' — lista curada (só limit/offset)'})
            catalog.append({'path': f"/api/v1/{p}/summary", 'purpose': f"Totais prontos de {desc.lower()}"})
    return catalog


# ── Execução em processo ────────────────────────────────────────────────────

async def fetch_endpoint(conn, client_id: int, scopes: dict, path: str, params: dict) -> Any:
    """Executa um path do catálogo com a mesma checagem de escopo das rotas HTTP."""
    params = dict(params or {})
    limit = int(params.get('limit', 50) or 50)
    offset = int(params.get('offset', 0) or 0)

    m = re.match(r'^/api/v1/data/([a-z0-9_-]+)$', path)
    if m:
        if 'filter' in params and 'filters' not in params:
            params['filters'] = params.pop('filter')
        q = {k: params[k] for k in _QUERY_KEYS if params.get(k) not in (None, '', [])}
        if isinstance(q.get('count'), str):
            q['count'] = q['count'].lower() == 'true'
        return await fetch_table(conn, client_id, scopes, m.group(1), limit, offset, **q)

    m = re.match(r'^/api/v1/([a-z_-]+)(/summary)?$', path)
    if m:
        res = m.group(1).replace('-', '_')
        if res not in _ERP:
            raise ValueError(f"Endpoint desconhecido: {path}")
        if not _can_read(scopes, res):
            raise PermissionError(f"API key sem permissão de leitura em {res}")
        list_fn, summary_fn, _ = _ERP[res]
        if m.group(2):
            return await asyncio.to_thread(summary_fn, conn)
        return await asyncio.to_thread(list_fn, conn, min(500, max(1, limit)), max(0, offset))

    raise ValueError(f"Endpoint fora do catálogo: {path}")


async def cached_fetch(conn, api_key_id: int, client_id: int, scopes: dict, path: str, params: dict) -> Any:
    key = f"{api_key_id}|{path}|{json.dumps(params or {}, sort_keys=True, default=str)}"
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1]
    data = await fetch_endpoint(conn, client_id, scopes, path, params)
    _cache[key] = (time.time(), data)
    if len(_cache) > 500:
        for k in sorted(_cache, key=lambda k: _cache[k][0])[:100]:
            _cache.pop(k, None)
    return data


# ── Seleção de candidatos ───────────────────────────────────────────────────

_STOP = {'de', 'da', 'do', 'das', 'dos', 'e', 'o', 'a', 'os', 'as', 'um', 'uma', 'que', 'em', 'no', 'na', 'nos', 'nas',
         'por', 'para', 'com', 'quais', 'qual', 'quantos', 'quantas', 'quanto', 'temos', 'tem', 'mais', 'menos', 'me',
         'mostre', 'liste', 'lista', 'total', 'todos', 'todas', 'ultimos', 'últimos', 'recentes', 'recentemente',
         'cadastrados', 'cadastradas', 'foram', 'feitos', 'feitas', 'este', 'esta', 'esse', 'essa', 'ano', 'mes', 'mês',
         'hoje', 'ontem', 'semana', 'valor', 'vendido', 'vendidos', 'são', 'sao', 'foi', 'como', 'onde', 'quando'}
# vocabulário de negócio → fragmentos comuns em nomes de tabela de ERP
_SYNONYMS = {'venda': ['pedido', 'venda', 'nf', 'nota'], 'vendas': ['pedido', 'venda', 'nf', 'nota'],
             'vendido': ['pedido', 'venda'], 'faturamento': ['nf', 'nota', 'fatur', 'pedido'],
             'financeiro': ['parcela', 'receber', 'pagar', 'titulo'], 'receber': ['parcela', 'receber', 'titulo'],
             'pagar': ['pagar', 'parcela', 'titulo'], 'estoque': ['estoque', 'produto', 'saldo'],
             'funcionario': ['funcion', 'colab', 'usuario'], 'vendedor': ['vendedor', 'represent', 'funcion']}


def _stem(t: str) -> str:
    for suf in ('ões', 'oes', 'es', 's'):
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            return t[:-len(suf)]
    return t


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r'[a-zà-ú0-9]{3,}', (text or '').lower()) if t not in _STOP}


# ── Memória: o que já foi validado guia as próximas perguntas ──────────────

_MAX_INSTRUCTIONS = 12
_MAX_LESSONS = 4


def question_key(question: str) -> str:
    """Chave estável da pergunta (termos normalizados) — usada para recuperar e deduplicar."""
    return " ".join(sorted({_stem(t) for t in _tokens(question)}))


def _overlap(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def recall(client_id: int, question: str, history: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Conhecimento VALIDADO deste cliente: todas as instruções (são poucas e valem sempre)
    e as lições mais parecidas com a pergunta atual.
    """
    try:
        memory = list_ai_memory(client_id, status='validated')
    except Exception as e:
        log.warning("recall falhou (client %s): %s", client_id, e)
        return [], []
    instructions = [m for m in memory if m['kind'] == 'instruction'][:_MAX_INSTRUCTIONS]
    key = question_key(question + " " + " ".join(m.get('content', '') for m in history[-2:] if m.get('role') == 'user'))
    lessons = sorted((m for m in memory if m['kind'] == 'lesson' and m.get('plan')),
                     key=lambda m: _overlap(key, m.get('terms') or ''), reverse=True)
    lessons = [m for m in lessons if _overlap(key, m.get('terms') or '') > 0][:_MAX_LESSONS]
    return instructions, lessons


def _memory_block(instructions: list[dict], lessons: list[dict]) -> str:
    out = ""
    if instructions:
        out += ("\nRegras deste cliente (validadas por um humano — siga à risca):\n"
                + "\n".join(f"- {m['content']}" for m in instructions) + "\n")
    if lessons:
        out += ("\nExemplos validados para este cliente (mesma pergunta → mesmas chamadas):\n"
                + "\n".join(f'- "{m["question"]}" → {json.dumps(m["plan"], ensure_ascii=False)}' for m in lessons) + "\n")
    return out


def _memory_tables(instructions: list[dict], lessons: list[dict]) -> set[str]:
    """Tabelas citadas no conhecimento validado — entram no catálogo mesmo se a busca por termos não as achar."""
    blob = " ".join([m.get('content') or '' for m in instructions]
                    + [json.dumps(m.get('plan') or [], ensure_ascii=False) for m in lessons]).lower()
    return {m for m in re.findall(r'/api/v1/data/([a-z0-9_-]+)', blob)} | {
        t.lower() for t in re.findall(r'\b([A-Z][A-Z0-9_$]{3,})\b', " ".join(m.get('content') or '' for m in instructions))}


def select_catalog(question: str, history: list[dict], catalog: list[dict], limit: int = _CATALOG_LIMIT,
                   pinned: set[str] | None = None) -> list[dict]:
    """
    ERPs têm centenas de tabelas; mandar tudo estoura o prompt e piora a escolha. Pontua cada tabela:
    termo no NOME da tabela vale muito mais que no propósito, que vale mais que em colunas.
    Tabelas curtas/principais (TBCLIENTE) vencem derivadas (TBCLIENTEALTERACOES) no empate.
    Recursos ERP fixos entram sempre.
    """
    if len(catalog) <= limit:
        return catalog
    raw = _tokens(question) | _tokens(" ".join(m.get('content', '') for m in history[-4:] if m.get('role') == 'user'))
    terms = {_stem(t) for t in raw}
    for t in list(raw):
        terms.update(_SYNONYMS.get(t, []))
    # tabelas citadas no conhecimento validado nunca ficam de fora do catálogo
    pinned = {p.lower() for p in (pinned or set())}
    fixed = [c for c in catalog if pinned and (c.get('table', '').lower() in pinned
                                               or c['path'].rsplit('/', 1)[-1].lower() in pinned)]

    def score(c: dict) -> float:
        name = (c.get('table') or '').lower()
        purpose = (c.get('purpose') or '').lower()
        cols = " ".join(list(c.get('columns', {}))[:40]).lower() + " " + " ".join((c.get('column_meaning') or {}).values()).lower()
        s = 0.0
        for t in terms:
            if t in name:
                s += 10 + (6 if name in (t, 'tb' + t, 'tb' + t + 's') else 0)
            if t in purpose:
                s += 3
            if t in cols:
                s += 1
        if s and c.get('purpose'):
            s += 1
        return s - len(name) / 100  # desempate: nome mais curto = tabela principal

    erp_entries = [c for c in catalog if not c['path'].startswith('/api/v1/data/')]
    head = erp_entries + fixed
    seen = {c['path'] for c in head}
    dyn = sorted((c for c in catalog if c['path'].startswith('/api/v1/data/') and c['path'] not in seen),
                 key=score, reverse=True)
    return head + dyn[:max(0, limit - len(head))]


# ── Planejamento ────────────────────────────────────────────────────────────

_PLANNER_RULES = """Você roteia perguntas de negócio para endpoints REST de um ERP. NÃO escreva SQL.
Escolha até 3 chamadas do catálogo. Endpoints /api/v1/data/* aceitam estes params:
- "count": true → total REAL de registros (use para "quantos"). Nunca conte linhas de uma lista: listas são limitadas a 500.
- "filters": ["COLUNA:op:valor", ...] — op: eq ne gt gte lt lte like isnull notnull. Datas: AAAA-MM-DD. Use SOMENTE colunas listadas em "columns".
- "order_by": "COLUNA", "order": "asc|desc" — use para "mais recentes", "maiores", "top N" (com "limit": N).
- "group_by": "COLUNA" | "year:COLUNA_DATA" | "month:COLUNA_DATA" + "agg": "count" | "sum:COL" | "avg:COL" | "min:COL" | "max:COL" — rankings e evolução no tempo. Só "agg" (sem group_by) devolve um único total.
- "fields": ["A","B"] — reduza colunas em listas. "limit" ≤ 200.
Escolha a tabela PRINCIPAL do assunto (ex.: TBCLIENTE, não TBCLIENTEALTERACOES). Use "enum_values" para valores de filtro.
Endpoints /api/v1/<recurso>/summary já trazem totais prontos; /api/v1/<recurso> só aceita limit/offset.
Se a pergunta não precisa de dados (saudação, dúvida sobre a conversa), responda em "answer" e deixe "calls" vazio.
Responda SOMENTE JSON: {"calls": [{"path": "...", "params": {...}}], "answer": null}
Exemplos:
"quantos clientes ativos?" → {"calls":[{"path":"/api/v1/data/tbcliente","params":{"count":true,"filters":["STATUS:eq:1"]}}],"answer":null}
"5 clientes mais recentes" → {"calls":[{"path":"/api/v1/data/tbcliente","params":{"order_by":"DATACAD","order":"desc","limit":5,"fields":["RAZAOSOCIAL","DATACAD"]}}],"answer":null}
"vendas por mês este ano" → {"calls":[{"path":"/api/v1/data/tbpedido","params":{"group_by":"month:DATAPEDIDO","agg":"sum:VALORTOTAL","filters":["DATAPEDIDO:gte:2026-01-01"]}}],"answer":null}"""


def _parse_plan(raw: str, catalog: list[dict]) -> dict:
    m = re.search(r'\{.*\}', raw or '', re.DOTALL)
    if not m:
        return {"calls": [], "answer": (raw or '').strip()}
    try:
        plan = json.loads(m.group())
    except json.JSONDecodeError:
        return {"calls": [], "answer": None}
    allowed = {c['path'] for c in catalog}
    calls = [{"path": c['path'], "params": c.get('params') if isinstance(c.get('params'), dict) else {}}
             for c in (plan.get('calls') or []) if isinstance(c, dict) and c.get('path') in allowed][:_MAX_CALLS]
    return {"calls": calls, "answer": plan.get('answer')}


def _plan_calls(question: str, history: list[dict], catalog: list[dict], feedback: str = "",
                instructions: list[dict] | None = None, lessons: list[dict] | None = None) -> dict:
    instructions, lessons = instructions or [], lessons or []
    catalog = select_catalog(question, history, catalog, pinned=_memory_tables(instructions, lessons))
    hist = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-6:])
    prompt = (
        _PLANNER_RULES + f"\n\nData de hoje: {_dt.date.today().isoformat()}\n"
        + _memory_block(instructions, lessons)
        + f"\nCatálogo:\n{json.dumps(catalog, ensure_ascii=False)}\n\n"
        + (f"Histórico:\n{hist}\n\n" if hist else "")
        + f"Pergunta: {question}"
        + (f"\n\nSua tentativa anterior falhou. Corrija usando apenas colunas do catálogo:\n{feedback}" if feedback else "")
    )
    return _parse_plan(query_ai(prompt, max_tokens=700, temperature=0.1), catalog)


# ── Narrativa ───────────────────────────────────────────────────────────────

def _summarize_result(r: dict) -> dict:
    d = r['data']
    base = {'endpoint': r['path'], 'params': r['params']}
    if isinstance(d, dict) and d.get('mode') == 'count':
        return {**base, 'tipo': 'contagem exata', 'count': d['count']}
    if isinstance(d, dict) and d.get('mode') == 'group':
        return {**base, 'tipo': 'agregação exata (VALOR = resultado do agg)', 'linhas': d.get('data', [])[:60]}
    rows = d.get('data') if isinstance(d, dict) and 'data' in d else d
    if isinstance(rows, list):
        return {**base, 'tipo': 'lista' + (' PARCIAL (há mais registros além do limite — não use para totais)' if isinstance(d, dict) and d.get('truncated') else ''),
                'linhas_retornadas': len(rows), 'linhas': rows[:25]}
    return {**base, 'tipo': 'resumo', 'dados': d}


def _narrate(question: str, history: list[dict], results: list[dict], errors: list[str],
             instructions: list[dict] | None = None) -> str:
    hist = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history[-6:])
    payload = json.dumps([_summarize_result(r) for r in results], ensure_ascii=False, default=str)[:50000]
    rules = "\n".join(f"- {m['content']}" for m in (instructions or []))
    prompt = (
        "Você é um analista de negócios. Responda em português do Brasil, direto ao ponto: comece pela resposta "
        "objetiva à pergunta (o número, o nome, a lista), depois 1–3 frases de contexto/insight.\n"
        "REGRAS: use SOMENTE os dados abaixo. Não invente números, nomes ou datas. 'contagem exata' e 'agregação exata' "
        "são totais reais do banco. Uma 'lista PARCIAL' é amostra: nunca derive totais dela. Se os dados não respondem "
        "à pergunta, diga o que faltou em vez de supor. Formate valores monetários como R$ 1.234,56 e datas como DD/MM/AAAA.\n"
        "Termine com 2 sugestões curtas de próximas perguntas. Se um gráfico fizer sentido para os dados, adicione na última "
        "linha exatamente: CHART:bar, CHART:pie ou CHART:line.\n"
        + (f"\nRegras deste cliente (validadas — têm prioridade sobre as acima):\n{rules}\n" if rules else "")
        + "\n" + (f"Histórico:\n{hist}\n\n" if hist else "")
        + f"Pergunta: {question}\nDados: {payload}"
        + (f"\nConsultas que falharam: {'; '.join(errors)}" if errors else "")
    )
    return query_ai(prompt, max_tokens=900, temperature=0.3)


# ── Orquestração ────────────────────────────────────────────────────────────

def _empty(answer: str, endpoints=None, warnings=None) -> dict:
    return {"answer": answer, "data": [], "columns": [], "total": 0, "chart_type": None,
            "endpoints": endpoints or [], "warnings": warnings or []}


async def _run_calls(conn, api_key_id, client_id, scopes, calls) -> tuple[list[dict], list[str]]:
    results, errors = [], []
    for c in calls:
        try:
            data = await cached_fetch(conn, api_key_id, client_id, scopes, c['path'], c['params'])
            results.append({'path': c['path'], 'params': c['params'], 'data': data})
        except PermissionError as e:
            errors.append(f"{c['path']}: sem permissão")
            log.info("ai_router permission: %s", e)
        except HTTPException as e:  # 400 do build_query: mensagem útil para o reparo
            errors.append(f"{c['path']} {json.dumps(c['params'], ensure_ascii=False)}: {e.detail}")
        except Exception as e:
            errors.append(f"{c['path']}: indisponível")
            log.warning("ai_router fetch %s falhou: %s", c['path'], e)
    return results, errors


async def ask(conn, api_key_id: int, client_id: int, scopes: dict,
              question: str, history: Optional[list[dict]] = None) -> dict:
    history = history or []
    catalog = await asyncio.to_thread(build_catalog, client_id, scopes)
    if not catalog:
        return _empty("Esta API key não tem permissão de leitura em nenhum endpoint. Peça ao administrador para liberar tabelas ou recursos.")

    instructions, lessons = await asyncio.to_thread(recall, client_id, question, history)
    repaired = False
    try:
        plan = await asyncio.to_thread(_plan_calls, question, history, catalog, "", instructions, lessons)
        if not plan['calls']:
            return _empty(plan.get('answer') or "Não identifiquei quais dados consultar. Pode reformular citando o assunto (clientes, pedidos, produtos…)?")
        results, errors = await _run_calls(conn, api_key_id, client_id, scopes, plan['calls'])
        # laço de reparo: consultas rejeitadas voltam UMA vez ao planejador com o motivo
        rejected = [e for e in errors if 'sem permissão' not in e and 'indisponível' not in e]
        if rejected:
            fixed = await asyncio.to_thread(_plan_calls, question, history, catalog, "\n".join(rejected), instructions, lessons)
            done = {(r['path'], json.dumps(r['params'], sort_keys=True)) for r in results}
            retry = [c for c in fixed['calls'] if (c['path'], json.dumps(c['params'], sort_keys=True)) not in done]
            if retry:
                r2, e2 = await _run_calls(conn, api_key_id, client_id, scopes, retry)
                results += r2
                errors = [e for e in errors if e not in rejected] + e2
                repaired = bool(r2)
    except RuntimeError as e:  # provedor de IA fora — resposta amigável, não 503 genérico
        log.warning("planner falhou: %s", e)
        return _empty("O provedor de IA não respondeu agora. Tente novamente em instantes ou verifique Configurações → Provedor de IA.",
                      warnings=["provedor de IA indisponível"])

    if not results:
        return _empty("Não consegui obter dados para essa pergunta. " + "; ".join(errors)[:400],
                      endpoints=[c['path'] for c in plan['calls']], warnings=errors)

    try:
        narrative = await asyncio.to_thread(_narrate, question, history, results, errors, instructions)
    except RuntimeError as e:  # dados já obtidos: entrega a tabela mesmo sem narrativa
        log.warning("narrativa falhou: %s", e)
        narrative = "Obtive os dados abaixo, mas o provedor de IA não conseguiu gerar a análise agora."
        errors.append("narrativa indisponível")
    chart_type = None
    m = re.search(r'CHART:(bar|pie|line)', narrative)
    if m:
        chart_type = m.group(1)
        narrative = narrative[:narrative.rfind('CHART:')].strip()

    # dados do resultado mais "tabular" alimentam tabela/gráfico do frontend
    def _rows(d):
        if isinstance(d, dict) and d.get('mode') == 'count':
            return [{'count': d['count']}]
        rows = d.get('data') if isinstance(d, dict) and 'data' in d else (d if isinstance(d, list) else [d])
        return [r if isinstance(r, dict) else {'value': r} for r in rows]
    best = max(results, key=lambda r: len(_rows(r['data'])))
    rows = _rows(best['data'])
    columns = list(rows[0].keys()) if rows else []

    plan_used = [{"path": r['path'], "params": r['params']} for r in results]
    memory = await asyncio.to_thread(_capture, client_id, question, plan_used, lessons, repaired)
    return {
        "answer": narrative,
        "data": rows[:100],
        "columns": columns,
        "total": len(rows),
        "chart_type": chart_type if len(rows) > 1 else None,
        "endpoints": [r['path'] for r in results],
        "queries": plan_used,
        "warnings": [e[:200] for e in errors],
        "memory": memory,          # {id, status} — o painel valida com um clique
        "used_memory": {"instructions": len(instructions), "lessons": len(lessons)},
    }


def _capture(client_id: int, question: str, plan: list[dict], used_lessons: list[dict], repaired: bool) -> dict:
    """
    Retroalimentação: registra a pergunta e o plano que funcionou como candidato a lição.
    Nada entra no prompt antes de um humano validar. Se já existe lição validada para a mesma
    pergunta, só contabiliza o uso (e atualiza o plano quando o reparo achou um caminho melhor).
    """
    try:
        key = question_key(question)
        if not key:
            return {}
        existing = find_ai_lesson(client_id, key)
        if existing:
            update_ai_memory(existing['id'], bump_use=True,
                             plan=plan if (repaired and existing['status'] != 'validated') else None)
            return {"id": existing['id'], "status": existing['status']}
        for m in used_lessons:  # a lição recuperada guiou esta resposta
            update_ai_memory(m['id'], bump_use=True)
        row = add_ai_memory(client_id, 'lesson', question=question.strip()[:400], terms=key, plan=plan,
                            source='repair' if repaired else 'auto')
        return {"id": row.get('id'), "status": row.get('status')}
    except Exception as e:
        log.warning("captura de lição falhou (client %s): %s", client_id, e)
        return {}
