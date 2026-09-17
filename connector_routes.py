"""
Connector system: male/female binding between dashboards/apps and API routes.

Admin endpoints (require admin session):
  GET/POST  /admin/api/connectors
  DELETE    /admin/api/connectors/{id}
  GET/POST  /admin/api/clients/{client_id}/connectors/{connector_id}/bindings
  POST      /admin/api/clients/{client_id}/connectors/{connector_id}/suggest
  POST      /admin/api/connectors/bindings/{binding_id}/approve
  POST      /admin/api/connectors/bindings/{binding_id}/reject
  DELETE    /admin/api/connectors/bindings/{binding_id}

Tenant endpoint (API key auth, any active key):
  POST /api/v1/connectors/{connector_id}/execute
    → runs all active bindings for this connector+client in parallel
    → returns {query_id: result, ...}
"""
import asyncio
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from admin_routes import require_admin_session
from tenant_auth import get_tenant_context, TenantContext
from platform_repository import (
    create_connector, get_connector, list_connectors, delete_connector,
    upsert_binding, get_bindings, update_binding_status, delete_binding,
    suggest_bindings_from_catalog, log_admin_action,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── DTOs ────────────────────────────────────────────────────────────────────

class ConnectorCreateDTO(BaseModel):
    name: str
    description: Optional[str] = None
    contract: dict = {}

class BindingCreateDTO(BaseModel):
    query_id: str
    route: str
    params: dict = {}
    instance_name: Optional[str] = None

# ── Admin: Connector definitions ────────────────────────────────────────────

@router.get("/admin/api/connectors", tags=["Admin"])
async def list_connectors_route(_: str = Depends(require_admin_session)):
    return list_connectors()

@router.post("/admin/api/connectors", tags=["Admin"])
async def create_connector_route(body: ConnectorCreateDTO, admin: str = Depends(require_admin_session)):
    try:
        c = create_connector(body.name, body.description or '', body.contract)
        log_admin_action(admin, 'create_connector', 'connector', c['id'])
        return c
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/admin/api/connectors/{connector_id}", tags=["Admin"])
async def delete_connector_route(connector_id: int, admin: str = Depends(require_admin_session)):
    if not get_connector(connector_id):
        raise HTTPException(status_code=404, detail="Conector não encontrado")
    delete_connector(connector_id)
    log_admin_action(admin, 'delete_connector', 'connector', connector_id)
    return {"message": "Conector removido"}

# ── Admin: Bindings ─────────────────────────────────────────────────────────

@router.get("/admin/api/clients/{client_id}/connectors/{connector_id}/bindings", tags=["Admin"])
async def list_bindings_route(
    client_id: int, connector_id: int, _: str = Depends(require_admin_session)
):
    return get_bindings(connector_id, client_id)

@router.post("/admin/api/clients/{client_id}/connectors/{connector_id}/bindings", tags=["Admin"])
async def create_binding_route(
    client_id: int, connector_id: int,
    body: BindingCreateDTO,
    admin: str = Depends(require_admin_session),
):
    b = upsert_binding(
        connector_id, client_id, body.query_id, body.route,
        params=body.params, status='active', instance_name=body.instance_name,
    )
    log_admin_action(admin, 'create_binding', 'connector_binding', connector_id,
                     f"client={client_id} query={body.query_id} route={body.route}")
    return b

@router.post("/admin/api/clients/{client_id}/connectors/{connector_id}/suggest", tags=["Admin"])
async def suggest_bindings_route(
    client_id: int, connector_id: int,
    admin: str = Depends(require_admin_session),
):
    """
    Auto-suggest bindings from schema catalog.
    Saves as 'suggested' — needs approval before going active.
    """
    suggestions = await asyncio.to_thread(suggest_bindings_from_catalog, client_id, connector_id)
    if not suggestions:
        return {'suggestions': [], 'total': 0,
                'message': 'Nenhuma sugestão — capture o catálogo primeiro (POST /schema/capture)'}

    saved = []
    for s in suggestions:
        b = upsert_binding(
            connector_id, client_id, s['query_id'], s['route'],
            status='suggested', confidence=s['confidence'],
        )
        b['table'] = s['table']
        b['resource'] = s['resource']
        saved.append(b)

    log_admin_action(admin, 'suggest_bindings', 'connector', connector_id,
                     f"client={client_id} sugestoes={len(saved)}")
    return {'suggestions': saved, 'total': len(saved)}

@router.post("/admin/api/connectors/bindings/{binding_id}/approve", tags=["Admin"])
async def approve_binding(binding_id: int, admin: str = Depends(require_admin_session)):
    update_binding_status(binding_id, 'active')
    log_admin_action(admin, 'approve_binding', 'connector_binding', binding_id)
    return {"message": "Binding ativado"}

@router.post("/admin/api/connectors/bindings/{binding_id}/reject", tags=["Admin"])
async def reject_binding(binding_id: int, admin: str = Depends(require_admin_session)):
    update_binding_status(binding_id, 'disabled')
    log_admin_action(admin, 'reject_binding', 'connector_binding', binding_id)
    return {"message": "Binding desativado"}

@router.delete("/admin/api/connectors/bindings/{binding_id}", tags=["Admin"])
async def delete_binding_route(binding_id: int, admin: str = Depends(require_admin_session)):
    delete_binding(binding_id)
    log_admin_action(admin, 'delete_binding', 'connector_binding', binding_id)
    return {"message": "Binding removido"}

# ── Execute (tenant-facing proxy) ────────────────────────────────────────────

@router.post("/api/v1/connectors/{connector_id}/execute", tags=["Connectors"])
async def execute_connector(
    connector_id: int,
    request: Request,
    context: TenantContext = Depends(get_tenant_context),
):
    """
    Executa todos os bindings ativos deste conector para o cliente autenticado.
    Calls são feitas em paralelo; retorna {query_id: result}.

    O dashboard sempre chama este endpoint — não precisa saber quais rotas
    estão mapeadas nem qual arquitetura de banco o cliente usa.
    """
    bindings = get_bindings(connector_id, context.client_id, status='active')
    if not bindings:
        raise HTTPException(
            status_code=404,
            detail="Nenhum binding ativo. Crie bindings em /admin/api/clients/{id}/connectors/{id}/bindings"
        )

    api_key = request.headers.get("x-api-key", "")
    base_url = str(request.base_url).rstrip("/")

    async def _call(binding: dict):
        url = f"{base_url}{binding['route']}"
        params = binding.get('params') or {}
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(url, params=params, headers={"x-api-key": api_key})
                r.raise_for_status()
                return binding['query_id'], r.json()
        except httpx.HTTPStatusError as e:
            logger.warning("connector %s binding %s: HTTP %s", connector_id, binding['query_id'], e.response.status_code)
            return binding['query_id'], {"error": e.response.status_code, "detail": e.response.text[:200]}
        except Exception as e:
            logger.exception("connector %s binding %s failed", connector_id, binding['query_id'])
            return binding['query_id'], {"error": 500, "detail": str(e)}

    # ponytail: no TTL cache — add when profiling shows repeated connector calls within seconds
    results = await asyncio.gather(*[_call(b) for b in bindings])
    return {qid: data for qid, data in results}
