"""
Regressão das correções de segurança/performance.
Execute: pytest tests/test_security_hardening.py -v
"""
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("PLATFORM_ENCRYPTION_KEY", "cnQhmA9c0dVdmLTzSJz0nEExrH3fR4GHT3E64TGFfRs=")

from fastapi.testclient import TestClient
import main

client = TestClient(main.app)


# ── Security headers ───────────────────────────────────────────────────────

def test_security_headers_presentes_no_health():
    r = client.get("/api/v1/health")
    assert r.headers["X-Frame-Options"] == "DENY"
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["Referrer-Policy"] == "no-referrer"


def test_security_headers_presentes_no_admin_html():
    r = client.get("/admin")
    assert r.status_code == 200
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "cdn.jsdelivr.net" in r.headers["Content-Security-Policy"], "Chart.js precisa estar na CSP"


# ── Exposição de dados ─────────────────────────────────────────────────────

def test_get_client_nao_retorna_senha_firebird():
    from platform_repository import get_client
    fake_row = {
        'id': 1, 'name': 'X', 'slug': 'x', 'status': 'active', 'created_at': None,
        'host': 'h', 'port': 3050, 'database_path': '/db', 'db_user': 'u',
        'db_password_encrypted': 'gAAAA-encrypted', 'charset': 'UTF8',
        'last_tested_at': None, 'last_test_ok': 1,
    }
    cur = MagicMock(); cur.fetchone.return_value = fake_row
    conn = MagicMock(); conn.cursor.return_value = cur
    with patch("platform_repository.get_db_connection", return_value=conn):
        result = get_client(1)
    assert 'db_password' not in result
    assert result['has_password'] is True
    assert 'encrypted' not in str(result)


def test_openapi_nao_expoe_header_manual_x_api_key_e_declara_security_scheme():
    spec = client.get("/openapi.json").json()
    schemes = spec['components']['securitySchemes']
    assert schemes['ApiKeyAuth']['name'] == 'X-API-Key'
    clientes = spec['paths']['/api/v1/clientes']['get']
    assert clientes['security'] == [{'ApiKeyAuth': []}]
    assert clientes['tags'] == ['Clientes']
    # rotas do painel só existem no spec interno (ver tests/test_docs.py)
    assert '/admin/api/login' not in spec['paths']
    full = main._full_openapi()
    assert full['components']['securitySchemes']['AdminCookie']['in'] == 'cookie'
    assert full['paths']['/admin/api/login']['post']['security'] == [{'AdminCookie': []}]


# ── Chat/MCP operam por API key e sem SQL ──────────────────────────────────

def test_admin_chat_nao_gera_sql():
    import admin_routes, ai_router, inspect
    assert not hasattr(admin_routes, '_run_sql')
    src = inspect.getsource(ai_router)
    assert 'firebirdsql.connect' not in src, "ai_router não deve abrir conexões próprias"
    assert 'cur.execute' not in src, "ai_router não deve executar SQL"


@pytest.mark.parametrize("resource,ok", [
    ("clientes", True), ("*", True), ("dyn:TBCLIENTE", True), ("dyn:tb_x9", True),
    ("dyn:RDB$RELATIONS", False), ("dyn:1abc", False), ("admin", False), ("dyn:", False),
])
def test_valid_scope_resource(resource, ok):
    from admin_routes import _valid_scope_resource
    assert _valid_scope_resource(resource) is ok


# ── Limites de payload IA ──────────────────────────────────────────────────

def test_summarize_rejeita_texto_acima_do_limite():
    from tenant_auth import get_tenant_context
    async def fake_ctx():
        yield MagicMock(client_id=1)
    main.app.dependency_overrides[get_tenant_context] = fake_ctx
    try:
        r = client.post("/api/v1/ai/summarize", json={"text": "a" * 50_001})
        assert r.status_code == 422
    finally:
        main.app.dependency_overrides.clear()


def test_mensagem_de_erro_ia_nao_vaza_detalhe_interno():
    from tenant_auth import get_tenant_context
    async def fake_ctx():
        yield MagicMock(client_id=1)
    main.app.dependency_overrides[get_tenant_context] = fake_ctx
    try:
        with patch("ai_routes.summarize_text", side_effect=RuntimeError("Connection refused http://localhost:20128")):
            r = client.post("/api/v1/ai/summarize", json={"text": "ola"})
        assert r.status_code == 503
        assert "20128" not in r.text
        assert "localhost" not in r.text
    finally:
        main.app.dependency_overrides.clear()


# ── Sessão admin ───────────────────────────────────────────────────────────

def test_jwt_admin_expira_em_8h():
    from admin_routes import JWT_EXPIRATION_HOURS
    assert JWT_EXPIRATION_HOURS <= 8


def test_lockout_login_minimo_5_minutos():
    from admin_routes import _LOGIN_LOCKOUT_SECS
    assert _LOGIN_LOCKOUT_SECS >= 300
