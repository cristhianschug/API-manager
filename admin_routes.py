"""Admin panel API routes: clients, API keys, metrics, logs"""
import firebirdsql
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Cookie, Request
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json
import secrets
from passlib.context import CryptContext
from jose import jwt

from platform_repository import (
    create_client, get_client, list_clients, update_client_credentials_test_status,
    create_api_key, list_api_keys, revoke_api_key, rotate_api_key,
    get_request_logs, get_request_logs_total_count, get_request_metrics,
    list_admin_users, create_admin_user, delete_admin_user,
    log_admin_action, get_audit_logs,
    get_client_credentials_for_connection, save_schema_snapshot, get_schema_snapshot,
)
from ini_parser import parse_confrede_ini

router = APIRouter(prefix="/admin/api", tags=["admin"])

JWT_SECRET = __import__('os').environ["JWT_SECRET_KEY"]
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

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
_LOGIN_LOCKOUT_SECS = 30
_LOGIN_MAX_ATTEMPTS = 5

@router.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    """Admin login endpoint"""
    import time
    from platform_db import get_db_connection

    ip = request.client.host if request.client else "unknown"
    now = time.time()
    count, last_fail = _login_failures.get(ip, (0, 0))
    if count >= _LOGIN_MAX_ATTEMPTS and now - last_fail < _LOGIN_LOCKOUT_SECS:
        raise HTTPException(status_code=429, detail="Muitas tentativas. Aguarde 30 segundos.")

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
    return list_admin_users()

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
    admins = list_admin_users()
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
            error_msg = str(e)

        if not connection_ok:
            raise HTTPException(status_code=400, detail=f"Connection test failed: {error_msg}")

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
        raise HTTPException(status_code=404, detail="Client not found")
    return client

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
        valid_resources = {'clientes', 'produtos', 'pedidos', 'parcelas', 'fornecedores'}
        # Accept list [{resource, can_read, can_write}] or dict {resource: {read, write}}
        if isinstance(raw_scopes, list):
            scopes = {}
            for item in raw_scopes:
                r = item.get('resource')
                if r not in valid_resources:
                    raise ValueError(f"Invalid resource: {r}")
                scopes[r] = {'read': bool(item.get('can_read', True)), 'write': bool(item.get('can_write', False))}
        else:
            scopes = raw_scopes
            for resource in scopes:
                if resource not in valid_resources:
                    raise ValueError(f"Invalid resource: {resource}")
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
    _: str = Depends(require_admin_session)
):
    return get_audit_logs(limit=limit, offset=offset)

# ============ SCHEMA CATALOG ============

@router.post("/clients/{client_id}/schema/capture")
async def capture_schema(client_id: int, admin: str = Depends(require_admin_session)):
    """Introspect client's Firebird DB and store a schema snapshot."""
    import asyncio
    creds = get_client_credentials_for_connection(client_id)
    if not creds:
        raise HTTPException(status_code=404, detail="Client credentials not found")

    def _introspect():
        conn = firebirdsql.connect(**creds)
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT TRIM(r.RDB$RELATION_NAME) as name,
                       TRIM(r.RDB$RELATION_TYPE) as rel_type
                FROM RDB$RELATIONS r
                WHERE r.RDB$SYSTEM_FLAG = 0
                ORDER BY r.RDB$RELATION_NAME
            """)
            tables = [{"name": row[0], "type": "view" if row[1] == 1 else "table"} for row in cur.fetchall()]

            cur.execute("""
                SELECT TRIM(RDB$PROCEDURE_NAME) as name
                FROM RDB$PROCEDURES
                WHERE RDB$SYSTEM_FLAG = 0
                ORDER BY RDB$PROCEDURE_NAME
            """)
            procedures = [row[0] for row in cur.fetchall()]

            cur.execute("""
                SELECT TRIM(RDB$TRIGGER_NAME) as name,
                       TRIM(RDB$RELATION_NAME) as table_name
                FROM RDB$TRIGGERS
                WHERE RDB$SYSTEM_FLAG = 0
                ORDER BY RDB$RELATION_NAME, RDB$TRIGGER_NAME
            """)
            triggers = [{"name": row[0], "table": row[1]} for row in cur.fetchall()]

            return {"tables": tables, "procedures": procedures, "triggers": triggers}
        finally:
            conn.close()

    try:
        schema = await asyncio.to_thread(_introspect)
        save_schema_snapshot(client_id, schema)
        log_admin_action(admin, 'capture_schema', 'client', client_id)
        return {
            "message": "Schema capturado com sucesso",
            "tables": len(schema["tables"]),
            "procedures": len(schema["procedures"]),
            "triggers": len(schema["triggers"]),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro ao conectar ao Firebird: {e}")

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

# ============ METRICS & LOGS ============

@router.get("/metrics")
async def get_metrics_route(client_id: Optional[int] = None, hours: int = 24, _: str = Depends(require_admin_session)):
    """Get request metrics"""
    return get_request_metrics(client_id, hours)

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
    """Get filtered request logs with pagination"""
    logs = get_request_logs(
        client_id=client_id,
        method=method,
        path_filter=path_filter,
        status_code=status_code,
        hours=hours,
        limit=limit,
        offset=offset
    )
    total = get_request_logs_total_count(client_id, hours)
    return {
        "logs": logs,
        "total": total,
        "limit": limit,
        "offset": offset,
    }

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
