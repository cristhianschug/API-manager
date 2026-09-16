"""Tests for API Anexar v2.0 — multi-tenant endpoints"""
from unittest.mock import patch
from fastapi.testclient import TestClient


# ── Health ───────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "2.0.0"
    assert data["database"] == "firebird"
    assert "platform_db" in data


# ── Auth / scope guards ───────────────────────────────────────────────────────

def test_missing_api_key_returns_422(client):
    # Missing required header → FastAPI 422 before dependency is called
    from main import app
    from tenant_auth import get_tenant_context
    saved = dict(app.dependency_overrides)
    app.dependency_overrides.clear()
    try:
        r = TestClient(app, raise_server_exceptions=False).get("/api/v1/clientes")
        assert r.status_code == 422
    finally:
        app.dependency_overrides.update(saved)


def test_no_scope_returns_403(client_no_scope):
    r = client_no_scope.get("/api/v1/clientes")
    assert r.status_code == 403


def test_read_only_cannot_post_cliente(client_read_only):
    r = client_read_only.post("/api/v1/clientes", json={
        "razao_social": "Test", "nome_fantasia": "Test",
        "cpf_cnpj": "12345678000100", "email": "t@t.com",
        "fone1": "11999990000", "endereco": "Rua A",
        "numero": "1", "cep": "01310100", "bairro": "Centro",
    })
    assert r.status_code == 403


# ── Clientes ──────────────────────────────────────────────────────────────────

def test_list_clientes_empty(client):
    r = client.get("/api/v1/clientes")
    assert r.status_code == 200
    assert r.json() == []


def test_get_cliente_not_found(client):
    r = client.get("/api/v1/clientes/99999")
    assert r.status_code == 404


# ── Produtos / Pedidos (smoke) ────────────────────────────────────────────────

def test_list_produtos_empty(client):
    r = client.get("/api/v1/produtos")
    assert r.status_code == 200
    assert r.json() == []


def test_list_pedidos_empty(client):
    r = client.get("/api/v1/pedidos")
    assert r.status_code == 200
    assert r.json() == []


# ── Per-client OpenAPI spec ───────────────────────────────────────────────────

def test_client_openapi_not_found():
    from main import app
    with patch("main.get_client_by_slug", return_value=None):
        r = TestClient(app).get("/api/v1/openapi/nonexistent")
    assert r.status_code == 404


def test_client_openapi_inactive_returns_404():
    from main import app
    inactive = {"id": 1, "name": "X", "slug": "x", "status": "inactive"}
    with patch("main.get_client_by_slug", return_value=inactive):
        r = TestClient(app).get("/api/v1/openapi/x")
    assert r.status_code == 404


def test_client_openapi_filters_by_scope():
    from main import app
    fake_client = {"id": 1, "name": "Test Corp", "slug": "test", "status": "active"}
    # Only clientes read, no write; no produtos
    fake_scopes = {"clientes": {"read": True, "write": False}}
    with patch("main.get_client_by_slug", return_value=fake_client), \
         patch("main.get_client_all_scopes", return_value=fake_scopes):
        r = TestClient(app).get("/api/v1/openapi/test")
    assert r.status_code == 200
    spec = r.json()
    assert "Test Corp" in spec["info"]["title"]
    paths = spec["paths"]
    assert "/api/v1/health" in paths
    # clientes list: GET allowed (read=True)
    assert "get" in paths.get("/api/v1/clientes", {})
    # clientes POST must be absent (write=False)
    assert "post" not in paths.get("/api/v1/clientes", {})
    # produtos must be absent entirely (not in scopes)
    assert "/api/v1/produtos" not in paths


# ── Per-client ReDoc page ─────────────────────────────────────────────────────

def test_client_docs_not_found():
    from main import app
    with patch("main.get_client_by_slug", return_value=None):
        r = TestClient(app).get("/docs/nonexistent")
    assert r.status_code == 404


def test_client_docs_returns_html():
    from main import app
    fake_client = {"id": 1, "name": "Test Corp", "slug": "test", "status": "active"}
    with patch("main.get_client_by_slug", return_value=fake_client):
        r = TestClient(app).get("/docs/test")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "redoc" in r.text.lower()
    assert "test" in r.text  # spec-url contains the slug
