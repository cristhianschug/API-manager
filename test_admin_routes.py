"""Tests for admin API routes"""
import os
os.environ.setdefault('JWT_SECRET_KEY', 'test-secret-for-testing-only')
os.environ.setdefault('ADMIN_BOOTSTRAP_PASSWORD', 'test-pass')
os.environ.setdefault('ENCRYPTION_KEY', 'test-encryption-key-32byteslong!!')

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


def _make_app():
    from main import app
    return app


def _authed_client(app):
    """TestClient with a valid admin session cookie injected."""
    from admin_routes import create_admin_token
    token = create_admin_token("admin")
    client = TestClient(app, cookies={"admin_token": token})
    return client


# ── Login ─────────────────────────────────────────────────────────────────────

def _mock_db(row):
    cur = MagicMock()
    cur.fetchone.return_value = row
    conn = MagicMock()
    conn.cursor.return_value = cur
    return conn


def test_login_success():
    app = _make_app()
    from passlib.context import CryptContext
    hashed = CryptContext(schemes=['argon2'], deprecated='auto').hash('secret123')
    with patch('platform_db.get_db_connection', return_value=_mock_db({'password_hash': hashed})):
        r = TestClient(app).post('/admin/api/login', data={'username': 'admin', 'password': 'secret123'})
    assert r.status_code == 200
    assert 'admin_token' in r.cookies


def test_login_wrong_password():
    app = _make_app()
    from passlib.context import CryptContext
    hashed = CryptContext(schemes=['argon2'], deprecated='auto').hash('correct')
    with patch('platform_db.get_db_connection', return_value=_mock_db({'password_hash': hashed})):
        r = TestClient(app).post('/admin/api/login', data={'username': 'admin', 'password': 'wrong'})
    assert r.status_code == 401


def test_login_unknown_user():
    app = _make_app()
    with patch('platform_db.get_db_connection', return_value=_mock_db(None)):
        r = TestClient(app).post('/admin/api/login', data={'username': 'nobody', 'password': 'x'})
    assert r.status_code == 401


# ── Session guard ─────────────────────────────────────────────────────────────

def test_protected_route_without_cookie():
    app = _make_app()
    r = TestClient(app).get('/admin/api/clients')
    assert r.status_code == 401


def test_protected_route_with_valid_token():
    app = _make_app()
    with patch('admin_routes.list_clients', return_value={'clients': [], 'total': 0}):
        r = _authed_client(app).get('/admin/api/clients')
    assert r.status_code == 200


# ── Clients ───────────────────────────────────────────────────────────────────

def test_list_clients_pagination_shape():
    app = _make_app()
    payload = {'clients': [{'id': 1, 'name': 'X', 'slug': 'x', 'status': 'active', 'created_at': '2026-01-01'}], 'total': 1}
    with patch('admin_routes.list_clients', return_value=payload):
        r = _authed_client(app).get('/admin/api/clients?limit=20&offset=0')
    assert r.status_code == 200
    data = r.json()
    assert 'clients' in data and 'total' in data


# ── Admin users ───────────────────────────────────────────────────────────────

def test_list_admins():
    app = _make_app()
    with patch('admin_routes.list_admin_users', return_value=[{'id': 1, 'username': 'admin', 'created_at': '2026-01-01'}]):
        r = _authed_client(app).get('/admin/api/admins')
    assert r.status_code == 200
    assert r.json()[0]['username'] == 'admin'


def test_delete_last_admin_blocked():
    app = _make_app()
    with patch('admin_routes.list_admin_users', return_value=[{'id': 1, 'username': 'admin', 'created_at': '2026-01-01'}]):
        r = _authed_client(app).delete('/admin/api/admins/1')
    assert r.status_code == 400


def test_cannot_delete_self():
    app = _make_app()
    admins = [
        {'id': 1, 'username': 'admin', 'created_at': '2026-01-01'},
        {'id': 2, 'username': 'other', 'created_at': '2026-01-02'},
    ]
    with patch('admin_routes.list_admin_users', return_value=admins):
        r = _authed_client(app).delete('/admin/api/admins/1')
    assert r.status_code == 400


# ── Change password ───────────────────────────────────────────────────────────

def test_change_password_wrong_current():
    app = _make_app()
    from passlib.context import CryptContext
    hashed = CryptContext(schemes=['argon2'], deprecated='auto').hash('current')
    with patch('platform_db.get_db_connection', return_value=_mock_db({'password_hash': hashed})):
        r = _authed_client(app).post('/admin/api/change-password',
                                     data={'current_password': 'wrong', 'new_password': 'newpass123'})
    assert r.status_code == 401


def test_change_password_too_short():
    app = _make_app()
    r = _authed_client(app).post('/admin/api/change-password',
                                 data={'current_password': 'x', 'new_password': 'short'})
    assert r.status_code == 400
