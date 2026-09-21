"""
Testes do caminho crítico de autenticação de tenant.
Cobre todos os cenários que geram 401, 422, 500 e 503 no browser.

Execute: pytest tests/test_tenant_auth.py -v
"""
import pytest
import anyio
from unittest.mock import patch, MagicMock
from fastapi import HTTPException


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_key_record(status="active", client_id=1, api_key_id=10):
    return {
        "id": api_key_id,
        "client_id": client_id,
        "status": status,
        "scopes": {"clientes": {"read": True, "write": False}},
    }


def _make_creds():
    return {
        "host": "localhost",
        "port": 3050,
        "database": "/data/test.fdb",
        "user": "SYSDBA",
        "password": "masterkey",
        "charset": "UTF8",
    }


def _to_thread_dispatcher(connect_result=None, connect_exc=None, calls=None):
    """
    Simula asyncio.to_thread: chamadas SQLite (get_api_key_by_hash, creds, close)
    executam a função real (já mockada); só `_connect` recebe o resultado/exceção
    configurada. `calls` acumula as funções passadas para asserção posterior.
    """
    async def fake(fn, *args, **kwargs):
        if calls is not None:
            calls.append(fn)
        if getattr(fn, "__name__", "") == "_connect":
            if connect_exc:
                raise connect_exc
            return connect_result
        return fn(*args, **kwargs)
    return fake


# ── Caminho 401 ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_api_key_invalida_retorna_401():
    """API key inexistente deve retornar 401, não 503."""
    from tenant_auth import get_tenant_context
    from unittest.mock import MagicMock

    request = MagicMock()

    with patch("tenant_auth.get_api_key_by_hash", return_value=None):
        gen = get_tenant_context(request, x_api_key="chave-falsa")
        with pytest.raises(HTTPException) as exc:
            await gen.__anext__()
        assert exc.value.status_code == 401
        assert "inválida" in exc.value.detail


@pytest.mark.anyio
async def test_api_key_revogada_retorna_401():
    """API key com status != active deve retornar 401."""
    from tenant_auth import get_tenant_context

    request = MagicMock()
    key_record = _make_key_record(status="revoked")

    with patch("tenant_auth.get_api_key_by_hash", return_value=key_record):
        gen = get_tenant_context(request, x_api_key="chave-revogada")
        with pytest.raises(HTTPException) as exc:
            await gen.__anext__()
        assert exc.value.status_code == 401
        assert "revogada" in exc.value.detail


# ── Caminho 503 ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_firebird_indisponivel_retorna_503():
    """
    Quando o Firebird recusa conexão (OperationalError), o endpoint deve retornar
    503 — nunca 500 nem travar o servidor.
    """
    import firebirdsql
    from tenant_auth import get_tenant_context

    request = MagicMock()

    with (
        patch("tenant_auth.get_api_key_by_hash", return_value=_make_key_record()),
        patch("tenant_auth.get_client_credentials_for_connection", return_value=_make_creds()),
        patch("tenant_auth.asyncio.to_thread",
              side_effect=_to_thread_dispatcher(connect_exc=firebirdsql.OperationalError("connection refused"))),
    ):
        gen = get_tenant_context(request, x_api_key="chave-valida")
        with pytest.raises(HTTPException) as exc:
            await gen.__anext__()
        assert exc.value.status_code == 503
        assert "indisponível" in exc.value.detail


@pytest.mark.anyio
async def test_firebird_timeout_retorna_503():
    """Timeout de 10s esgotado deve gerar 503, não travar o event loop."""
    import firebirdsql
    from tenant_auth import get_tenant_context

    request = MagicMock()

    with (
        patch("tenant_auth.get_api_key_by_hash", return_value=_make_key_record()),
        patch("tenant_auth.get_client_credentials_for_connection", return_value=_make_creds()),
        patch("tenant_auth.asyncio.to_thread",
              side_effect=_to_thread_dispatcher(connect_exc=firebirdsql.OperationalError("timeout"))),
    ):
        gen = get_tenant_context(request, x_api_key="chave-valida")
        with pytest.raises(HTTPException) as exc:
            await gen.__anext__()
        assert exc.value.status_code == 503


@pytest.mark.anyio
async def test_erro_inesperado_na_conexao_retorna_503():
    """Exceção genérica (OSError, etc.) também deve ser 503, não 500."""
    from tenant_auth import get_tenant_context

    request = MagicMock()

    with (
        patch("tenant_auth.get_api_key_by_hash", return_value=_make_key_record()),
        patch("tenant_auth.get_client_credentials_for_connection", return_value=_make_creds()),
        patch("tenant_auth.asyncio.to_thread",
              side_effect=_to_thread_dispatcher(connect_exc=OSError("network unreachable"))),
    ):
        gen = get_tenant_context(request, x_api_key="chave-valida")
        with pytest.raises(HTTPException) as exc:
            await gen.__anext__()
        assert exc.value.status_code == 503


# ── Caminho 500 ────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_cliente_sem_credenciais_retorna_500():
    """Cliente cadastrado sem credenciais de conexão deve retornar 500."""
    from tenant_auth import get_tenant_context

    request = MagicMock()

    with (
        patch("tenant_auth.get_api_key_by_hash", return_value=_make_key_record()),
        patch("tenant_auth.get_client_credentials_for_connection", return_value=None),
    ):
        gen = get_tenant_context(request, x_api_key="chave-valida")
        with pytest.raises(HTTPException) as exc:
            await gen.__anext__()
        assert exc.value.status_code == 500


# ── Caminho feliz + limpeza de conexão ────────────────────────────────────

@pytest.mark.anyio
async def test_conexao_fechada_no_finally_mesmo_com_excecao_no_endpoint():
    """
    A conexão Firebird deve ser fechada pelo finally mesmo se o endpoint
    levantar uma exceção — garante que não há leak de conexão.
    O finally chama asyncio.to_thread(conn.close), então verificamos
    que to_thread foi chamado com conn.close como argumento.
    """
    from tenant_auth import get_tenant_context
    import asyncio

    request = MagicMock()
    mock_conn = MagicMock()
    to_thread_calls = []

    with (
        patch("tenant_auth.get_api_key_by_hash", return_value=_make_key_record()),
        patch("tenant_auth.get_client_credentials_for_connection", return_value=_make_creds()),
        patch("tenant_auth.asyncio.to_thread",
              side_effect=_to_thread_dispatcher(connect_result=mock_conn, calls=to_thread_calls)),
        patch("tenant_auth.asyncio.create_task"),
    ):
        gen = get_tenant_context(request, x_api_key="chave-valida")
        ctx = await gen.__anext__()
        assert ctx.client_id == 1

        # Simula exceção no endpoint durante yield
        try:
            await gen.athrow(RuntimeError("erro no handler"))
        except (RuntimeError, StopAsyncIteration):
            pass

        # O finally deve ter chamado to_thread com conn.close
        assert mock_conn.close in to_thread_calls, (
            "conn.close não foi passado para asyncio.to_thread no finally — leak de conexão"
        )


# ── Isolamento entre tenants ───────────────────────────────────────────────

@pytest.mark.anyio
async def test_tenant_context_usa_client_id_da_api_key_nao_do_request():
    """
    O client_id deve vir exclusivamente do hash da API key.
    Não pode ser sobrescrito por parâmetro na requisição.
    """
    from tenant_auth import get_tenant_context

    request = MagicMock()
    mock_conn = MagicMock()

    with (
        patch("tenant_auth.get_api_key_by_hash", return_value=_make_key_record(client_id=42)),
        patch("tenant_auth.get_client_credentials_for_connection", return_value=_make_creds()),
        patch("tenant_auth.asyncio.to_thread", side_effect=_to_thread_dispatcher(connect_result=mock_conn)),
        patch("tenant_auth.asyncio.create_task"),
    ):
        gen = get_tenant_context(request, x_api_key="chave-cliente-42")
        ctx = await gen.__anext__()
        assert ctx.client_id == 42, "client_id deve ser o da API key, não pode ser manipulado"
        assert ctx.creds == _make_creds(), "creds devem ficar no contexto para o dynamic_router reusar"
