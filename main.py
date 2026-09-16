"""FastAPI main application - ERP Anexar v2.0 (Multi-tenant with API Keys)"""
import os
import asyncio
import logging
import logging.config
from dotenv import load_dotenv
load_dotenv('.env.local')  # must run before any local import that reads os.environ

logging.config.dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            'format': '%(asctime)s %(levelname)s %(name)s %(message)s',
            'datefmt': '%Y-%m-%dT%H:%M:%S',
        },
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'json'},
    },
    'root': {'level': os.getenv('LOG_LEVEL', 'INFO'), 'handlers': ['console']},
})
logger = logging.getLogger(__name__)

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pathlib import Path
import firebirdsql

from repository import (
    list_clientes, get_cliente, list_produtos, get_produto,
    list_pedidos, get_pedido, list_fornecedores, get_fornecedor,
    list_parcelas, get_parcela
)
from schemas import (
    ClienteListDTO, ClienteDetailDTO, ClienteCreateDTO,
    ProdutoListDTO, ProdutoDetailDTO,
    PedidoListDTO, PedidoDetailDTO,
    ParcelaListDTO, ParcelaDetailDTO,
    FornecedorListDTO, FornecedorDetailDTO, FornecedorCreateDTO,
    HealthDTO
)
from tenant_auth import get_tenant_context, require_scope, TenantContext
from platform_repository import get_client_by_slug, get_client_all_scopes, get_request_metrics
from request_logging import RequestLoggingMiddleware
from admin_routes import router as admin_router
from ai_routes import router as ai_router
from platform_db import init_platform_db

# Initialize platform database on startup
try:
    init_platform_db()
except Exception as e:
    logger.warning("Platform DB init: %s", e)

app = FastAPI(
    title=os.getenv('API_TITLE', 'Anexar ERP API'),
    version=os.getenv('API_VERSION', '2.0.0'),
    description='Multi-tenant API para ERP Anexar (Real Firebird)',
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# ============ STATIC PAGES (BEFORE ROUTER) ============

@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """Serve dashboard at root"""
    dashboard_path = Path(__file__).parent / "dashboard.html"
    if dashboard_path.exists():
        return FileResponse(dashboard_path, media_type="text/html")
    return {"message": "Dashboard not found"}

@app.get("/admin", include_in_schema=False)
async def serve_admin_panel():
    """Serve admin dashboard at /admin"""
    admin_path = Path(__file__).parent / "admin_dashboard.html"
    if admin_path.exists():
        return FileResponse(admin_path, media_type="text/html")
    return {"message": "Admin dashboard not found"}

# Include admin routes (API endpoints, not static pages)
app.include_router(admin_router)

# Include AI routes
app.include_router(ai_router)

# resource slug → path prefix (used to filter OpenAPI spec per client)
_RESOURCE_PATH = {
    'clientes':    '/api/v1/clientes',
    'produtos':    '/api/v1/produtos',
    'pedidos':     '/api/v1/pedidos',
    'parcelas':    '/api/v1/parcelas',
    'fornecedores': '/api/v1/fornecedores',
}

@app.get("/api/v1/openapi/{client_slug}", include_in_schema=False)
async def client_openapi(client_slug: str):
    """Filtered OpenAPI spec for a specific client based on their active scopes"""
    client = get_client_by_slug(client_slug)
    if not client or client['status'] != 'active':
        raise HTTPException(status_code=404, detail="Client not found")

    scopes = get_client_all_scopes(client['id'])
    spec = dict(app.openapi())
    spec['info'] = {**spec['info'], 'title': f"{client['name']} — API Docs"}

    filtered_paths = {}
    for path, methods in spec.get('paths', {}).items():
        if path == '/api/v1/health':
            filtered_paths[path] = methods
            continue
        matched = False
        for resource, prefix in _RESOURCE_PATH.items():
            if path == prefix or path.startswith(prefix + '/'):
                perms = scopes.get(resource, {})
                allowed = {
                    m: op for m, op in methods.items()
                    if (m.upper() in ('GET', 'HEAD') and perms.get('read'))
                    or (m.upper() in ('POST', 'PUT', 'PATCH', 'DELETE') and perms.get('write'))
                }
                if allowed:
                    filtered_paths[path] = allowed
                matched = True
                break
        # Non-resource paths (e.g. /api/v1/ai/*) are excluded from client docs

    spec['paths'] = filtered_paths
    return JSONResponse(spec)


@app.get("/docs/{client_slug}", include_in_schema=False)
async def client_docs(client_slug: str):
    """ReDoc documentation page filtered to a client's permissions"""
    client = get_client_by_slug(client_slug)
    if not client or client['status'] != 'active':
        raise HTTPException(status_code=404, detail="Client not found")

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <title>{client['name']} — Documentação da API</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
  <style>
    body {{ margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
  </style>
</head>
<body>
  <redoc spec-url="/api/v1/openapi/{client_slug}" expand-responses="200,201"></redoc>
  <script src="https://cdn.jsdelivr.net/npm/redoc/bundles/redoc.standalone.js"></script>
</body>
</html>"""
    return HTMLResponse(html)


# ============ HEALTH CHECK ============

@app.get("/api/v1/health", response_model=HealthDTO)
async def health_check():
    """Health check endpoint (no auth required)"""
    return HealthDTO(
        status="ok",
        version="2.0.0",
        database="firebird"
    )

# ============ METRICS ============

@app.get("/api/v1/metrics", include_in_schema=True)
async def request_metrics(hours: int = Query(24, ge=1, le=168)):
    """Aggregated request metrics for the last N hours (admin use — no tenant auth)"""
    try:
        return await asyncio.to_thread(get_request_metrics, hours=hours)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ CLIENTES ============

@app.get("/api/v1/clientes", response_model=list[ClienteListDTO])
async def list_clientes_route(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ativo: bool = Query(True),
    context: TenantContext = Depends(require_scope('clientes', 'read'))
):
    """List clientes"""
    try:
        results = list_clientes(context.conn, limit=limit, offset=offset, ativo=ativo)
        return [ClienteListDTO(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/clientes/{cliente_id}", response_model=ClienteDetailDTO)
async def get_cliente_route(
    cliente_id: int,
    context: TenantContext = Depends(require_scope('clientes', 'read'))
):
    """Get cliente by ID"""
    try:
        result = get_cliente(context.conn, cliente_id)
        if not result:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        return ClienteDetailDTO(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/clientes", response_model=ClienteDetailDTO, status_code=201)
async def create_cliente(
    cliente: ClienteCreateDTO,
    context: TenantContext = Depends(require_scope('clientes', 'write'))
):
    """Create novo cliente (POST)"""
    try:
        cur = context.conn.cursor()
        query = """
            INSERT INTO TBCLIENTE (RAZAOSOCIAL, NOMEFANTASIA, CNPJCPF, EMAIL,
                                   FONE1, ENDERECO, NUM, CEP, BAIRRO, STATUS, DATACAD)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            RETURNING PKCODCLI
        """
        cur.execute(query, (
            cliente.razao_social,
            cliente.nome_fantasia,
            cliente.cpf_cnpj,
            cliente.email,
            cliente.fone1,
            cliente.endereco,
            cliente.numero,
            cliente.cep,
            cliente.bairro,
        ))
        new_id = cur.fetchone()[0]
        context.conn.commit()
        cur.close()

        # Fetch created record
        result = get_cliente(context.conn, new_id)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create cliente")
        return ClienteDetailDTO(**result)
    except Exception as e:
        context.conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ============ PRODUTOS ============

@app.get("/api/v1/produtos", response_model=list[ProdutoListDTO])
async def list_produtos_route(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ativo: bool = Query(True),
    context: TenantContext = Depends(require_scope('produtos', 'read'))
):
    """List produtos"""
    try:
        results = list_produtos(context.conn, limit=limit, offset=offset, ativo=ativo)
        return [ProdutoListDTO(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/produtos/{produto_id}", response_model=ProdutoDetailDTO)
async def get_produto_route(
    produto_id: int,
    context: TenantContext = Depends(require_scope('produtos', 'read'))
):
    """Get produto by ID"""
    try:
        result = get_produto(context.conn, produto_id)
        if not result:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        return ProdutoDetailDTO(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ PEDIDOS ============

@app.get("/api/v1/pedidos", response_model=list[PedidoListDTO])
async def list_pedidos_route(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    context: TenantContext = Depends(require_scope('pedidos', 'read'))
):
    """List pedidos"""
    try:
        results = list_pedidos(context.conn, limit=limit, offset=offset)
        return [PedidoListDTO(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/pedidos/{pedido_id}", response_model=PedidoDetailDTO)
async def get_pedido_route(
    pedido_id: int,
    context: TenantContext = Depends(require_scope('pedidos', 'read'))
):
    """Get pedido by ID"""
    try:
        result = get_pedido(context.conn, pedido_id)
        if not result:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        return PedidoDetailDTO(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ PARCELAS ============

@app.get("/api/v1/parcelas", response_model=list[ParcelaListDTO])
async def list_parcelas_route(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    context: TenantContext = Depends(require_scope('parcelas', 'read'))
):
    """List parcelas abertas"""
    try:
        results = list_parcelas(context.conn, limit=limit, offset=offset)
        return [ParcelaListDTO(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/parcelas/{parcela_id}", response_model=ParcelaDetailDTO)
async def get_parcela_route(
    parcela_id: int,
    context: TenantContext = Depends(require_scope('parcelas', 'read'))
):
    """Get parcela by ID"""
    try:
        result = get_parcela(context.conn, parcela_id)
        if not result:
            raise HTTPException(status_code=404, detail="Parcela não encontrada")
        return ParcelaDetailDTO(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============ FORNECEDORES ============

@app.get("/api/v1/fornecedores", response_model=list[FornecedorListDTO])
async def list_fornecedores_route(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ativo: bool = Query(True),
    context: TenantContext = Depends(require_scope('fornecedores', 'read'))
):
    """List fornecedores"""
    try:
        results = list_fornecedores(context.conn, limit=limit, offset=offset, ativo=ativo)
        return [FornecedorListDTO(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/fornecedores/{fornecedor_id}", response_model=FornecedorDetailDTO)
async def get_fornecedor_route(
    fornecedor_id: int,
    context: TenantContext = Depends(require_scope('fornecedores', 'read'))
):
    """Get fornecedor by ID"""
    try:
        result = get_fornecedor(context.conn, fornecedor_id)
        if not result:
            raise HTTPException(status_code=404, detail="Fornecedor não encontrado")
        return FornecedorDetailDTO(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/fornecedores", response_model=FornecedorDetailDTO, status_code=201)
async def create_fornecedor(
    fornecedor: FornecedorCreateDTO,
    context: TenantContext = Depends(require_scope('fornecedores', 'write'))
):
    """Create novo fornecedor (POST)"""
    try:
        cur = context.conn.cursor()
        query = """
            INSERT INTO TBFORNECEDOR (RAZAOSOCIAL, NOMEFANTASIA, CNPJCPF, EMAIL,
                                      FONE1, ENDERECO, CEP, BAIRRO, STATUS, DATACAD)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
            RETURNING PKCODFORN
        """
        cur.execute(query, (
            fornecedor.razao_social,
            fornecedor.nome_fantasia,
            fornecedor.cpf_cnpj,
            fornecedor.email,
            fornecedor.fone1,
            fornecedor.endereco,
            fornecedor.cep,
            fornecedor.bairro,
        ))
        new_id = cur.fetchone()[0]
        context.conn.commit()
        cur.close()

        result = get_fornecedor(context.conn, new_id)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create fornecedor")
        return FornecedorDetailDTO(**result)
    except Exception as e:
        context.conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail,
            "code": exc.status_code
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
