"""Admin panel API routes: clients, API keys, metrics, logs"""
import asyncio
import logging
import time as _time
import firebirdsql
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Cookie, Request
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json
import re as _re
import secrets
from passlib.context import CryptContext
from jose import jwt
from pydantic import BaseModel as _BM, Field as _Field

import ai_router
import schema_mapping
from platform_repository import (
    create_client, get_client, list_clients, update_client, update_client_credentials_test_status,
    create_api_key, list_api_keys, get_api_key_by_id, revoke_api_key, rotate_api_key,
    get_request_logs, get_request_logs_total_count, get_request_metrics,
    list_admin_users, create_admin_user, delete_admin_user,
    log_admin_action, get_audit_logs,
    get_client_credentials_for_connection, save_schema_snapshot, get_schema_snapshot,
    save_schema_context, get_schema_context, get_mapping_status,
    list_exposed_tables, upsert_exposed_table, toggle_exposed_table,
)
from ini_parser import parse_confrede_ini

_IDENT_RE = _re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_ERP_RESOURCES = {'clientes', 'produtos', 'pedidos', 'parcelas', 'fornecedores',
                  'atendimentos', 'ordens_servico', 'ordens_prestacao'}

def _valid_scope_resource(r: str) -> bool:
    """Recursos ERP fixos, '*' (todas as tabelas dinâmicas) ou 'dyn:TABELA'."""
    if r in _ERP_RESOURCES or r == '*':
        return True
    return r.startswith('dyn:') and bool(_IDENT_RE.match(r[4:]))

# ── Column cache: client_id → (timestamp, {table: [col, ...]}) — 30 min TTL ──
_col_cache: dict[int, tuple[float, dict]] = {}
_COL_CACHE_TTL = 1800

def _get_tbl_cols(client_id: int, creds: dict) -> dict[str, list[str]]:
    """Fetch all user-table column names from Firebird; cached 30 min per client."""
    cached = _col_cache.get(client_id)
    if cached and (_time.time() - cached[0]) < _COL_CACHE_TTL:
        return cached[1]
    conn = firebirdsql.connect(**creds)
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT TRIM(f.RDB$RELATION_NAME), TRIM(f.RDB$FIELD_NAME)
            FROM RDB$RELATION_FIELDS f
            JOIN RDB$RELATIONS r ON r.RDB$RELATION_NAME = f.RDB$RELATION_NAME
            WHERE r.RDB$SYSTEM_FLAG = 0 AND f.RDB$SYSTEM_FLAG = 0
            ORDER BY f.RDB$RELATION_NAME, f.RDB$FIELD_POSITION
        """)
        tbl_cols: dict[str, list[str]] = {}
        for tbl, col in cur.fetchall():
            tbl_cols.setdefault(tbl, []).append(col)
    finally:
        conn.close()
    _col_cache[client_id] = (_time.time(), tbl_cols)
    return tbl_cols

router = APIRouter(prefix="/admin/api", tags=["Admin"])

JWT_SECRET = __import__('os').environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 8

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# ============ AUTH HELPERS ============

def verify_admin_password(plain: str, hashed: str) -> bool:
    """Verify admin password"""
    return pwd_context.verify(plain, hashed)

def create_admin_token(username: str) -> str:
    """Create JWT token for admin session"""
    payload = {
        "sub": username,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_admin_token(token: str) -> str:
    """Verify JWT token and return username"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except Exception:
        return None

def require_admin_session(admin_token: Optional[str] = Cookie(None)) -> str:
    """Dependency: require valid admin session cookie"""
    if not admin_token:
        raise HTTPException(status_code=401, detail="Admin session required")

    username = verify_admin_token(admin_token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired admin session")

    return username

# ============ LOGIN ============

_login_failures: dict = {}  # ip -> (count, last_fail_ts)
_LOGIN_LOCKOUT_SECS = 300  # ponytail: em memória; Redis se multi-worker
_LOGIN_MAX_ATTEMPTS = 5

def _cleanup_login_failures() -> None:
    """Purge stale lockout entries older than 2x lockout window."""
    cutoff = _time.time() - _LOGIN_LOCKOUT_SECS * 2
    stale = [ip for ip, (_, ts) in _login_failures.items() if ts < cutoff]
    for ip in stale:
        _login_failures.pop(ip, None)

@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Admin login endpoint"""
    from platform_db import get_db_connection

    ip = request.client.host if request.client else "unknown"
    now = _time.time()
    _cleanup_login_failures()
    count, last_fail = _login_failures.get(ip, (0, 0))
    if count >= _LOGIN_MAX_ATTEMPTS and now - last_fail < _LOGIN_LOCKOUT_SECS:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde 5 minutos.")

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT password_hash FROM admin_users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row or not verify_admin_password(password, row['password_hash']):
            _login_failures[ip] = (count + 1, now)
            await __import__('asyncio').sleep(1)  # slow down brute-force
            raise HTTPException(status_code=401, detail="Credenciais inválidas")

        _login_failures.pop(ip, None)
        log_admin_action(username, 'login', 'admin_user')
        token = create_admin_token(username)
        secure = "Secure; " if request.url.scheme == "https" else ""
        return JSONResponse(
            {"message": "Logged in successfully"},
            headers={"Set-Cookie": f"admin_token={token}; HttpOnly; {secure}SameSite=Lax; Max-Age={JWT_EXPIRATION_HOURS*3600}"}
        )
    finally:
        conn.close()

@router.post("/logout")
async def logout(request: Request):
    """Admin logout endpoint"""
    secure = "Secure; " if request.url.scheme == "https" else ""
    return JSONResponse(
        {"message": "Logged out"},
        headers={"Set-Cookie": f"admin_token=; HttpOnly; {secure}SameSite=Lax; Max-Age=0"}
    )

@router.post("/change-password")
async def change_password(
    current_password: str = Form(...),
    new_password: str = Form(...),
    username: str = Depends(require_admin_session)
):
    """Change admin password"""
    from platform_db import get_db_connection
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Nova senha deve ter pelo menos 8 caracteres")
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT password_hash FROM admin_users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row or not verify_admin_password(current_password, row['password_hash']):
            raise HTTPException(status_code=401, detail="Senha atual incorreta")
        new_hash = pwd_context.hash(new_password)
        cur.execute("UPDATE admin_users SET password_hash = ? WHERE username = ?", (new_hash, username))
        conn.commit()
        log_admin_action(username, 'change_password', 'admin_user')
        return {"message": "Senha alterada com sucesso"}
    finally:
        conn.close()

# ============ CLIENTS ============

@router.get("/clients")
async def list_clients_route(
    status: str = "active",
    limit: int = 20,
    offset: int = 0,
    _: str = Depends(require_admin_session)
):
    """List clients with pagination"""
    return list_clients(status, limit=limit, offset=offset)

# ── Admin users ──────────────────────────────────────────────────────────────

@router.get("/admins")
async def list_admins_route(_: str = Depends(require_admin_session)):
    return await asyncio.to_thread(list_admin_users)

@router.post("/admins")
async def create_admin_route(
    username: str = Form(...),
    password: str = Form(...),
    _: str = Depends(require_admin_session)
):
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Senha deve ter pelo menos 8 caracteres")
    try:
        result = create_admin_user(username, pwd_context.hash(password))
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

@router.delete("/admins/{admin_id}")
async def delete_admin_route(admin_id: int, username: str = Depends(require_admin_session)):
    admins = await asyncio.to_thread(list_admin_users)
    if len(admins) <= 1:
        raise HTTPException(status_code=400, detail="Não é possível remover o último admin")
    me = next((a for a in admins if a['username'] == username), None)
    if me and me['id'] == admin_id:
        raise HTTPException(status_code=400, detail="Não é possível remover sua própria conta")
    if not delete_admin_user(admin_id):
        raise HTTPException(status_code=404, detail="Admin não encontrado")
    return {"message": "Admin removido"}

@router.post("/clients")
async def create_client_route(
    name: str = Form(...),
    slug: str = Form(...),
    confrede_file: UploadFile = File(...),
    admin: str = Depends(require_admin_session)
):
    """Create new client with confrede.ini upload"""
    try:
        # Parse confrede.ini
        content = await confrede_file.read()
        config = parse_confrede_ini(content)

        # Test connection
        try:
            test_conn = firebirdsql.connect(
                host=config['server'],
                port=config['port'],
                database=config['database'],
                user=config['username'],
                password=config['password'],
                charset=config.get('charset', 'UTF8'),
            )
            test_conn.close()
            connection_ok = True
        except Exception as e:
            connection_ok = False
            logging.getLogger("admin").warning("Teste de conexão falhou para slug=%s: %s", slug, e)

        if not connection_ok:
            raise HTTPException(status_code=400, detail="Falha no teste de conexão Firebird. Verifique host, porta, caminho do banco e credenciais.")

        # Create client with encrypted credentials
        client = create_client(
            name=name,
            slug=slug,
            host=config['server'],
            port=config['port'],
            database_path=config['database'],
            db_user=config['username'],
            db_password=config['password'],
        )

        update_client_credentials_test_status(client['id'], True)
        log_admin_action(admin, 'create_client', 'client', client['id'], f"slug={slug}")
        # Mapeamento completo em background: captura → expõe todas as tabelas → enriquece
        client['mapping'] = schema_mapping.start_mapping(client['id'], 'full')
        return client
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create client: {e}")

@router.get("/clients/{client_id}")
async def get_client_route(client_id: int, _: str = Depends(require_admin_session)):
    """Get client details"""
    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client

@router.patch("/clients/{client_id}")
async def update_client_route(
    client_id: int,
    name: Optional[str] = Form(None),
    slug: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    admin: str = Depends(require_admin_session),
):
    """Update client name, slug or status"""
    if status and status not in ('active', 'inactive', 'suspended'):
        raise HTTPException(status_code=422, detail="Status inválido. Use: active, inactive, suspended")
    result = update_client(client_id, name=name, slug=slug, status=status)
    if not result:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    log_admin_action(admin, 'update_client', 'client', client_id, f"name={name} slug={slug} status={status}")
    return result

# ============ API KEYS ============

@router.post("/clients/{client_id}/keys")
async def create_api_key_route(
    client_id: int,
    name: str = Form(...),
    scopes_json: str = Form(...),
    expires_in_days: Optional[int] = Form(None),
    admin: str = Depends(require_admin_session)
):
    """Generate new API key for a client with scopes"""
    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    try:
        raw_scopes = json.loads(scopes_json)
        # Accept list [{resource, can_read, can_write}] or dict {resource: {read, write}}
        if isinstance(raw_scopes, list):
            scopes = {}
            for item in raw_scopes:
                r = item.get('resource')
                if not _valid_scope_resource(r):
                    raise ValueError(f"Invalid resource: {r}")
                scopes[r] = {'read': bool(item.get('can_read', True)), 'write': bool(item.get('can_write', False))}
        else:
            scopes = raw_scopes
            for resource in scopes:
                if not _valid_scope_resource(resource):
                    raise ValueError(f"Invalid resource: {resource}")
        # tabelas dinâmicas são somente leitura
        for r in list(scopes):
            if r == '*' or r.startswith('dyn:'):
                scopes[r] = {'read': bool(scopes[r].get('read')), 'write': False}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in scopes")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    key_info = create_api_key(client_id, name, scopes, expires_in_days=expires_in_days)
    log_admin_action(admin, 'create_key', 'api_key', key_info['id'], f"client={client_id} name={name}")
    return key_info

@router.get("/clients/{client_id}/keys")
async def list_client_keys_route(client_id: int, _: str = Depends(require_admin_session)):
    """List all API keys for a client"""
    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return list_api_keys(client_id)

@router.post("/keys/{api_key_id}/revoke")
async def revoke_key_route(api_key_id: int, admin: str = Depends(require_admin_session)):
    """Revoke an API key"""
    revoke_api_key(api_key_id)
    log_admin_action(admin, 'revoke_key', 'api_key', api_key_id)
    return {"message": "API key revoked"}

@router.post("/keys/{api_key_id}/rotate")
async def rotate_key_route(api_key_id: int, admin: str = Depends(require_admin_session)):
    """Rotate an API key (revoke old, generate new with same name/scopes)"""
    new_key_info = rotate_api_key(api_key_id)
    log_admin_action(admin, 'rotate_key', 'api_key', api_key_id)
    return new_key_info

# ============ AUDIT LOGS ============

@router.get("/audit-logs")
async def get_audit_logs_route(
    limit: int = 50,
    offset: int = 0,
    admin_user: Optional[str] = None,
    action: Optional[str] = None,
    target_type: Optional[str] = None,
    _: str = Depends(require_admin_session)
):
    return get_audit_logs(limit=limit, offset=offset,
                          admin_user=admin_user, action=action, target_type=target_type)

# ============ SCHEMA CATALOG ============

@router.post("/clients/{client_id}/schema/capture")
async def capture_schema(client_id: int, admin: str = Depends(require_admin_session)):
    """Introspect client's Firebird DB and store a schema snapshot (sem expor/enriquecer)."""
    creds = await asyncio.to_thread(get_client_credentials_for_connection, client_id)
    if not creds:
        raise HTTPException(status_code=404, detail="Client credentials not found")
    try:
        schema = await asyncio.to_thread(schema_mapping.introspect, creds)
        await asyncio.to_thread(save_schema_snapshot, client_id, schema)
        log_admin_action(admin, 'capture_schema', 'client', client_id)
        return {
            "message": "Schema capturado com sucesso",
            "tables": len(schema["tables"]),
            "procedures": len(schema["procedures"]),
            "triggers": len(schema["triggers"]),
        }
    except Exception as e:
        logging.getLogger("admin").warning("capture_schema client %s: %s", client_id, e)
        raise HTTPException(status_code=502, detail="Erro ao conectar ao Firebird do cliente")

@router.get("/clients/{client_id}/schema")
async def get_schema(client_id: int, _: str = Depends(require_admin_session)):
    snap = get_schema_snapshot(client_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Nenhum snapshot capturado. Use POST /schema/capture primeiro.")
    return snap

@router.get("/clients/{client_id}/schema/tables")
async def get_schema_tables(client_id: int, _: str = Depends(require_admin_session)):
    snap = get_schema_snapshot(client_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Nenhum snapshot. Use /schema/capture primeiro.")
    return {"tables": snap.get("tables", []), "captured_at": snap.get("captured_at")}

@router.get("/clients/{client_id}/schema/columns")
async def get_table_columns(
    client_id: int,
    table: str,
    _: str = Depends(require_admin_session)
):
    """Introspect columns of a specific table from the client's Firebird DB."""
    import asyncio
    creds = get_client_credentials_for_connection(client_id)
    if not creds:
        raise HTTPException(status_code=404, detail="Client credentials not found")

    def _cols():
        conn = firebirdsql.connect(**creds)
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT TRIM(f.RDB$FIELD_NAME)      as col_name,
                       TRIM(tp.RDB$TYPE_NAME)      as col_type,
                       f.RDB$NULL_FLAG             as not_null,
                       f.RDB$FIELD_POSITION        as field_order
                FROM RDB$RELATION_FIELDS f
                LEFT JOIN RDB$FIELDS fd ON fd.RDB$FIELD_NAME = f.RDB$FIELD_SOURCE
                LEFT JOIN RDB$TYPES tp ON tp.RDB$TYPE = fd.RDB$FIELD_TYPE
                                      AND tp.RDB$FIELD_NAME = 'RDB$FIELD_TYPE'
                WHERE TRIM(f.RDB$RELATION_NAME) = ?
                  AND f.RDB$SYSTEM_FLAG = 0
                ORDER BY f.RDB$FIELD_POSITION
            """, (table.upper(),))
            return [{"name": r[0], "type": r[1], "not_null": bool(r[2]), "pos": r[3] or 0}
                    for r in cur.fetchall()]
        finally:
            conn.close()

    try:
        cols = await asyncio.to_thread(_cols)
        if not cols:
            raise HTTPException(status_code=404, detail=f"Tabela '{table}' nao encontrada ou sem colunas")
        return {"table": table.upper(), "columns": cols}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro Firebird: {e}")

# ============ METRICS & LOGS ============

@router.get("/metrics")
async def get_metrics_route(client_id: Optional[int] = None, hours: int = 24, _: str = Depends(require_admin_session)):
    return await asyncio.to_thread(get_request_metrics, client_id, hours)

@router.get("/logs")
async def get_logs_route(
    client_id: Optional[int] = None,
    method: Optional[str] = None,
    path_filter: Optional[str] = None,
    status_code: Optional[int] = None,
    hours: int = 24,
    limit: int = 100,
    offset: int = 0,
    _: str = Depends(require_admin_session)
):
    def _fetch():
        logs = get_request_logs(
            client_id=client_id, method=method, path_filter=path_filter,
            status_code=status_code, hours=hours, limit=limit, offset=offset,
        )
        total = get_request_logs_total_count(
            client_id=client_id, hours=hours,
            method=method, path_filter=path_filter, status_code=status_code,
        )
        return logs, total
    logs, total = await asyncio.to_thread(_fetch)
    return {"logs": logs, "total": total, "limit": limit, "offset": offset}

# ============ POSTMAN COLLECTION ============

@router.get("/clients/{client_id}/postman")
async def generate_postman_collection(client_id: int, _: str = Depends(require_admin_session)):
    """Generate Postman collection for a client with their latest API key"""
    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    keys = list_api_keys(client_id)
    if not keys or all(k['status'] != 'active' for k in keys):
        raise HTTPException(status_code=400, detail="No active API keys for this client")

    # Get latest active key
    active_key = next((k for k in keys if k['status'] == 'active'), None)
    if not active_key:
        raise HTTPException(status_code=400, detail="No active API keys")

    # Build Postman collection JSON
    collection = {
        "info": {
            "name": f"ERP Anexar API - {client['name']}",
            "description": f"API collection for client: {client['slug']}",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "auth": {
            "type": "apikey",
            "apikey": [
                {"key": "key", "value": "X-API-Key", "type": "string"},
                {"key": "value", "value": active_key['prefix'], "type": "string"},
                {"key": "in", "value": "header", "type": "string"}
            ]
        },
        "item": [
            {
                "name": "Clientes",
                "item": [
                    {
                        "name": "List Clientes",
                        "request": {
                            "method": "GET",
                            "url": {"raw": "http://localhost:8000/api/v1/clientes?limit=50&offset=0", "protocol": "http", "host": ["localhost"], "port": ["8000"], "path": ["api", "v1", "clientes"], "query": [{"key": "limit", "value": "50"}, {"key": "offset", "value": "0"}]}
                        }
                    },
                    {
                        "name": "Create Cliente",
                        "request": {
                            "method": "POST",
                            "header": [{"key": "Content-Type", "value": "application/json"}],
                            "url": {"raw": "http://localhost:8000/api/v1/clientes", "protocol": "http", "host": ["localhost"], "port": ["8000"], "path": ["api", "v1", "clientes"]},
                            "body": {"mode": "raw", "raw": json.dumps({"razao_social": "", "cpf_cnpj": "", "email": "", "fone1": "", "endereco": "", "numero": "", "cep": "", "bairro": ""}, indent=2)}
                        }
                    }
                ]
            },
            {
                "name": "Produtos",
                "item": [
                    {
                        "name": "List Produtos",
                        "request": {
                            "method": "GET",
                            "url": {"raw": "http://localhost:8000/api/v1/produtos?limit=100&offset=0", "protocol": "http", "host": ["localhost"], "port": ["8000"], "path": ["api", "v1", "produtos"], "query": [{"key": "limit", "value": "100"}, {"key": "offset", "value": "0"}]}
                        }
                    }
                ]
            },
            {
                "name": "Pedidos",
                "item": [
                    {
                        "name": "List Pedidos",
                        "request": {
                            "method": "GET",
                            "url": {"raw": "http://localhost:8000/api/v1/pedidos?limit=50&offset=0", "protocol": "http", "host": ["localhost"], "port": ["8000"], "path": ["api", "v1", "pedidos"], "query": [{"key": "limit", "value": "50"}, {"key": "offset", "value": "0"}]}
                        }
                    }
                ]
            },
            {
                "name": "Parcelas",
                "item": [
                    {
                        "name": "List Parcelas",
                        "request": {
                            "method": "GET",
                            "url": {"raw": "http://localhost:8000/api/v1/parcelas?limit=100&offset=0", "protocol": "http", "host": ["localhost"], "port": ["8000"], "path": ["api", "v1", "parcelas"], "query": [{"key": "limit", "value": "100"}, {"key": "offset", "value": "0"}]}
                        }
                    }
                ]
            },
            {
                "name": "Fornecedores",
                "item": [
                    {
                        "name": "List Fornecedores",
                        "request": {
                            "method": "GET",
                            "url": {"raw": "http://localhost:8000/api/v1/fornecedores?limit=100&offset=0", "protocol": "http", "host": ["localhost"], "port": ["8000"], "path": ["api", "v1", "fornecedores"], "query": [{"key": "limit", "value": "100"}, {"key": "offset", "value": "0"}]}
                        }
                    }
                ]
            }
        ]
    }

    from fastapi.responses import Response
    return Response(
        content=json.dumps(collection, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=postman_collection_{client['slug']}.json"}
    )


# ============ AI CHAT (roteador de endpoints — sem SQL) ============

class _AIChatMsg(_BM):
    role: str
    content: str

class AIChatRequest(_BM):
    query: str = _Field(..., max_length=2000)
    api_key_id: int
    history: list[_AIChatMsg] = []

@router.post("/ai/chat")
async def admin_ai_chat(body: AIChatRequest, _: str = Depends(require_admin_session)):
    """
    Chat IA do painel: opera COMO a API key escolhida — só vê os endpoints que ela pode ler.
    A IA escolhe endpoints do catálogo; o backend executa, cacheia e narra. Nenhum SQL é gerado.
    """
    key = await asyncio.to_thread(get_api_key_by_id, body.api_key_id)
    if not key or key['status'] != 'active':
        raise HTTPException(status_code=404, detail="API key não encontrada ou inativa")

    creds = await asyncio.to_thread(get_client_credentials_for_connection, key['client_id'])
    if not creds:
        raise HTTPException(status_code=404, detail="Credenciais do cliente não encontradas")

    try:
        conn = await asyncio.to_thread(lambda: firebirdsql.connect(**creds, timeout=10))
    except Exception as e:
        logging.getLogger("admin.ai").warning("Firebird indisponível (client %s): %s", key['client_id'], e)
        raise HTTPException(status_code=503, detail="Banco de dados do cliente indisponível")

    try:
        history = [m.model_dump() for m in body.history[-8:]]
        return await ai_router.ask(conn, key['id'], key['client_id'], key['scopes'], body.query, history)
    except HTTPException:
        raise
    except Exception as e:
        logging.getLogger("admin.ai").error("AI chat error: %s", e, exc_info=True)
        raise HTTPException(status_code=503, detail="Serviço de IA indisponível no momento")
    finally:
        await asyncio.to_thread(conn.close)


# ============ PROVEDOR DE IA (Configurações) ============
# O painel só conhece o id/nome do fornecedor; as URLs ficam no registro do backend (omniroute_client.AI_PROVIDERS).

import omniroute_client as _ai

class _AIProviderBody(_BM):
    provider: str = _Field(..., max_length=40)
    api_key: Optional[str] = _Field(None, max_length=500)   # None = usar a salva (se for do mesmo fornecedor)
    base_url: Optional[str] = _Field(None, max_length=300)  # só para provider='custom'
    model: Optional[str] = _Field(None, max_length=150)

def _ai_fail(e: Exception, what: str) -> HTTPException:
    if isinstance(e, ValueError):
        return HTTPException(status_code=422, detail=str(e))
    status = getattr(e, "status_code", None)
    logging.getLogger("admin").warning("%s falhou: %s", what, str(e)[:300])
    if status in (401, 403):
        return HTTPException(status_code=401, detail="Chave de API recusada pelo fornecedor. Confira a chave e as permissões.")
    if status == 404:
        return HTTPException(status_code=502, detail="O fornecedor não reconheceu o modelo ou o endpoint. Recarregue a lista de modelos.")
    if status == 429:
        return HTTPException(status_code=502, detail="Fornecedor respondeu limite de uso excedido (429). Verifique créditos/plano.")
    return HTTPException(status_code=502, detail="Fornecedor de IA não respondeu. Verifique a conexão do servidor com a internet e o status do fornecedor.")

@router.get("/settings/ai/providers")
async def list_ai_providers(_: str = Depends(require_admin_session)):
    return _ai.list_providers()

@router.get("/settings/ai")
async def get_ai_settings(_: str = Depends(require_admin_session)):
    return await asyncio.to_thread(_ai.public_config)

@router.post("/settings/ai/models")
async def list_ai_models(body: _AIProviderBody, _: str = Depends(require_admin_session)):
    """Autentica a chave no fornecedor e devolve os modelos disponíveis para ela."""
    try:
        models = await asyncio.to_thread(_ai.list_models, body.provider, body.api_key or None, body.base_url)
        return {"provider": body.provider, "models": models, "count": len(models)}
    except Exception as e:
        raise _ai_fail(e, "listar modelos")

@router.post("/settings/ai/test")
async def test_ai_settings(body: _AIProviderBody, _: str = Depends(require_admin_session)):
    if not body.model:
        raise HTTPException(status_code=422, detail="Selecione um modelo para testar")
    try:
        return await asyncio.to_thread(_ai.ping_provider, body.provider, body.model, body.api_key or None, body.base_url)
    except Exception as e:
        raise _ai_fail(e, "teste do provedor de IA")

@router.put("/settings/ai")
async def put_ai_settings(body: _AIProviderBody, admin: str = Depends(require_admin_session)):
    from platform_repository import set_setting
    if not body.model:
        raise HTTPException(status_code=422, detail="Selecione um modelo")
    try:
        base_url = _ai.resolve_base_url(body.provider, body.base_url)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    prev = await asyncio.to_thread(_ai.public_config)
    needs_key = _ai.AI_PROVIDERS[body.provider].get("needs_key", True)
    new_key = (body.api_key or "").strip()
    if needs_key and not new_key and not (prev["provider"] == body.provider and prev["has_api_key"]):
        raise HTTPException(status_code=422, detail="Informe a API key deste fornecedor")
    await asyncio.to_thread(set_setting, "ai.provider", body.provider, False, admin)
    await asyncio.to_thread(set_setting, "ai.base_url", base_url, False, admin)
    await asyncio.to_thread(set_setting, "ai.model", body.model.strip(), False, admin)
    if new_key:
        await asyncio.to_thread(set_setting, "ai.api_key", new_key, True, admin)
    elif prev["provider"] != body.provider:  # trocou de fornecedor sem chave (ex.: Ollama) → não reaproveita a antiga
        await asyncio.to_thread(set_setting, "ai.api_key", None, True, admin)
    _ai.invalidate()
    log_admin_action(admin, 'update_ai_settings', 'settings', None, f"provider={body.provider} model={body.model}")
    return await asyncio.to_thread(_ai.public_config)


# ============ MAPEAMENTO AUTOMÁTICO ============

@router.get("/clients/{client_id}/mapping")
async def get_mapping_route(client_id: int, _: str = Depends(require_admin_session)):
    st = await asyncio.to_thread(schema_mapping.status_with_recovery, client_id)
    if st is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return st

@router.post("/clients/{client_id}/mapping/start")
async def start_mapping_route(
    client_id: int, mode: str = "sync", admin: str = Depends(require_admin_session)
):
    """mode=full reprocessa tudo; mode=sync só acrescenta o novo e remove o que sumiu."""
    if mode not in ("full", "sync"):
        raise HTTPException(status_code=422, detail="mode deve ser 'full' ou 'sync'")
    if not await asyncio.to_thread(get_client, client_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    st = schema_mapping.start_mapping(client_id, mode)
    log_admin_action(admin, 'start_mapping', 'client', client_id, f"mode={mode}")
    return st


# ============ SCHEMA CONTEXT ============

@router.get("/clients/{client_id}/schema/context")
async def get_schema_context_route(client_id: int, _: str = Depends(require_admin_session)):
    ctx = await asyncio.to_thread(get_schema_context, client_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Contexto não gerado. Inicie o mapeamento: POST /mapping/start")
    return ctx

class _SchemaContextBody(_BM):
    context: dict

@router.put("/clients/{client_id}/schema/context")
async def put_schema_context_route(
    client_id: int, body: _SchemaContextBody, _: str = Depends(require_admin_session)
):
    await asyncio.to_thread(save_schema_context, client_id, body.context)
    # Invalidate column cache so next chat uses new semantic context
    _col_cache.pop(client_id, None)
    return {"message": "Contexto salvo", "tables": len(body.context)}


@router.post("/clients/{client_id}/schema/enrich")
async def enrich_schema_context(
    client_id: int, _: str = Depends(require_admin_session)
):
    """
    Enrich schema with semantic context inferred from Firebird data.
    Reads FIRST 5 rows from each exposed table, calls AI to infer:
    - purpose: what entity this table represents
    - joins: FK relationships to other tables (column mapping)
    - filters: enum values for categorical columns
    Returns draft context (admin must validate and save via PUT).
    """
    # Verify client exists
    client = await asyncio.to_thread(get_client, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    creds = await asyncio.to_thread(get_client_credentials_for_connection, client_id)
    if not creds:
        raise HTTPException(status_code=503, detail="Credenciais não configuradas")

    # Connect to Firebird
    try:
        conn = await asyncio.to_thread(
            lambda: firebirdsql.connect(**creds, timeout=15)
        )
    except Exception as e:
        _log.warning("Firebird connection failed for client %s: %s", client_id, e)
        raise HTTPException(status_code=503, detail="Banco de dados indisponível")

    try:
        # Get exposed tables
        tables = await asyncio.to_thread(list_exposed_tables, client_id)
        enabled_tables = [t for t in tables if t['enabled']]

        if not enabled_tables:
            raise HTTPException(status_code=400, detail="Nenhuma tabela exposta configurada")

        # Fetch sample rows for each table
        samples: Dict[str, list] = {}
        cur = await asyncio.to_thread(conn.cursor)
        for t in enabled_tables:
            try:
                await asyncio.to_thread(
                    cur.execute,
                    f"SELECT * FROM {t['table_name']} ROWS 1 TO 5"
                )
                rows = await asyncio.to_thread(cur.fetchall)
                desc = await asyncio.to_thread(lambda: cur.description)
                if rows and desc:
                    cols = [d[0] for d in desc]
                    samples[t['table_name']] = [dict(zip(cols, row)) for row in rows]
                else:
                    samples[t['table_name']] = []
            except Exception as e:
                _log.warning("Failed to sample %s: %s", t['table_name'], e)
                samples[t['table_name']] = []

        # Batch tables in groups of 10 for AI enrichment
        table_names = list(samples.keys())
        context_draft = {}

        for i in range(0, len(table_names), 10):
            batch = table_names[i : i + 10]

            # Build prompt
            tables_desc = "\n\n".join(
                f"**{tname}** (sample rows):\n"
                + _json.dumps(samples[tname][:3], indent=2, ensure_ascii=False, default=str)
                for tname in batch
            )

            prompt = f"""Analyze these {len(batch)} database tables and infer semantic context.
For each table, return a JSON object with:
- purpose: brief description of what entity it represents (1 sentence)
- joins: dict mapping column names to likely FK targets (e.g., {{"user_id": "USERS.ID"}})
- filters: dict of categorical columns and their observed values (e.g., {{"status": ["ACTIVE", "INACTIVE"]}})
- columns: dict of non-obvious column meanings (skip obvious ones like IDs)

Return ONLY valid JSON in format: {{"TABLENAME": {{"purpose": "...", "joins": {{}}, "filters": {{}}, "columns": {{}}}} }}

{tables_desc}"""

            try:
                response = await asyncio.to_thread(
                    _ai.query_ai,
                    prompt,
                    model=None,
                    temperature=0.3,  # Low temp for consistency
                    max_tokens=2000
                )
                # Parse JSON response
                # Find JSON content (may have surrounding text)
                import json as _json_parser
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    batch_result = _json_parser.loads(json_str)
                    context_draft.update(batch_result)
                else:
                    _log.warning("Failed to parse JSON from AI response (batch %d)", i // 10)
            except Exception as e:
                _log.error("AI enrichment failed for batch %d: %s", i // 10, e)
                raise HTTPException(
                    status_code=502,
                    detail=f"Serviço de IA indisponível: {str(e)[:100]}"
                )

        return {
            "context": context_draft,
            "tables_processed": len(table_names),
            "message": "Rascunho gerado. Revise e salve via PUT /schema/context"
        }

    finally:
        await asyncio.to_thread(conn.close)

# ============ EXPOSED TABLES ============

@router.get("/clients/{client_id}/exposed-tables")
async def list_exposed_tables_route(client_id: int, _: str = Depends(require_admin_session)):
    """List tables configured for dynamic REST endpoint exposure."""
    return await asyncio.to_thread(list_exposed_tables, client_id)

class _ExposeTableBody(_BM):
    table_name: str
    slug: str
    pk_column: Optional[str] = None
    columns: list[str] = []  # empty = expose all columns
    enabled: bool = True

@router.post("/clients/{client_id}/exposed-tables")
async def expose_table_route(
    client_id: int, body: _ExposeTableBody, admin: str = Depends(require_admin_session)
):
    """Expose a Firebird table as a REST endpoint at /api/v1/data/{slug}."""
    if not _IDENT_RE.match(body.table_name):
        raise HTTPException(status_code=400, detail="table_name inválido: use apenas letras, números e _")
    if body.pk_column and not _IDENT_RE.match(body.pk_column):
        raise HTTPException(status_code=400, detail="pk_column inválido: use apenas letras, números e _")
    if body.slug and not _re.match(r'^[a-z0-9_-]+$', body.slug):
        raise HTTPException(status_code=400, detail="slug inválido: use apenas letras minúsculas, números, - e _")
    bad_cols = [c for c in body.columns if not _IDENT_RE.match(c)]
    if bad_cols:
        raise HTTPException(status_code=400, detail=f"Colunas inválidas: {bad_cols}")

    # Snapshot obrigatório — valida que a tabela e colunas existem no Firebird
    snap = await asyncio.to_thread(get_schema_snapshot, client_id)
    if not snap:
        raise HTTPException(status_code=400, detail="Capture o schema primeiro: POST /admin/api/clients/{id}/schema/capture")
    snap_tables = {t['name'].upper(): t for t in snap.get('tables', [])}
    if body.table_name.upper() not in snap_tables:
        raise HTTPException(status_code=400, detail=f"Tabela '{body.table_name}' não encontrada no schema")

    # Validate selected columns against live Firebird schema
    if body.columns:
        creds = await asyncio.to_thread(get_client_credentials_for_connection, client_id)
        if not creds:
            raise HTTPException(status_code=400, detail="Credenciais do cliente não encontradas")
        tbl_cols = await asyncio.to_thread(_get_tbl_cols, client_id, creds)
        known = {c.upper() for c in tbl_cols.get(body.table_name.upper(), [])}
        bad_snap = [c for c in body.columns if c.upper() not in known]
        if bad_snap:
            raise HTTPException(status_code=400, detail=f"Colunas não existem na tabela: {bad_snap}")

    cols_to_store = [c.upper() for c in body.columns] if body.columns else []
    result = await asyncio.to_thread(
        upsert_exposed_table, client_id, body.table_name, body.slug,
        body.pk_column, body.enabled, cols_to_store or None
    )
    log_admin_action(admin, 'expose_table', 'client', client_id,
                     f"table={body.table_name} slug={body.slug} cols={len(cols_to_store) or 'all'}")
    return result

class _ToggleBody(_BM):
    enabled: bool

@router.patch("/clients/{client_id}/exposed-tables/{table_name}")
async def toggle_table_route(
    client_id: int, table_name: str, body: _ToggleBody, admin: str = Depends(require_admin_session)
):
    found = await asyncio.to_thread(toggle_exposed_table, client_id, table_name, body.enabled)
    if not found:
        raise HTTPException(status_code=404, detail=f"Tabela '{table_name}' não encontrada nos endpoints expostos")
    log_admin_action(admin, 'toggle_exposed_table', 'client', client_id,
                     f"table={table_name} enabled={body.enabled}")
    return {"message": f"Tabela '{table_name}' {'habilitada' if body.enabled else 'desabilitada'}"}
