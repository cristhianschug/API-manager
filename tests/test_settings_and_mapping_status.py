"""
Settings do provedor de IA (cifradas) e recuperação de status de mapeamento órfão.
Usa um platform.db temporário — nunca toca o banco real.
"""
import os
import pytest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("PLATFORM_ENCRYPTION_KEY", "cnQhmA9c0dVdmLTzSJz0nEExrH3fR4GHT3E64TGFfRs=")


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    import platform_db
    monkeypatch.setattr(platform_db, "PLATFORM_DB_PATH", tmp_path / "platform.db")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "x")
    platform_db.init_platform_db()
    return tmp_path / "platform.db"


def test_setting_cifrado_nao_fica_em_claro_no_sqlite(tmp_db):
    import sqlite3
    from platform_repository import set_setting, get_setting
    set_setting("ai.api_key", "sk-super-secreta-123", encrypted=True, updated_by="admin")
    set_setting("ai.model", "gpt-4o-mini", encrypted=False)
    raw = sqlite3.connect(tmp_db).execute("SELECT value FROM platform_settings WHERE key='ai.api_key'").fetchone()[0]
    assert "sk-super-secreta" not in raw
    assert get_setting("ai.api_key") == "sk-super-secreta-123"
    assert get_setting("ai.model") == "gpt-4o-mini"
    assert get_setting("inexistente") is None


def test_config_ia_prefere_settings_sobre_env(tmp_db, monkeypatch):
    import omniroute_client as oc
    from platform_repository import set_setting
    monkeypatch.setenv("AI_BASE_URL", "http://env:1/v1")
    monkeypatch.setenv("AI_MODEL", "env-model")
    oc.invalidate()
    assert oc.get_config(force=True)["base_url"] == "http://env:1/v1"
    set_setting("ai.base_url", "https://api.openai.com/v1")
    set_setting("ai.api_key", "sk-abcdefghijklmnop", encrypted=True)
    cfg = oc.get_config(force=True)
    assert cfg["base_url"] == "https://api.openai.com/v1"
    assert cfg["model"] == "env-model", "campo não salvo no painel cai para env"
    assert cfg["source"] == "settings" and cfg["provider"] == "openai", "provider inferido da URL (config legada)"
    pub = oc.public_config()
    assert pub["has_api_key"] is True
    assert "sk-abcdefghijklmnop" not in str(pub), "chave nunca volta ao painel"
    assert pub["api_key_masked"].startswith("sk-ab")


@pytest.fixture
def admin_client(tmp_db):
    import main, omniroute_client as oc
    from fastapi.testclient import TestClient
    from admin_routes import require_admin_session
    main.app.dependency_overrides[require_admin_session] = lambda: "tester"
    oc.invalidate()
    yield TestClient(main.app)
    main.app.dependency_overrides.clear()
    oc.invalidate()


def test_lista_de_fornecedores_nao_expoe_urls(admin_client):
    r = admin_client.get("/admin/api/settings/ai/providers")
    assert r.status_code == 200
    ids = [p["id"] for p in r.json()]
    assert {"openai", "groq", "openrouter", "omniroute", "custom"} <= set(ids)
    assert "http" not in r.text, "URLs dos fornecedores ficam só no backend"
    assert next(p for p in r.json() if p["id"] == "omniroute")["needs_key"] is False


def test_salvar_fornecedor_resolve_url_no_backend_e_mascara_chave(admin_client):
    import omniroute_client as oc
    r = admin_client.put("/admin/api/settings/ai", json={"provider": "groq", "model": "llama-3.3-70b-versatile", "api_key": "gsk_1234567890abcdef"})
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "groq" and body["has_api_key"] and "gsk_1234567890abcdef" not in r.text
    assert oc.get_config(force=True)["base_url"] == "https://api.groq.com/openai/v1"
    # sem api_key no body → mantém a salva (mesmo fornecedor)
    r = admin_client.put("/admin/api/settings/ai", json={"provider": "groq", "model": "outro"})
    assert r.status_code == 200 and r.json()["has_api_key"] is True and r.json()["model"] == "outro"


@pytest.mark.parametrize("body,status", [
    ({"provider": "inexistente", "model": "m", "api_key": "k"}, 422),
    ({"provider": "openai", "model": "gpt", "api_key": None}, 422),          # exige chave
    ({"provider": "openai", "api_key": "sk-x"}, 422),                         # exige modelo
    ({"provider": "custom", "model": "m", "api_key": "k", "base_url": "ftp://x"}, 422),
    ({"provider": "custom", "model": "m", "api_key": "k", "base_url": "https://gw.exemplo.com/v1/"}, 200),
    ({"provider": "ollama", "model": "llama3.1"}, 200),                       # não exige chave
])
def test_validacao_ao_salvar(admin_client, body, status):
    assert admin_client.put("/admin/api/settings/ai", json=body).status_code == status


def test_chave_de_um_fornecedor_nunca_e_usada_em_outro(admin_client):
    import omniroute_client as oc
    admin_client.put("/admin/api/settings/ai", json={"provider": "groq", "model": "m", "api_key": "gsk_secreta_groq_123"})
    assert oc._key_for("groq", None) == "gsk_secreta_groq_123"
    assert oc._key_for("openai", None) == "sk-none", "listar modelos de outro fornecedor não pode enviar a chave da Groq"
    # trocar para fornecedor sem chave apaga a antiga
    admin_client.put("/admin/api/settings/ai", json={"provider": "ollama", "model": "llama3.1"})
    assert oc.public_config()["has_api_key"] is False


def test_omniroute_local_usa_lista_de_reserva_quando_models_falha(admin_client):
    from unittest.mock import MagicMock
    import omniroute_client as oc
    fake = MagicMock(); fake.models.list.side_effect = RuntimeError("401")
    with patch.object(oc, "OpenAI", return_value=fake):
        r = admin_client.post("/admin/api/settings/ai/models", json={"provider": "omniroute"})
    assert r.status_code == 200 and r.json()["models"] == ["auto"]


def test_listar_modelos_filtra_nao_chat_e_traduz_erro_de_chave(admin_client):
    from unittest.mock import MagicMock
    import omniroute_client as oc
    fake = MagicMock()
    fake.models.list.return_value = [MagicMock(id=i) for i in ["gpt-4o-mini", "text-embedding-3-small", "whisper-1", "models/gemini-2.0-flash", "gpt-4o"]]
    with patch.object(oc, "OpenAI", return_value=fake) as ctor:
        r = admin_client.post("/admin/api/settings/ai/models", json={"provider": "openai", "api_key": "sk-abc"})
    assert r.status_code == 200
    assert r.json()["models"] == ["gemini-2.0-flash", "gpt-4o", "gpt-4o-mini"]
    assert ctor.call_args.kwargs["base_url"] == "https://api.openai.com/v1"

    class AuthErr(Exception):
        status_code = 401
    fake.models.list.side_effect = AuthErr("Incorrect API key provided: sk-abc")
    with patch.object(oc, "OpenAI", return_value=fake):
        r = admin_client.post("/admin/api/settings/ai/models", json={"provider": "openai", "api_key": "sk-abc"})
    assert r.status_code == 401 and "recusada" in r.json()["message"]
    assert "sk-abc" not in r.text, "mensagem do fornecedor (com a chave) não é repassada"


def test_status_running_orfao_vira_error_recuperavel(tmp_db):
    import schema_mapping
    from platform_repository import create_client, set_mapping_status
    with patch("platform_repository.encrypt_password", return_value="enc"), \
         patch("platform_repository.decrypt_password", return_value="x"):
        cl = create_client("A", "a", "h", 3050, "/db", "u", "p")
    set_mapping_status(cl["id"], "running", 40, "Enriquecendo")
    st = schema_mapping.status_with_recovery(cl["id"])
    assert st["status"] == "error" and st["running"] is False
    assert "interrompido" in st["error"]
    assert st["progress"] == 40


def test_status_ok_nao_e_alterado(tmp_db):
    import schema_mapping
    from platform_repository import create_client, set_mapping_status
    with patch("platform_repository.encrypt_password", return_value="enc"), \
         patch("platform_repository.decrypt_password", return_value="x"):
        cl = create_client("B", "b", "h", 3050, "/db", "u", "p")
    set_mapping_status(cl["id"], "ok", 100, "Mapeado")
    st = schema_mapping.status_with_recovery(cl["id"])
    assert st["status"] == "ok" and st["progress"] == 100
