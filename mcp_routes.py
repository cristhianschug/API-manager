"""
MCP (Model Context Protocol) server for Anexar ERP.

Exposes tenant-scoped tools over SSE transport at /mcp/sse.
Authentication: same X-API-Key header used by the REST API.
Available tools depend on the API key's scopes.

Resources:
  schema://firebird  — Firebird schema snapshot for this tenant

Tools (per scope):
  list_clientes / get_cliente
  list_produtos  / get_produto
  list_pedidos   / get_pedido
  list_parcelas  / get_parcela
  list_fornecedores / get_fornecedor
  analyze_data   — AI analysis with schema auto-injected
"""
import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Request, HTTPException
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import (
    Tool, Resource, TextContent,
    ListToolsResult, CallToolResult,
    ListResourcesResult, ReadResourceResult,
    ResourceContents, TextResourceContents,
)

from platform_repository import (
    get_api_key_by_hash, hash_api_key,
    get_client_credentials_for_connection,
    get_schema_snapshot,
)
from omniroute_client import analyze_data as _analyze_data

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["MCP"])

# ── Schema summary helper ───────────────────────────────────────────────────

def _schema_summary(snap: dict | None) -> str:
    if not snap:
        return "Nenhum catalogo capturado. Use POST /admin/api/clients/{id}/schema/capture."
    tables = [t['name'] for t in snap.get('tables', [])]
    procs  = [p['name'] for p in snap.get('procedures', [])]
    trigs  = [t['name'] for t in snap.get('triggers', [])]
    captured = snap.get('captured_at', '')
    return (
        f"Catalogo Firebird (capturado: {captured})\n"
        f"Tabelas ({len(tables)}): {', '.join(tables)}\n"
        f"Procedures ({len(procs)}): {', '.join(procs)}\n"
        f"Triggers ({len(trigs)}): {', '.join(trigs)}"
    )

# ── Tool definitions (static part) ─────────────────────────────────────────

_RESOURCE_TOOLS: dict[str, list[Tool]] = {
    "clientes": [
        Tool(name="list_clientes",
             description="Lista clientes do banco Firebird com paginacao.",
             inputSchema={"type":"object","properties":{
                 "limit":{"type":"integer","default":50,"maximum":200},
                 "offset":{"type":"integer","default":0},
                 "ativo":{"type":"boolean","default":True}}}),
        Tool(name="get_cliente",
             description="Retorna detalhes de um cliente pelo ID.",
             inputSchema={"type":"object","properties":{
                 "id":{"type":"integer"}},"required":["id"]}),
    ],
    "produtos": [
        Tool(name="list_produtos",
             description="Lista produtos do banco Firebird com paginacao.",
             inputSchema={"type":"object","properties":{
                 "limit":{"type":"integer","default":100,"maximum":500},
                 "offset":{"type":"integer","default":0},
                 "ativo":{"type":"boolean","default":True}}}),
        Tool(name="get_produto",
             description="Retorna detalhes de um produto pelo ID.",
             inputSchema={"type":"object","properties":{
                 "id":{"type":"integer"}},"required":["id"]}),
    ],
    "pedidos": [
        Tool(name="list_pedidos",
             description="Lista pedidos do banco Firebird com paginacao.",
             inputSchema={"type":"object","properties":{
                 "limit":{"type":"integer","default":50,"maximum":500},
                 "offset":{"type":"integer","default":0}}}),
        Tool(name="get_pedido",
             description="Retorna detalhes de um pedido pelo ID.",
             inputSchema={"type":"object","properties":{
                 "id":{"type":"integer"}},"required":["id"]}),
    ],
    "parcelas": [
        Tool(name="list_parcelas",
             description="Lista parcelas abertas com paginacao.",
             inputSchema={"type":"object","properties":{
                 "limit":{"type":"integer","default":100,"maximum":500},
                 "offset":{"type":"integer","default":0}}}),
        Tool(name="get_parcela",
             description="Retorna detalhes de uma parcela pelo ID.",
             inputSchema={"type":"object","properties":{
                 "id":{"type":"integer"}},"required":["id"]}),
    ],
    "fornecedores": [
        Tool(name="list_fornecedores",
             description="Lista fornecedores do banco Firebird com paginacao.",
             inputSchema={"type":"object","properties":{
                 "limit":{"type":"integer","default":100,"maximum":500},
                 "offset":{"type":"integer","default":0},
                 "ativo":{"type":"boolean","default":True}}}),
        Tool(name="get_fornecedor",
             description="Retorna detalhes de um fornecedor pelo ID.",
             inputSchema={"type":"object","properties":{
                 "id":{"type":"integer"}},"required":["id"]}),
    ],
}

_ANALYZE_TOOL = Tool(
    name="analyze_data",
    description=(
        "Analisa dados usando IA (OmniRoute). O catalogo Firebird deste cliente "
        "e injetado automaticamente como contexto — o agente nao precisa repassar o schema."
    ),
    inputSchema={"type":"object","properties":{
        "data":{"description":"Dados a analisar (objeto ou string)"},
        "query":{"type":"string","description":"Pergunta ou instrucao em portugues"},
        "max_tokens":{"type":"integer","default":400}},"required":["data","query"]},
)

_SCHEMA_TOOL = Tool(
    name="get_schema",
    description="Retorna o catalogo Firebird capturado para este cliente (tabelas, procedures, triggers).",
    inputSchema={"type":"object","properties":{}},
)

# ── SSE endpoint factory ────────────────────────────────────────────────────

def _build_mcp_server(client_id: int, scopes: dict, conn, snap: dict | None) -> Server:
    """Build a per-session MCP Server instance bound to one tenant."""
    server = Server("anexar-erp")

    # Collect allowed tools based on scopes
    allowed_tools = [_SCHEMA_TOOL, _ANALYZE_TOOL]
    for resource, tool_list in _RESOURCE_TOOLS.items():
        if resource in scopes and scopes[resource].get('read'):
            allowed_tools.extend(tool_list)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return allowed_tools

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        return [Resource(
            uri="schema://firebird",
            name="Catalogo Firebird",
            description="Schema do banco Firebird deste cliente (tabelas, procedures, triggers).",
            mimeType="text/plain",
        )]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        if uri == "schema://firebird":
            return _schema_summary(snap)
        raise ValueError(f"Resource desconhecido: {uri}")

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            result = await _dispatch_tool(name, arguments, client_id, scopes, conn, snap)
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, default=str))]
        except PermissionError as e:
            return [TextContent(type="text", text=f"Erro de permissao: {e}")]
        except Exception as e:
            logger.exception("MCP tool %s error", name)
            return [TextContent(type="text", text=f"Erro: {e}")]

    return server


async def _dispatch_tool(name: str, args: dict, client_id: int,
                         scopes: dict, conn, snap: dict | None) -> Any:
    """Route tool call to the right repository function."""
    import repository as repo

    def _check(resource: str):
        if resource not in scopes or not scopes[resource].get('read'):
            raise PermissionError(f"Sem permissao de leitura em {resource}")

    if name == "get_schema":
        return snap or {}

    if name == "analyze_data":
        schema_ctx = _schema_summary(snap)
        data_str = json.dumps(args["data"]) if isinstance(args["data"], dict) else str(args["data"])
        return await asyncio.to_thread(
            _analyze_data, data_str, args["query"], args.get("max_tokens", 400), schema_ctx
        )

    if name == "list_clientes":
        _check("clientes")
        return await asyncio.to_thread(repo.list_clientes, conn,
            limit=args.get("limit", 50), offset=args.get("offset", 0),
            ativo=args.get("ativo", True))

    if name == "get_cliente":
        _check("clientes")
        r = await asyncio.to_thread(repo.get_cliente, conn, args["id"])
        if not r: raise ValueError("Cliente nao encontrado")
        return r

    if name == "list_produtos":
        _check("produtos")
        return await asyncio.to_thread(repo.list_produtos, conn,
            limit=args.get("limit", 100), offset=args.get("offset", 0),
            ativo=args.get("ativo", True))

    if name == "get_produto":
        _check("produtos")
        r = await asyncio.to_thread(repo.get_produto, conn, args["id"])
        if not r: raise ValueError("Produto nao encontrado")
        return r

    if name == "list_pedidos":
        _check("pedidos")
        return await asyncio.to_thread(repo.list_pedidos, conn,
            limit=args.get("limit", 50), offset=args.get("offset", 0))

    if name == "get_pedido":
        _check("pedidos")
        r = await asyncio.to_thread(repo.get_pedido, conn, args["id"])
        if not r: raise ValueError("Pedido nao encontrado")
        return r

    if name == "list_parcelas":
        _check("parcelas")
        return await asyncio.to_thread(repo.list_parcelas, conn,
            limit=args.get("limit", 100), offset=args.get("offset", 0))

    if name == "get_parcela":
        _check("parcelas")
        r = await asyncio.to_thread(repo.get_parcela, conn, args["id"])
        if not r: raise ValueError("Parcela nao encontrada")
        return r

    if name == "list_fornecedores":
        _check("fornecedores")
        return await asyncio.to_thread(repo.list_fornecedores, conn,
            limit=args.get("limit", 100), offset=args.get("offset", 0),
            ativo=args.get("ativo", True))

    if name == "get_fornecedor":
        _check("fornecedores")
        r = await asyncio.to_thread(repo.get_fornecedor, conn, args["id"])
        if not r: raise ValueError("Fornecedor nao encontrado")
        return r

    raise ValueError(f"Tool desconhecida: {name}")


# ── FastAPI SSE endpoint ────────────────────────────────────────────────────

@router.get("/sse")
async def mcp_sse(request: Request):
    """
    MCP server over SSE. Authenticate with X-API-Key header.
    Connect with any MCP client (Claude Desktop, cline, etc.) pointing to:
      http://localhost:8000/mcp/sse
    """
    x_api_key = request.headers.get("x-api-key") or request.query_params.get("api_key")
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header obrigatorio")

    key_record = get_api_key_by_hash(hash_api_key(x_api_key))
    if not key_record or key_record['status'] != 'active':
        raise HTTPException(status_code=401, detail="API key invalida ou revogada")

    client_id = key_record['client_id']
    scopes    = key_record['scopes']

    creds = get_client_credentials_for_connection(client_id)
    if not creds:
        raise HTTPException(status_code=500, detail="Credenciais do cliente nao encontradas")

    import firebirdsql
    try:
        conn = await asyncio.to_thread(
            firebirdsql.connect,
            host=creds['host'], port=creds['port'], database=creds['database'],
            user=creds['user'], password=creds['password'], charset=creds['charset'],
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Banco Firebird indisponivel: {e}")

    snap = await asyncio.to_thread(get_schema_snapshot, client_id)
    server = _build_mcp_server(client_id, scopes, conn, snap)

    sse_transport = SseServerTransport("/mcp/messages")

    async def cleanup():
        try:
            conn.close()
        except Exception:
            pass

    try:
        async with sse_transport.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
    finally:
        await cleanup()


@router.post("/messages")
async def mcp_messages(request: Request):
    """SSE message post endpoint (used internally by MCP transport)."""
    # Handled by SseServerTransport internally — this route just needs to exist
    # so FastAPI registers the path; the transport processes the body directly.
    pass
