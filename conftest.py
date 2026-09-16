"""Pytest configuration and fixtures for API Anexar v2.0"""
import os
# Set env vars before any local import reads os.environ at module level
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-for-testing-only')
os.environ.setdefault('ADMIN_BOOTSTRAP_PASSWORD', 'test-pass')
os.environ.setdefault('ENCRYPTION_KEY', 'test-encryption-key-32byteslong!!')

import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from tenant_auth import TenantContext, get_tenant_context

ALL_SCOPES = {r: {'read': True, 'write': True}
              for r in ('clientes', 'produtos', 'pedidos', 'parcelas', 'fornecedores')}


def _mock_conn():
    cur = MagicMock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


def _make_tenant(scopes=None):
    return TenantContext(
        conn=_mock_conn(),
        client_id=1,
        api_key_id=1,
        scopes=scopes if scopes is not None else dict(ALL_SCOPES),
    )


@pytest.fixture
def client():
    """Test client with full read+write scopes"""
    from main import app
    tenant = _make_tenant()
    app.dependency_overrides[get_tenant_context] = lambda: tenant
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_read_only():
    """Test client with read-only scopes"""
    from main import app
    tenant = _make_tenant(scopes={r: {'read': True, 'write': False} for r in ALL_SCOPES})
    app.dependency_overrides[get_tenant_context] = lambda: tenant
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def client_no_scope():
    """Test client with no scopes"""
    from main import app
    tenant = _make_tenant(scopes={})
    app.dependency_overrides[get_tenant_context] = lambda: tenant
    yield TestClient(app)
    app.dependency_overrides.clear()
