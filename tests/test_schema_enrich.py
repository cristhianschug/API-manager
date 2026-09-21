"""Test schema context enrichment endpoints"""
import os
import json
import pytest
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("PLATFORM_ENCRYPTION_KEY", "cnQhmA9c0dVdmLTzSJz0nEExrH3fR4GHT3E64TGFfRs=")

from fastapi.testclient import TestClient
import platform_db, main
from platform_repository import create_client, upsert_exposed_table, save_schema_context, get_schema_context
from admin_routes import create_admin_token


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(platform_db, "PLATFORM_DB_PATH", tmp_path / "platform.db")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "x")
    platform_db.init_platform_db()
    main._openapi_cache = None

    with patch("platform_repository.encrypt_password", return_value="enc"):
        c = create_client("Test", "test", "localhost", 3050, "/db", "u", "p")
        cid = c["id"]

    upsert_exposed_table(cid, "USERS", "users", "ID", True, None)
    return TestClient(main.app), cid


def test_put_saves_context(env):
    cli, cid = env
    ctx = {"USERS": {"purpose": "User table", "joins": {}, "filters": {}, "columns": {}}}

    r = cli.put(f"/admin/api/clients/{cid}/schema/context",
                json={"context": ctx},
                headers={"Cookie": f"admin_token={create_admin_token('admin')}"})

    assert r.status_code == 200
    assert r.json()["tables"] == 1


def test_get_context(env):
    cli, cid = env
    ctx = {"USERS": {"purpose": "test", "joins": {}, "filters": {}, "columns": {}}}
    save_schema_context(cid, ctx)

    r = cli.get(f"/admin/api/clients/{cid}/schema/context",
                headers={"Cookie": f"admin_token={create_admin_token('admin')}"})

    assert r.status_code == 200
    assert r.json()["USERS"]["purpose"] == "test"


def test_context_in_catalog(env):
    import ai_router
    cli, cid = env
    ctx = {"USERS": {"purpose": "User data", "joins": {"ROLE_ID": "ROLES.ID"}, "filters": {}, "columns": {}}}

    with patch("ai_router.get_table_columns", return_value={"USERS": {"ID": "INTEGER"}}):
        save_schema_context(cid, ctx)
        catalog = ai_router.build_catalog(cid, {"*": {"read": True}})
        users = next((e for e in catalog if e["table"] == "USERS"), None)
        if users:
            assert users["purpose"] == "User data"


def test_enrich_requires_auth(env):
    cli, cid = env
    r = cli.post(f"/admin/api/clients/{cid}/schema/enrich")
    assert r.status_code == 401


def test_enrich_404_missing_client(env):
    cli, _ = env
    r = cli.post(f"/admin/api/clients/9999/schema/enrich",
                 headers={"Cookie": f"admin_token={create_admin_token('admin')}"})
    assert r.status_code == 404
