"""
Dynamic REST endpoints auto-generated from exposed_tables config.

  GET /api/v1/data                 — tabelas que esta API key pode ler
  GET /api/v1/data/{slug}          — consulta: lista, contagem ou agregação
  GET /api/v1/data/{slug}/{pk_id}  — registro por PK

Parâmetros de consulta (todos opcionais, combináveis):
  limit, offset        paginação (limit ≤ 500)
  fields=A,B           só estas colunas
  filter=COL:op:valor  repetível (máx. 8). op: eq ne gt gte lt lte like isnull notnull
  order_by=COL&order=asc|desc
  count=true           → {"count": N} respeitando os filtros (total real, sem limite de 500)
  group_by=COL | year:COL | month:COL   + agg=count | sum:COL | avg:COL | min:COL | max:COL

Segurança: identificadores (tabela/colunas) só são aceitos se existirem no snapshot do banco
(e na whitelist de colunas da tabela exposta, se houver); valores vão SEMPRE por bind param.
Nenhum SQL vem do cliente ou da IA — apenas parâmetros estruturados.
"""
import asyncio
import logging
import re
import time as _time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from tenant_auth import get_tenant_context, TenantContext
from platform_repository import list_exposed_tables, get_schema_context, get_schema_snapshot

_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_$]*$')
_OPS = {'eq': '=', 'ne': '<>', 'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<=', 'like': 'LIKE'}
_NULL_OPS = {'isnull': 'IS NULL', 'notnull': 'IS NOT NULL'}
_AGGS = {'count', 'sum', 'avg', 'min', 'max'}
_MAX_FILTERS = 8
_MAX_LIMIT = 500

# ponytail: caches por processo (config de tabelas 30s, colunas 5min); Redis se multi-worker
_table_cache: dict[int, tuple[float, list]] = {}
_TABLE_CACHE_TTL = 30.0
_cols_cache: dict[int, tuple[float, dict]] = {}
_COLS_CACHE_TTL = 300.0

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/data", tags=["Dynamic Data"])


def _get_exposed_tables(client_id: int) -> list:
    hit = _table_cache.get(client_id)
    if hit and (_time.time() - hit[0]) < _TABLE_CACHE_TTL:
        return hit[1]
    tables = list_exposed_tables(client_id)
    _table_cache[client_id] = (_time.time(), tables)
    return tables


def get_table_columns(client_id: int) -> dict[str, dict[str, str]]:
    """{TABELA: {COLUNA: TIPO}} a partir do snapshot do mapeamento."""
    hit = _cols_cache.get(client_id)
    if hit and (_time.time() - hit[0]) < _COLS_CACHE_TTL:
        return hit[1]
    snap = get_schema_snapshot(client_id) or {}
    cols = {t['name'].upper(): {c['name'].upper(): (c.get('type') or '') for c in t.get('columns', [])}
            for t in snap.get('tables', [])}
    _cols_cache[client_id] = (_time.time(), cols)
    return cols


def _serialize_row(row, cols):
    out = {}
    for k, v in zip(cols, row):
        if v is None:
            out[k] = None
        elif isinstance(v, (int, float, bool)):
            out[k] = v
        else:
            s = str(v).strip()
            try:  # Decimal → número, para o front somar/plotar
                out[k] = float(s) if re.fullmatch(r'-?\d+\.\d+', s) else s
            except ValueError:
                out[k] = s
    return out


def _label_columns(columns: list[str], context: Optional[dict], table_name: str) -> list[dict]:
    tbl_ctx = (context or {}).get(table_name, {}) if context else {}
    col_labels = tbl_ctx.get('columns', {}) if tbl_ctx else {}
    return [{"name": c, "label": col_labels.get(c, c)} for c in columns]


def _check_table_scope(context: TenantContext, table_name: str) -> None:
    resource = f"dyn:{table_name.upper()}"
    if not context.scopes.get(resource, {}).get('read') and not context.scopes.get('*', {}).get('read'):
        raise HTTPException(status_code=403, detail=f"Acesso negado à tabela '{table_name}'")


# ── Construtor de query (função pura — testável sem banco) ──────────────────

def _bad(msg: str):
    raise HTTPException(status_code=400, detail=msg)


def build_query(table: str, allowed: Optional[set], *, fields: Optional[list] = None,
                filters: Optional[list] = None, order_by: Optional[str] = None, order: str = 'asc',
                limit: int = 50, offset: int = 0, count: bool = False,
                group_by: Optional[str] = None, agg: Optional[str] = None) -> tuple[str, list, str]:
    """
    Retorna (sql, params, mode) com mode ∈ {'list','count','group'}.
    `allowed`: colunas permitidas (None = snapshot sem colunas → valida só o formato do identificador).
    """
    if not _IDENT_RE.match(table):
        _bad("Tabela inválida")

    def col(name: str) -> str:
        n = (name or '').strip().upper()
        if not _IDENT_RE.match(n):
            _bad(f"Coluna inválida: {name!r}")
        if allowed is not None and n not in allowed:
            _bad(f"Coluna '{n}' não existe ou não está exposta nesta tabela")
        return n

    limit = max(1, min(_MAX_LIMIT, int(limit)))
    offset = max(0, int(offset))
    order = 'DESC' if str(order).lower() == 'desc' else 'ASC'

    where, params = [], []
    filters = [f for f in (filters or []) if f]
    if len(filters) > _MAX_FILTERS:
        _bad(f"Máximo de {_MAX_FILTERS} filtros")
    for f in filters:
        parts = str(f).split(':', 2)
        if len(parts) < 2:
            _bad(f"Filtro inválido: {f!r} — use COLUNA:op:valor")
        c, op = col(parts[0]), parts[1].lower()
        if op in _NULL_OPS:
            where.append(f"{c} {_NULL_OPS[op]}")
            continue
        if op not in _OPS or len(parts) < 3:
            _bad(f"Operador inválido em {f!r} — use {', '.join([*_OPS, *_NULL_OPS])}")
        val = parts[2]
        if op == 'like':
            where.append(f"UPPER({c}) LIKE UPPER(?)")
            params.append(val if '%' in val else f"%{val}%")
        else:
            where.append(f"{c} {_OPS[op]} ?")
            params.append(val)
    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    if group_by or (agg and not count):
        fn, _, agg_col = (agg or 'count').partition(':')
        fn = fn.lower()
        if fn not in _AGGS:
            _bad(f"agg inválido — use {', '.join(sorted(_AGGS))}")
        agg_expr = "COUNT(*)" if fn == 'count' and not agg_col else f"{fn.upper()}({col(agg_col)})"
        if not group_by:  # agregação sem grupo: um único valor
            return f"SELECT {agg_expr} AS VALOR FROM {table}{where_sql}", params, 'group'
        part, _, gcol = group_by.rpartition(':')
        g = col(gcol)
        part = part.lower()
        if part == 'year':
            sel, n = f"EXTRACT(YEAR FROM {g}) AS ANO", 1
        elif part == 'month':
            sel, n = f"EXTRACT(YEAR FROM {g}) AS ANO, EXTRACT(MONTH FROM {g}) AS MES", 2
        elif part == '':
            sel, n = g, 1
        else:
            _bad("group_by inválido — use COLUNA, year:COLUNA ou month:COLUNA")
        idx = ", ".join(str(i + 1) for i in range(n))
        # datas em ordem cronológica; categorias pelo maior valor primeiro
        order_sql = f"ORDER BY {idx}" if part else f"ORDER BY {n + 1} DESC"
        if order_by:  # permite forçar ordem pelo valor agregado
            order_sql = f"ORDER BY {n + 1} {order}" if order_by.upper() == 'VALOR' else order_sql
        return (f"SELECT FIRST {limit} SKIP {offset} {sel}, {agg_expr} AS VALOR FROM {table}{where_sql} "
                f"GROUP BY {idx} {order_sql}"), params, 'group'

    if count:
        return f"SELECT COUNT(*) FROM {table}{where_sql}", params, 'count'

    select = ", ".join(col(f) for f in fields) if fields else "*"
    order_sql = f" ORDER BY {col(order_by)} {order}" if order_by else ""
    return f"SELECT FIRST {limit} SKIP {offset} {select} FROM {table}{where_sql}{order_sql}", params, 'list'


# ── Núcleo compartilhado (rota HTTP, roteador de IA e MCP) ──────────────────

async def fetch_table(conn, client_id: int, scopes: dict, slug: str, limit: int = 50, offset: int = 0,
                      *, fields=None, filters=None, order_by=None, order='asc',
                      count=False, group_by=None, agg=None) -> dict:
    table_info = await _resolve_table(slug, client_id)
    table = table_info['table_name']
    _check_table_scope(TenantContext(conn, client_id, 0, scopes), table)

    all_cols = (await asyncio.to_thread(get_table_columns, client_id)).get(table.upper())
    configured = [c.upper() for c in (table_info.get('columns') or []) if _IDENT_RE.match(c)]
    allowed = set(configured) if configured else (set(all_cols) if all_cols else None)

    if isinstance(fields, str):
        fields = [f for f in fields.split(',') if f.strip()]
    if isinstance(filters, str):
        filters = [filters]
    if not fields and configured:
        fields = configured  # whitelist de colunas da tabela exposta

    sql, params, mode = build_query(table, allowed, fields=fields, filters=filters, order_by=order_by,
                                    order=order, limit=limit, offset=offset, count=count,
                                    group_by=group_by, agg=agg)

    def _query():
        cur = conn.cursor()
        try:
            cur.execute(sql, params)  # nosec: identificadores validados em build_query; valores por bind
            cols = [d[0] for d in cur.description]
            return cols, cur.fetchall()
        finally:
            cur.close()

    try:
        columns, rows = await asyncio.to_thread(_query)
    except Exception as e:
        logger.warning("dynamic query %s falhou: %s | sql=%s", slug, e, sql)
        raise HTTPException(status_code=400, detail="Consulta inválida para esta tabela — verifique tipos dos filtros (datas: AAAA-MM-DD) e colunas de agregação numéricas.")

    base = {"table": table, "slug": slug, "mode": mode}
    if mode == 'count':
        return {**base, "count": int(rows[0][0] or 0), "filters": filters or []}

    schema_ctx = await asyncio.to_thread(get_schema_context, client_id)
    tbl_ctx = (schema_ctx or {}).get(table, {}) or {}
    data = [_serialize_row(r, columns) for r in rows]
    return {
        **base,
        "purpose": tbl_ctx.get('purpose', ''),
        "columns": _label_columns(columns, schema_ctx, table),
        "data": data,
        "total": len(data),
        "limit": max(1, min(_MAX_LIMIT, int(limit))),
        "offset": max(0, int(offset)),
        "truncated": mode == 'list' and len(data) >= max(1, min(_MAX_LIMIT, int(limit))),
    }


@router.get("")
async def list_all_exposed(context: TenantContext = Depends(get_tenant_context)):
    """Tabelas expostas que ESTA api key pode ler."""
    tables = await asyncio.to_thread(list_exposed_tables, context.client_id)
    star = context.scopes.get('*', {}).get('read')
    return [t for t in tables if t['enabled'] and (star or context.scopes.get(f"dyn:{t['table_name']}", {}).get('read'))]


@router.get("/{slug}")
async def list_table(
    slug: str,
    limit: int = Query(50, ge=1, le=_MAX_LIMIT),
    offset: int = Query(0, ge=0),
    fields: Optional[str] = Query(None, description="Colunas separadas por vírgula"),
    filter: list[str] = Query(default=[], description="COLUNA:op:valor — op: eq ne gt gte lt lte like isnull notnull. Repetível."),
    order_by: Optional[str] = Query(None),
    order: str = Query('asc', pattern='^(?i)(asc|desc)$'),
    count: bool = Query(False, description="Retorna só {count} respeitando os filtros"),
    group_by: Optional[str] = Query(None, description="COLUNA, year:COLUNA ou month:COLUNA"),
    agg: Optional[str] = Query(None, description="count | sum:COL | avg:COL | min:COL | max:COL"),
    context: TenantContext = Depends(get_tenant_context),
):
    """Lista paginada, contagem ou agregação de uma tabela exposta."""
    return await fetch_table(context.conn, context.client_id, context.scopes, slug, limit, offset,
                             fields=fields, filters=filter, order_by=order_by, order=order,
                             count=count, group_by=group_by, agg=agg)


@router.get("/{slug}/{pk_id}")
async def get_table_row(slug: str, pk_id: str, context: TenantContext = Depends(get_tenant_context)):
    """Single row by PK for a dynamically exposed table."""
    table_info = await _resolve_table(slug, context.client_id)
    _check_table_scope(context, table_info['table_name'])
    if not table_info.get('pk_column'):
        raise HTTPException(status_code=400, detail=f"Tabela '{slug}' não tem PK configurada")

    res = await fetch_table(context.conn, context.client_id, context.scopes, slug, 1, 0,
                            filters=[f"{table_info['pk_column']}:eq:{pk_id}"])
    if not res['data']:
        raise HTTPException(status_code=404, detail=f"Registro não encontrado em {table_info['table_name']}")
    return {"table": res['table'], "slug": slug, "pk_column": table_info['pk_column'], "pk_value": pk_id,
            "columns": res['columns'], "data": res['data'][0]}


async def _resolve_table(slug: str, client_id: int) -> dict:
    tables = await asyncio.to_thread(_get_exposed_tables, client_id)
    match = next((t for t in tables if t['slug'] == slug and t['enabled']), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"Tabela '{slug}' não exposta ou não encontrada")
    return match
