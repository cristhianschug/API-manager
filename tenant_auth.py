"""Tenant resolution and authorization via API key"""
import firebirdsql
from fastapi import Depends, HTTPException, Header, Request
from typing import Optional, Dict, Any
import asyncio

from platform_repository import (
    get_api_key_by_hash, hash_api_key, get_client_credentials_for_connection,
    update_api_key_last_used
)

class TenantContext:
    """Context for a multi-tenant request: connection, client, key info, scopes"""
    def __init__(self, conn: firebirdsql.Connection, client_id: int, api_key_id: int, scopes: Dict[str, Dict[str, bool]]):
        self.conn = conn
        self.client_id = client_id
        self.api_key_id = api_key_id
        self.scopes = scopes

async def get_tenant_context(request: Request, x_api_key: str = Header(...)) -> TenantContext:
    """
    Dependency: resolve X-API-Key header to tenant context.

    1. Hash the key
    2. Look up in platform.db
    3. Check if active (not revoked)
    4. Load client credentials and decrypt
    5. Open Firebird connection for that client
    6. Return context with scopes

    Raises 401 if key invalid/revoked, or if connection fails.
    """
    key_hash = hash_api_key(x_api_key)

    # Look up key in platform.db
    key_record = get_api_key_by_hash(key_hash)
    if not key_record:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if key_record['status'] != 'active':
        raise HTTPException(status_code=401, detail="API key revoked or inactive")

    client_id = key_record['client_id']
    api_key_id = key_record['id']
    scopes = key_record['scopes']

    # Load client credentials (decrypted)
    creds = get_client_credentials_for_connection(client_id)
    if not creds:
        raise HTTPException(status_code=500, detail="Client credentials not found")

    # Open Firebird connection (off event loop — firebirdsql is synchronous)
    try:
        conn = await asyncio.to_thread(
            firebirdsql.connect,
            host=creds['host'],
            port=creds['port'],
            database=creds['database'],
            user=creds['user'],
            password=creds['password'],
            charset=creds['charset'],
        )
    except Exception:
        raise HTTPException(status_code=503, detail="Database connection unavailable")

    context = TenantContext(conn, client_id, api_key_id, scopes)
    request.state.tenant_context = context
    asyncio.create_task(_update_key_usage(api_key_id))
    return context

async def _update_key_usage(api_key_id: int):
    try:
        await asyncio.to_thread(update_api_key_last_used, api_key_id)
    except Exception:
        pass

def require_scope(resource: str, mode: str = 'read'):
    """
    Dependency factory: check if tenant has permission for a resource.

    Args:
        resource: one of 'clientes', 'produtos', 'pedidos', 'parcelas', 'fornecedores'
        mode: 'read' or 'write'

    Raises 403 if scope not granted
    """
    async def check_scope(context: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        if resource not in context.scopes:
            raise HTTPException(status_code=403, detail=f"API key does not have access to {resource}")

        scope_perms = context.scopes[resource]
        can_do = scope_perms.get('read', False) if mode == 'read' else scope_perms.get('write', False)

        if not can_do:
            raise HTTPException(status_code=403, detail=f"API key does not have {mode} permission on {resource}")

        return context

    return check_scope
