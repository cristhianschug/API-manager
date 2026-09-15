"""Admin panel API routes: clients, API keys, metrics, logs"""
import firebirdsql
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Cookie
from fastapi.responses import FileResponse, JSONResponse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import json
import secrets
from passlib.context import CryptContext
from python_jose import jwt

from platform_repository import (
    create_client, get_client, list_clients, update_client_credentials_test_status,
    create_api_key, list_api_keys, revoke_api_key, rotate_api_key,
    get_request_logs, get_request_logs_total_count, get_request_metrics,
)
from ini_parser import parse_confrede_ini

router = APIRouter(prefix="/admin/api", tags=["admin"])

JWT_SECRET = __import__('os').getenv('JWT_SECRET_KEY', 'dev-secret-change-in-prod')
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

@router.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """Admin login endpoint"""
    import sqlite3
    from platform_db import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT password_hash FROM admin_users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row or not verify_admin_password(password, row['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        token = create_admin_token(username)
        return JSONResponse(
            {"message": "Logged in successfully"},
            headers={"Set-Cookie": f"admin_token={token}; HttpOnly; Secure; SameSite=Strict; Max-Age={JWT_EXPIRATION_HOURS*3600}"}
        )
    finally:
        conn.close()

@router.post("/logout")
async def logout():
    """Admin logout endpoint"""
    return JSONResponse(
        {"message": "Logged out"},
        headers={"Set-Cookie": "admin_token=; HttpOnly; Secure; SameSite=Strict; Max-Age=0"}
    )

# ============ CLIENTS ============

@router.get("/clients")
async def list_clients_route(status: str = "active", _: str = Depends(require_admin_session)):
    """List all clients"""
    return list_clients(status)

@router.post("/clients")
async def create_client_route(
    name: str = Form(...),
    slug: str = Form(...),
    confrede_file: UploadFile = File(...),
    _: str = Depends(require_admin_session)
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

        # Mark connection as tested and OK
        update_client_credentials_test_status(client['id'], True)

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
    _: str = Depends(require_admin_session)
):
    """Generate new API key for a client with scopes"""
    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    try:
        scopes = json.loads(scopes_json)
        # Validate scopes format
        valid_resources = {'clientes', 'produtos', 'pedidos', 'parcelas', 'fornecedores'}
        for resource in scopes:
            if resource not in valid_resources:
                raise ValueError(f"Invalid resource: {resource}")
            if 'read' not in scopes[resource] or 'write' not in scopes[resource]:
                raise ValueError(f"Scope for {resource} must have 'read' and 'write' booleans")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in scopes")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    key_info = create_api_key(client_id, name, scopes)
    return key_info

@router.get("/clients/{client_id}/keys")
async def list_client_keys_route(client_id: int, _: str = Depends(require_admin_session)):
    """List all API keys for a client"""
    client = get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return list_api_keys(client_id)

@router.post("/keys/{api_key_id}/revoke")
async def revoke_key_route(api_key_id: int, _: str = Depends(require_admin_session)):
    """Revoke an API key"""
    revoke_api_key(api_key_id)
    return {"message": "API key revoked"}

@router.post("/keys/{api_key_id}/rotate")
async def rotate_key_route(api_key_id: int, _: str = Depends(require_admin_session)):
    """Rotate an API key (revoke old, generate new with same name/scopes)"""
    new_key_info = rotate_api_key(api_key_id)
    return new_key_info

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

    # Return as downloadable JSON
    return FileResponse(
        content=json.dumps(collection, indent=2).encode(),
        media_type="application/json",
        filename=f"postman_collection_{client['slug']}.json"
    )
