"""
Docs: Swagger UI é o motor único; spec global não vaza schema de clientes;
spec do cliente exige autenticação e respeita os escopos da API key.
"""
import os
import pytest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("PLATFORM_ENCRYPTION_KEY", "cnQhmA9c0dVdmLTzSJz0nEExrH3fR4GHT3E64TGFfRs=")


@pytest.fixture
def env(tmp_path, monkeypatch):
    import platform_db, main, dynamic_router
    from fastapi.testclient import TestClient
    from platform_repository import create_client, create_api_key, upsert_exposed_table
    monkeypatch.setattr(platform_db, "PLATFORM_DB_PATH", tmp_path / "platform.db")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "x")
    platform_db.init_platform_db()
    dynamic_router._cols_cache.clear(); dynamic_router._table_cache.clear()
    main._openapi_cache = None
    with patch("platform_repository.encrypt_password", return_value="enc"), \
         patch("platform_repository.decrypt_password", return_value="x"):
        a = create_client("Acme", "acme", "h", 3050, "/db", "u", "p")
        b = create_client("Outra", "outra", "h", 3050, "/db", "u", "p")
    for t, pk in [("TBCLIENTE", "PKCODCLI"), ("TBPEDIDO", "ID"), ("TBSEGREDO", None)]:
        upsert_exposed_table(a["id"], t, t.lower(), pk, True, None)
    keys = {
        "one":   create_api_key(a["id"], "so-cliente", {"dyn:TBCLIENTE": {"read": True}, "pedidos": {"read": True}})["full_key"],
        "star":  create_api_key(a["id"], "tudo", {"*": {"read": True}})["full_key"],
        "other": create_api_key(b["id"], "de-outro-cliente", {"*": {"read": True}})["full_key"],
    }
    return TestClient(main.app), keys


def test_docs_e_swagger_com_tema_e_csp_libera_o_css(env):
    c, _ = env
    r = c.get("/docs")
    assert r.status_code == 200
    assert "swagger-ui-bundle.js" in r.text and "swagger-ui.css" in r.text and "redoc" not in r.text.lower()
    assert "tryItOutEnabled: true" in r.text, "rotas testáveis por padrão"
    csp = r.headers["content-security-policy"]
    style = next(p for p in csp.split(";") if p.strip().startswith("style-src"))
    assert "https://cdn.jsdelivr.net" in style, "sem isso o Swagger renderiza sem estilo"


def test_redoc_removido(env):
    c, _ = env
    assert c.get("/redoc").status_code == 404


def test_spec_global_nao_expoe_tabelas_de_clientes(env):
    c, _ = env
    spec = c.get("/openapi.json").json()
    dyn = [p for p in spec["paths"] if p.startswith("/api/v1/data/")]
    assert sorted(dyn) == ["/api/v1/data/{slug}", "/api/v1/data/{slug}/{pk_id}"]
    assert "tbcliente" not in c.get("/openapi.json").text.lower()


# ── Isolamento: o gerenciador não aparece para clientes ────────────────────

INTERNOS = ("/admin", "/mcp", "/api/v1/ai", "/api/v1/connectors", "/api/v1/openapi", "/api/v1/metrics")


def test_spec_publico_nao_expoe_o_gerenciador(env):
    c, _ = env
    r = c.get("/openapi.json")
    spec = r.json()
    vazou = [p for p in spec["paths"] if p.startswith(INTERNOS)]
    assert vazou == [], f"rotas internas no spec público: {vazou[:5]}"
    assert "AdminCookie" not in spec["components"]["securitySchemes"], "esquema de sessão admin não interessa ao cliente"
    body = r.text.lower()
    for termo in ("login", "change-password", "api_key_id", "bootstrap", "mcp"):
        assert termo not in body, f"termo interno '{termo}' no spec público"


def test_spec_publico_nao_carrega_schemas_de_corpo_do_painel(env):
    c, _ = env
    schemas = c.get("/openapi.json").json()["components"].get("schemas", {})
    assert schemas, "os DTOs do ERP continuam documentados"
    assert not [k for k in schemas if k.startswith("Body_")], "corpos de formulário do painel"
    assert "AIChatRequest" not in schemas and "ConnectorCreateDTO" not in schemas


def test_console_do_cliente_so_tem_endpoints_de_dados(env):
    c, keys = env
    spec = c.get("/api/v1/openapi/acme", headers={"X-API-Key": keys["star"]}).json()
    vazou = [p for p in spec["paths"] if p.startswith(INTERNOS)]
    assert vazou == [], vazou[:5]
    assert "/api/v1/health" not in spec["paths"], "status da plataforma é do gerenciador"
    assert "/api/v1/data" in spec["paths"], "catálogo das próprias tabelas fica"
    schemas = spec["components"].get("schemas", {})
    assert not [k for k in schemas if k.startswith("Body_")]
    assert "AskRequest" not in schemas and "AIStatusResponse" not in schemas


def test_schemas_do_cliente_sao_podados_para_o_que_ele_usa(env):
    c, keys = env
    # key só com 'pedidos' → mantém os DTOs de pedido, descarta os de outros recursos
    spec = c.get("/api/v1/openapi/acme", headers={"X-API-Key": keys["one"]}).json()
    schemas = set(spec["components"].get("schemas", {}))
    assert {"PedidoListDTO", "PedidoDetailDTO"} <= schemas
    assert not any(s.startswith(("Produto", "Fornecedor", "Parcela")) for s in schemas), schemas


def test_docs_do_gerenciador_exige_sessao_admin(env):
    from admin_routes import create_admin_token
    c, _ = env
    assert c.get("/admin/api/openapi").status_code == 401
    pagina = c.get("/docs/admin")
    assert pagina.status_code == 200 and "Gerenciador de API" in pagina.text
    assert "/admin/api/login" not in pagina.text, "a página não embute o spec"
    c.cookies.set("admin_token", create_admin_token("admin"))
    spec = c.get("/admin/api/openapi").json()
    assert "/admin/api/login" in spec["paths"] and "/api/v1/data/{slug}" in spec["paths"]


def test_spec_do_cliente_exige_autenticacao(env):
    c, keys = env
    assert c.get("/api/v1/openapi/acme").status_code == 401
    assert c.get("/api/v1/openapi/acme", headers={"X-API-Key": "sk_live_inexistente"}).status_code == 401
    assert c.get("/api/v1/openapi/acme", headers={"X-API-Key": keys["other"]}).status_code == 401, "key de outro cliente"
    assert c.get("/api/v1/openapi/naoexiste", headers={"X-API-Key": keys["star"]}).status_code == 404


def test_spec_do_cliente_respeita_os_escopos_da_key(env):
    c, keys = env
    spec = c.get("/api/v1/openapi/acme", headers={"X-API-Key": keys["one"]}).json()
    paths = set(spec["paths"])
    assert "/api/v1/data/tbcliente" in paths and "/api/v1/data/tbcliente/{pk_id}" in paths
    assert "/api/v1/data/tbpedido" not in paths and "/api/v1/data/tbsegredo" not in paths
    assert "/api/v1/pedidos" in paths and "/api/v1/clientes" not in paths
    assert not any(p.startswith("/admin") for p in paths), "console do cliente não mostra rotas admin"
    assert "so-cliente" in spec["info"]["description"]


def test_spec_com_estrela_lista_tudo_agrupado_e_com_parametros_por_ref(env):
    c, keys = env
    spec = c.get("/api/v1/openapi/acme", headers={"X-API-Key": keys["star"]}).json()
    op = spec["paths"]["/api/v1/data/tbcliente"]["get"]
    assert op["tags"] == ["Tabelas · C"] and op["security"] == [{"ApiKeyAuth": []}]
    assert {"$ref": "#/components/parameters/DynFilter"} in op["parameters"]
    assert set(spec["components"]["parameters"]) >= {"DynCount", "DynFilter", "DynOrderBy", "DynGroupBy", "DynAgg"}
    assert "/api/v1/data/tbsegredo/{pk_id}" not in spec["paths"], "sem PK → sem rota por id"
    assert {t["name"] for t in spec["tags"]} == {"Tabelas · C", "Tabelas · P", "Tabelas · S"}
    assert "AdminCookie" not in spec["components"]["securitySchemes"]


def test_admin_logado_ve_a_uniao_dos_escopos(env):
    from admin_routes import create_admin_token
    c, _ = env
    assert c.get("/admin/api/openapi/acme").status_code == 401, "sem sessão admin"
    c.cookies.set("admin_token", create_admin_token("admin"))
    spec = c.get("/admin/api/openapi/acme").json()
    assert "/api/v1/data/tbsegredo" in spec["paths"] and "sessão admin" in spec["info"]["description"]
    # a rota pública NÃO aceita o cookie admin — só API key
    assert c.get("/api/v1/openapi/acme").status_code == 401


def test_pagina_do_cliente_pede_a_key_e_nao_embute_segredos(env):
    c, keys = env
    r = c.get("/docs/acme")
    assert r.status_code == 200 and 'id="dx-gate"' in r.text and "/api/v1/openapi/acme" in r.text
    assert "preauthorizeApiKey" in r.text
    assert not any(k in r.text for k in keys.values())
    assert c.get("/docs/naoexiste").status_code == 404


def test_agrupamento_simples_por_letra_sem_prefixo_tb():
    import main
    g = main._table_groups(["TBCLIENTE", "TBCHEQUE", "BIPEDIDO", "VENDAS", "TB", "TB_X"])
    assert g["TBCLIENTE"] == g["TBCHEQUE"] == "Tabelas · C"
    assert g["BIPEDIDO"] == "Tabelas · B" and g["VENDAS"] == "Tabelas · V" and g["TB"] == "Tabelas · T" and g["TB_X"] == "Tabelas · #"


def test_agrupamento_subdivide_secoes_gigantes_e_junta_sobras():
    import main
    sped = [f"TBSPED{b}{i:03d}" for b in "ABCDE" for i in range(40)]      # 200 tabelas com o mesmo prefixo
    outras = ["TBSERVICO", "TBSMS", "TBSTATUS"]                             # sobras pequenas da letra S
    g = main._table_groups(sped + outras + ["TBCLIENTE"])
    from collections import Counter
    sizes = Counter(g.values())
    assert max(sizes.values()) <= main._GROUP_MAX, sizes
    assert g["TBSPEDA000"] == "Tabelas · SPEDA" and g["TBSPEDE039"] == "Tabelas · SPEDE"
    assert g["TBSERVICO"] == g["TBSMS"] == g["TBSTATUS"] == "Tabelas · S (outras)"
    assert g["TBCLIENTE"] == "Tabelas · C"
    assert set(g) == set(sped + outras + ["TBCLIENTE"]), "nenhuma tabela fica sem seção"
