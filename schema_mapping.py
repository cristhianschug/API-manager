"""
Mapeamento automático do banco Firebird de um cliente, executado em background.

Etapas (progresso 0-100 persistido em clients.mapping_*):
  1. Introspecção: tabelas, colunas, PKs, procedures, triggers → schema_snapshots
  2. Exposição: toda tabela vira endpoint /api/v1/data/{slug} (exposed_tables)
  3. Enriquecimento: IA infere propósito/joins/filtros por tabela → schema_context

mode='full'  → reprocessa tudo.
mode='sync'  → confronta snapshot novo com o contexto salvo: enriquece só tabelas novas,
               remove as que sumiram e preserva o que o admin já revisou.
"""
import asyncio
import json
import logging
import re
from typing import Optional

import firebirdsql

from omniroute_client import query_ai
from platform_repository import (
    get_client_credentials_for_connection, save_schema_snapshot,
    get_schema_context, save_schema_context,
    list_exposed_tables, upsert_exposed_table, delete_exposed_table,
    set_mapping_status, get_mapping_status,
)

log = logging.getLogger(__name__)

_IDENT_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_ENRICH_BATCH = 10
_SAMPLE_ROWS = 5

# ponytail: um job por client_id em memória; se multi-worker, mover para SQLite (status já está lá)
_jobs: dict[int, asyncio.Task] = {}


def slugify_table(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


# ── Introspecção ────────────────────────────────────────────────────────────

def introspect(creds: dict) -> dict:
    conn = firebirdsql.connect(**creds)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT TRIM(r.RDB$RELATION_NAME), r.RDB$RELATION_TYPE
            FROM RDB$RELATIONS r WHERE r.RDB$SYSTEM_FLAG = 0 ORDER BY 1""")
        tables = {row[0]: {"name": row[0], "type": "view" if row[1] == 1 else "table", "columns": [], "pk": None}
                  for row in cur.fetchall()}

        cur.execute("""
            SELECT TRIM(f.RDB$RELATION_NAME), TRIM(f.RDB$FIELD_NAME), TRIM(tp.RDB$TYPE_NAME)
            FROM RDB$RELATION_FIELDS f
            LEFT JOIN RDB$FIELDS fd ON fd.RDB$FIELD_NAME = f.RDB$FIELD_SOURCE
            LEFT JOIN RDB$TYPES tp ON tp.RDB$TYPE = fd.RDB$FIELD_TYPE AND tp.RDB$FIELD_NAME = 'RDB$FIELD_TYPE'
            WHERE f.RDB$SYSTEM_FLAG = 0
            ORDER BY f.RDB$RELATION_NAME, f.RDB$FIELD_POSITION""")
        for tbl, col, ctype in cur.fetchall():
            if tbl in tables:
                tables[tbl]["columns"].append({"name": col, "type": ctype or ""})

        cur.execute("""
            SELECT TRIM(rc.RDB$RELATION_NAME), TRIM(sg.RDB$FIELD_NAME), sg.RDB$FIELD_POSITION
            FROM RDB$RELATION_CONSTRAINTS rc
            JOIN RDB$INDEX_SEGMENTS sg ON sg.RDB$INDEX_NAME = rc.RDB$INDEX_NAME
            WHERE rc.RDB$CONSTRAINT_TYPE = 'PRIMARY KEY'
            ORDER BY 1, 3""")
        pk_segments: dict[str, list[str]] = {}
        for tbl, col, _pos in cur.fetchall():
            pk_segments.setdefault(tbl, []).append(col)
        for tbl, cols in pk_segments.items():
            if tbl in tables and len(cols) == 1:  # PK composta não vira rota /{pk_id}
                tables[tbl]["pk"] = cols[0]

        cur.execute("SELECT TRIM(RDB$PROCEDURE_NAME) FROM RDB$PROCEDURES WHERE RDB$SYSTEM_FLAG = 0 ORDER BY 1")
        procedures = [r[0] for r in cur.fetchall()]

        cur.execute("""
            SELECT TRIM(RDB$TRIGGER_NAME), TRIM(RDB$RELATION_NAME)
            FROM RDB$TRIGGERS WHERE RDB$SYSTEM_FLAG = 0 ORDER BY 2, 1""")
        triggers = [{"name": r[0], "table": r[1]} for r in cur.fetchall()]

        return {"tables": list(tables.values()), "procedures": procedures, "triggers": triggers}
    finally:
        conn.close()


def sample_tables(creds: dict, table_names: list[str]) -> dict:
    conn = firebirdsql.connect(**creds)
    cur = conn.cursor()
    samples = {}
    try:
        for tbl in table_names:
            if not _IDENT_RE.match(tbl):
                continue
            try:
                cur.execute(f"SELECT FIRST {_SAMPLE_ROWS} * FROM {tbl}")  # nosec: validado por _IDENT_RE
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                samples[tbl] = {"columns": cols,
                                "rows": [[str(v) if v is not None else None for v in r] for r in rows]}
            except Exception as e:
                log.debug("sample %s falhou: %s", tbl, e)
                samples[tbl] = {"columns": [], "rows": []}
    finally:
        conn.close()
    return samples


def enrich_batch(batch: dict) -> dict:
    prompt = (
        "Analise as tabelas Firebird abaixo com amostras de dados. "
        "Para cada tabela, infira: purpose (propósito em pt-BR, 1 frase), joins (FK relationships), "
        "filters (colunas com valores enum e seus valores), columns (significado apenas para colunas não óbvias).\n"
        "Responda SOMENTE com JSON válido no formato:\n"
        '{"NOME_TABELA": {"purpose": "...", "joins": {"COL": "OUTRA_TABELA.COL"}, '
        '"filters": {"COL": ["val1","val2"]}, "columns": {"COL": "descrição"}}}\n\n'
        f"Dados:\n{json.dumps(batch, ensure_ascii=False)}"
    )
    raw = query_ai(prompt, max_tokens=2000)
    m = re.search(r'\{.*\}', raw, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group())
    except json.JSONDecodeError:
        return {}


# ── Job ─────────────────────────────────────────────────────────────────────

def run_mapping(client_id: int, mode: str = "full") -> None:
    """Síncrono; executar via asyncio.to_thread. Persiste progresso a cada etapa."""
    def step(pct: int, msg: str):
        set_mapping_status(client_id, "running", pct, msg)

    try:
        step(2, "Conectando ao Firebird")
        creds = get_client_credentials_for_connection(client_id)
        if not creds:
            raise RuntimeError("Credenciais do cliente não encontradas")

        step(5, "Lendo tabelas, colunas e chaves")
        schema = introspect(creds)
        save_schema_snapshot(client_id, schema)
        all_tables = [t for t in schema["tables"] if t["type"] == "table"]
        names = {t["name"] for t in schema["tables"]}

        step(20, f"Expondo {len(schema['tables'])} tabelas como endpoints")
        exposed = {e["table_name"]: e for e in list_exposed_tables(client_id)}
        for t in schema["tables"]:
            if t["name"] not in exposed:
                upsert_exposed_table(client_id, t["name"], slugify_table(t["name"]), t.get("pk"), True, None)
            elif t.get("pk") and not exposed[t["name"]].get("pk_column"):
                e = exposed[t["name"]]
                upsert_exposed_table(client_id, t["name"], e["slug"], t["pk"], bool(e["enabled"]), e.get("columns") or None)
        for gone in set(exposed) - names:
            delete_exposed_table(client_id, gone)

        step(30, "Preparando enriquecimento")
        existing = get_schema_context(client_id) if mode == "sync" else None
        context = {k: v for k, v in (existing or {}).items() if not k.startswith("_")}
        context = {k: v for k, v in context.items() if k in names}  # remove tabelas que sumiram
        todo = [t["name"] for t in all_tables if mode == "full" or t["name"] not in context]

        if not todo:
            save_schema_context(client_id, context)
            set_mapping_status(client_id, "ok", 100, "Mapeamento em dia — nada novo")
            return

        samples = sample_tables(creds, todo)
        items = list(samples.items())
        total_batches = max(1, (len(items) + _ENRICH_BATCH - 1) // _ENRICH_BATCH)
        consecutive_failures = 0
        for i in range(0, len(items), _ENRICH_BATCH):
            batch = dict(items[i:i + _ENRICH_BATCH])
            done = i // _ENRICH_BATCH
            step(35 + int(60 * done / total_batches),
                 f"Enriquecendo tabelas {i + 1}–{min(i + _ENRICH_BATCH, len(items))} de {len(items)}")
            try:
                context.update(enrich_batch(batch))
                consecutive_failures = 0
            except Exception as e:
                consecutive_failures += 1
                log.warning("enrich batch %d falhou (client %d): %s", done, client_id, e)
                if consecutive_failures >= 2:
                    save_schema_context(client_id, context)
                    raise RuntimeError(
                        f"Provedor de IA indisponível — {len([k for k in context if k in names])} tabelas já enriquecidas "
                        "foram salvas. Sincronize novamente quando o provedor voltar (só o restante será processado)."
                    )
            save_schema_context(client_id, context)  # progresso parcial persiste

        set_mapping_status(client_id, "ok", 100,
                           f"{len(schema['tables'])} tabelas mapeadas, {len(todo)} enriquecidas")
    except Exception as e:
        log.error("mapping client %d falhou: %s", client_id, e)
        set_mapping_status(client_id, "error", 0, None, str(e)[:300])


def start_mapping(client_id: int, mode: str = "full") -> dict:
    """Agenda o job se não houver um em execução. Retorna status atual."""
    task = _jobs.get(client_id)
    if task and not task.done():
        return get_mapping_status(client_id) or {"status": "running"}
    set_mapping_status(client_id, "running", 0, "Na fila")
    _jobs[client_id] = asyncio.create_task(asyncio.to_thread(run_mapping, client_id, mode))
    return get_mapping_status(client_id)


def is_running(client_id: int) -> bool:
    task = _jobs.get(client_id)
    return bool(task and not task.done())


def status_with_recovery(client_id: int) -> Optional[dict]:
    """
    Status persistido + flag `running` deste processo. Se o SQLite diz 'running' mas
    nenhum job existe aqui (reinício do servidor no meio do mapeamento), marca como
    interrompido — o modo sync retoma de onde parou, pois o contexto é salvo por lote.
    """
    st = get_mapping_status(client_id)
    if st is None:
        # Default status se nunca foi iniciado
        st = set_mapping_status(client_id, 'idle', {}, None)
    running = is_running(client_id)
    if st['status'] == 'running' and not running:
        set_mapping_status(client_id, 'error', st.get('progress') or 0, None,
                           'Mapeamento interrompido (servidor reiniciou). Clique em Sincronizar para retomar.')
        st = get_mapping_status(client_id)
    st['running'] = running
    return st
