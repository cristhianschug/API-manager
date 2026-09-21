"""
Roteador de IA e mapeamento: catálogo respeita escopos da API key; nenhum SQL gerado.
Execute: pytest tests/test_ai_router.py -v
"""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("PLATFORM_ENCRYPTION_KEY", "cnQhmA9c0dVdmLTzSJz0nEExrH3fR4GHT3E64TGFfRs=")

import ai_router
import schema_mapping


_TABLES = [
    {"table_name": "TBCLIENTE", "slug": "tbcliente", "enabled": 1, "columns": [], "pk_column": "PKCODCLI"},
    {"table_name": "TBSEGREDO", "slug": "tbsegredo", "enabled": 1, "columns": [], "pk_column": None},
    {"table_name": "TBOFF", "slug": "tboff", "enabled": 0, "columns": [], "pk_column": None},
]
_CTX = {"TBCLIENTE": {"purpose": "Cadastro de clientes", "columns": {"RAZAOSOCIAL": "Nome"}}}


_TYPED = {"TBCLIENTE": {"PKCODCLI": "LONG", "RAZAOSOCIAL": "VARYING", "DATACAD": "TIMESTAMP"},
          "TBSEGREDO": {"ID": "LONG"}, "TBOFF": {"ID": "LONG"}}


def _catalog(scopes):
    with patch("ai_router.list_exposed_tables", return_value=_TABLES), \
         patch("ai_router.get_schema_context", return_value=_CTX), \
         patch("ai_router.get_table_columns", return_value=_TYPED):
        return ai_router.build_catalog(1, scopes)


def test_catalogo_traz_colunas_tipadas_com_pk_primeiro():
    cli = next(c for c in _catalog({"*": {"read": True}}) if c['table'] == 'TBCLIENTE')
    assert list(cli['columns'])[0] == "PKCODCLI"
    assert cli['columns']['DATACAD'] == "TIMESTAMP"


@pytest.mark.anyio
async def test_fetch_endpoint_repassa_parametros_de_consulta():
    with patch("ai_router.fetch_table", return_value={"mode": "count", "count": 7}) as ft:
        await ai_router.fetch_endpoint(MagicMock(), 1, {"*": {"read": True}}, "/api/v1/data/tbcliente",
                                       {"count": "true", "filter": ["STATUS:eq:1"], "limit": 5, "sql": "DROP"})
    kw = ft.call_args.kwargs
    assert kw == {"count": True, "filters": ["STATUS:eq:1"]}, "só chaves conhecidas passam; 'sql' é descartado"


@pytest.mark.anyio
async def test_ask_repara_consulta_rejeitada_uma_vez():
    from fastapi import HTTPException
    ai_router._cache.clear()
    cat = [{"path": "/api/v1/data/tbcliente", "table": "TBCLIENTE", "columns": {"DATACAD": "TIMESTAMP"}}]
    bad = '{"calls":[{"path":"/api/v1/data/tbcliente","params":{"count":true,"filters":["DT:gte:2026-01-01"]}}]}'
    good = '{"calls":[{"path":"/api/v1/data/tbcliente","params":{"count":true,"filters":["DATACAD:gte:2026-01-01"]}}]}'
    calls = []
    async def fake_fetch(conn, cid, scopes, path, params):
        calls.append(params)
        if "DT:gte" in str(params): raise HTTPException(400, "Coluna 'DT' não existe")
        return {"mode": "count", "count": 276}
    with patch("ai_router.build_catalog", return_value=cat), \
         patch("ai_router.query_ai", side_effect=[bad, good, "Foram 276 clientes."]) as qa, \
         patch("ai_router.fetch_endpoint", side_effect=fake_fetch):
        res = await ai_router.ask(MagicMock(), 9, 1, {"*": {"read": True}}, "quantos clientes em 2026?")
    assert len(calls) == 2 and qa.call_count == 3
    assert "Coluna 'DT' não existe" in qa.call_args_list[1].args[0], "o erro volta ao planejador"
    assert res['data'] == [{"count": 276}] and res['warnings'] == []
    assert res['queries'][0]['params']['filters'] == ["DATACAD:gte:2026-01-01"]


def test_narrador_recebe_tipo_do_resultado():
    s = ai_router._summarize_result({"path": "/p", "params": {}, "data": {"mode": "count", "count": 3373}})
    assert s['tipo'] == 'contagem exata' and s['count'] == 3373
    s = ai_router._summarize_result({"path": "/p", "params": {}, "data": {"mode": "list", "truncated": True, "data": [{"a": 1}] * 500}})
    assert 'PARCIAL' in s['tipo'] and len(s['linhas']) == 25


def test_catalogo_so_inclui_tabelas_com_escopo_dyn():
    paths = {c['path'] for c in _catalog({"dyn:TBCLIENTE": {"read": True}})}
    assert paths == {"/api/v1/data/tbcliente"}


def test_escopo_estrela_libera_todas_as_tabelas_habilitadas():
    paths = {c['path'] for c in _catalog({"*": {"read": True}})}
    assert "/api/v1/data/tbcliente" in paths
    assert "/api/v1/data/tbsegredo" in paths
    assert "/api/v1/data/tboff" not in paths, "tabela desabilitada não entra"


def test_escopo_erp_gera_lista_e_summary():
    paths = {c['path'] for c in _catalog({"pedidos": {"read": True}})}
    assert paths == {"/api/v1/pedidos", "/api/v1/pedidos/summary"}


def test_catalogo_carrega_semantica_do_contexto():
    cat = _catalog({"*": {"read": True}})
    cli = next(c for c in cat if c['table'] == 'TBCLIENTE')
    assert cli['purpose'] == "Cadastro de clientes"
    assert cli['column_meaning'] == {"RAZAOSOCIAL": "Nome"}


@pytest.mark.anyio
async def test_fetch_endpoint_fora_do_catalogo_e_rejeitado():
    with pytest.raises(ValueError):
        await ai_router.fetch_endpoint(MagicMock(), 1, {"*": {"read": True}}, "/admin/api/clients", {})
    with pytest.raises(ValueError):
        await ai_router.fetch_endpoint(MagicMock(), 1, {"*": {"read": True}}, "/api/v1/data/x; DROP", {})


@pytest.mark.anyio
async def test_fetch_endpoint_erp_sem_escopo_levanta_permission_error():
    with pytest.raises(PermissionError):
        await ai_router.fetch_endpoint(MagicMock(), 1, {"clientes": {"read": True}}, "/api/v1/pedidos", {})


@pytest.mark.anyio
async def test_plano_ignora_paths_fora_do_catalogo():
    cat = [{"path": "/api/v1/data/tbcliente"}]
    fake = '{"calls": [{"path": "/api/v1/data/tbcliente", "params": {"limit": 5}}, {"path": "/api/v1/data/tbsegredo"}], "answer": null}'
    with patch("ai_router.query_ai", return_value=fake):
        plan = ai_router._plan_calls("quantos clientes?", [], cat)
    assert [c['path'] for c in plan['calls']] == ["/api/v1/data/tbcliente"]


@pytest.mark.anyio
async def test_ask_sem_catalogo_responde_sem_chamar_ia():
    with patch("ai_router.build_catalog", return_value=[]), patch("ai_router.query_ai") as qa:
        res = await ai_router.ask(MagicMock(), 1, 1, {}, "oi")
    qa.assert_not_called()
    assert "permissão" in res['answer']


@pytest.mark.anyio
async def test_ask_usa_cache_na_segunda_chamada():
    ai_router._cache.clear()
    cat = [{"path": "/api/v1/data/tbcliente"}]
    plan = '{"calls": [{"path": "/api/v1/data/tbcliente", "params": {"limit": 5}}], "answer": null}'
    fetched = {"data": [{"A": 1}], "columns": [{"name": "A"}]}
    with patch("ai_router.build_catalog", return_value=cat), \
         patch("ai_router.query_ai", side_effect=[plan, "resposta", plan, "resposta2"]), \
         patch("ai_router.fetch_endpoint", return_value=fetched) as fe:
        await ai_router.ask(MagicMock(), 7, 1, {"*": {"read": True}}, "q")
        await ai_router.ask(MagicMock(), 7, 1, {"*": {"read": True}}, "q")
    assert fe.call_count == 1, "segunda pergunta idêntica deve vir do cache"


def test_select_catalog_prioriza_tabelas_relevantes_e_mantem_erp():
    big = [{"path": f"/api/v1/data/t{i}", "table": f"T{i}", "purpose": "", "columns": []} for i in range(200)]
    big.append({"path": "/api/v1/data/tbcliente", "table": "TBCLIENTE", "purpose": "Cadastro de clientes", "columns": ["RAZAOSOCIAL", "DATACAD"]})
    big.append({"path": "/api/v1/data/tbpedido", "table": "TBPEDIDO", "purpose": "Pedidos de venda", "columns": ["DTPEDIDO"]})
    big.append({"path": "/api/v1/pedidos", "purpose": "Pedidos de venda"})
    sel = ai_router.select_catalog("quantos clientes temos e quais os pedidos recentes?", [], big, limit=10)
    paths = [c['path'] for c in sel]
    assert len(sel) == 10
    assert "/api/v1/pedidos" in paths, "recursos ERP entram sempre"
    assert paths.index("/api/v1/data/tbcliente") < 3 and paths.index("/api/v1/data/tbpedido") < 3


def test_select_catalog_pequeno_nao_filtra():
    cat = [{"path": "/api/v1/data/a"}, {"path": "/api/v1/data/b"}]
    assert ai_router.select_catalog("x", [], cat, limit=40) == cat


@pytest.mark.anyio
async def test_ask_com_provedor_fora_responde_amigavel_sem_503():
    cat = [{"path": "/api/v1/data/tbcliente"}]
    with patch("ai_router.build_catalog", return_value=cat), \
         patch("ai_router.query_ai", side_effect=RuntimeError("AI provider error: 502")):
        res = await ai_router.ask(MagicMock(), 1, 1, {"*": {"read": True}}, "quantos clientes?")
    assert "provedor de ia" in res['answer'].lower()
    assert res['warnings'] == ["provedor de IA indisponível"]


def test_query_ai_repete_em_5xx_e_nao_em_4xx(monkeypatch):
    import omniroute_client as oc
    monkeypatch.setattr(oc.time, "sleep", lambda s: None)
    calls = {"n": 0}
    class Err(Exception):
        def __init__(self, code): super().__init__(f"code {code}"); self.status_code = code
    def make(code, then_ok=False):
        def create(**kw):
            calls["n"] += 1
            if then_ok and calls["n"] > 1:
                m = MagicMock(); m.choices = [MagicMock(message=MagicMock(content="ok"))]; return m
            raise Err(code)
        c = MagicMock(); c.chat.completions.create = create; return c
    with patch.object(oc, "get_client", return_value=make(502, then_ok=True)), patch.object(oc, "get_config", return_value={"model": "m"}):
        assert oc.query_ai("p") == "ok" and calls["n"] == 2
    calls["n"] = 0
    with patch.object(oc, "get_client", return_value=make(401)), patch.object(oc, "get_config", return_value={"model": "m"}):
        with pytest.raises(RuntimeError):
            oc.query_ai("p")
        assert calls["n"] == 1, "4xx não deve repetir"


# ── schema_mapping ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("name,slug", [
    ("TBCLIENTE", "tbcliente"), ("TB_ORDEM_SERVICO", "tb-ordem-servico"), ("ITENS$X", "itens-x"),
])
def test_slugify_table(name, slug):
    assert schema_mapping.slugify_table(name) == slug


def test_run_mapping_sync_preserva_contexto_e_remove_tabelas_que_sumiram():
    schema = {"tables": [{"name": "TBNOVA", "type": "table", "columns": [], "pk": "ID"},
                         {"name": "TBVELHA", "type": "table", "columns": [], "pk": None}],
              "procedures": [], "triggers": []}
    existing_ctx = {"TBVELHA": {"purpose": "já revisada"}, "TBSUMIU": {"purpose": "x"}, "_generated_at": "t"}
    saved = {}
    statuses = []
    with patch("schema_mapping.get_client_credentials_for_connection", return_value={"host": "h"}), \
         patch("schema_mapping.introspect", return_value=schema), \
         patch("schema_mapping.save_schema_snapshot"), \
         patch("schema_mapping.list_exposed_tables", return_value=[{"table_name": "TBSUMIU", "slug": "tbsumiu", "enabled": 1, "pk_column": None, "columns": []}]), \
         patch("schema_mapping.upsert_exposed_table") as up, \
         patch("schema_mapping.delete_exposed_table") as dele, \
         patch("schema_mapping.get_schema_context", return_value=existing_ctx), \
         patch("schema_mapping.save_schema_context", side_effect=lambda cid, ctx: saved.update(ctx)), \
         patch("schema_mapping.sample_tables", return_value={"TBNOVA": {"columns": [], "rows": []}}) as samp, \
         patch("schema_mapping.enrich_batch", return_value={"TBNOVA": {"purpose": "nova"}}), \
         patch("schema_mapping.set_mapping_status", side_effect=lambda *a, **k: statuses.append(a)):
        schema_mapping.run_mapping(1, mode="sync")

    exposed = {c.args[1] for c in up.call_args_list}
    assert exposed == {"TBNOVA", "TBVELHA"}
    dele.assert_called_once_with(1, "TBSUMIU")
    assert samp.call_args.args[1] == ["TBNOVA"], "sync só enriquece tabelas novas"
    assert saved["TBVELHA"]["purpose"] == "já revisada", "contexto revisado preservado"
    assert "TBSUMIU" not in saved
    assert saved["TBNOVA"]["purpose"] == "nova"
    assert statuses[-1][1] == "ok" and statuses[-1][2] == 100


def test_run_mapping_aborta_apos_2_falhas_consecutivas_do_provedor_preservando_parcial():
    schema = {"tables": [{"name": f"T{i}", "type": "table", "columns": [], "pk": None} for i in range(30)],
              "procedures": [], "triggers": []}
    saved, statuses = {}, []
    results = iter([{"T0": {"purpose": "ok"}}, RuntimeError("502"), RuntimeError("502"), {"T30": {}}])
    def fake_enrich(batch):
        r = next(results)
        if isinstance(r, Exception): raise r
        return r
    with patch("schema_mapping.get_client_credentials_for_connection", return_value={"host": "h"}), \
         patch("schema_mapping.introspect", return_value=schema), \
         patch("schema_mapping.save_schema_snapshot"), \
         patch("schema_mapping.list_exposed_tables", return_value=[]), \
         patch("schema_mapping.upsert_exposed_table"), \
         patch("schema_mapping.delete_exposed_table"), \
         patch("schema_mapping.get_schema_context", return_value=None), \
         patch("schema_mapping.save_schema_context", side_effect=lambda cid, ctx: saved.update(ctx)), \
         patch("schema_mapping.sample_tables", return_value={t["name"]: {"columns": [], "rows": []} for t in schema["tables"]}), \
         patch("schema_mapping.enrich_batch", side_effect=fake_enrich) as eb, \
         patch("schema_mapping.set_mapping_status", side_effect=lambda *a, **k: statuses.append(a)):
        schema_mapping.run_mapping(1)
    assert eb.call_count == 3, "1 sucesso + 2 falhas consecutivas → aborta (não tenta o 4º lote)"
    assert saved == {"T0": {"purpose": "ok"}}, "parcial preservado"
    assert statuses[-1][1] == "error" and "Provedor de IA" in statuses[-1][4]


def test_run_mapping_erro_grava_status_error_sem_vazar_traceback():
    statuses = []
    with patch("schema_mapping.get_client_credentials_for_connection", return_value=None), \
         patch("schema_mapping.set_mapping_status", side_effect=lambda *a, **k: statuses.append(a)):
        schema_mapping.run_mapping(1)
    assert statuses[-1][1] == "error"
    assert "Credenciais" in statuses[-1][4]
