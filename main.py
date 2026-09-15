"""FastAPI main application - ERP Anexar v2.0 (Real Firebird)"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
import os
from dotenv import load_dotenv
import firebirdsql

from database import get_db
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

load_dotenv('.env.local')

app = FastAPI(
    title=os.getenv('API_TITLE', 'Anexar ERP API'),
    version=os.getenv('API_VERSION', '2.0.0'),
    description='Read-Only API para ERP Anexar (Real Firebird)',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# ============ HEALTH CHECK ============

@app.get("/api/v1/health", response_model=HealthDTO)
async def health_check(conn: firebirdsql.Connection = Depends(get_db)):
    """Health check endpoint"""
    try:
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_TIMESTAMP FROM RDB$DATABASE")
        cur.fetchone()
        cur.close()
        return HealthDTO(
            status="ok",
            version="2.0.0",
            database="firebird"
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

# ============ CLIENTES ============

@app.get("/api/v1/clientes", response_model=list[ClienteListDTO])
async def list_clientes_route(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ativo: bool = Query(True),
    conn: firebirdsql.Connection = Depends(get_db)
):
    """List clientes"""
    try:
        results = list_clientes(conn, limit=limit, offset=offset, ativo=ativo)
        return [ClienteListDTO(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/clientes/{cliente_id}", response_model=ClienteDetailDTO)
async def get_cliente_route(
    cliente_id: int,
    conn: firebirdsql.Connection = Depends(get_db)
):
    """Get cliente by ID"""
    try:
        result = get_cliente(conn, cliente_id)
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
    conn: firebirdsql.Connection = Depends(get_db)
):
    """Create novo cliente (POST)"""
    try:
        cur = conn.cursor()
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
        conn.commit()
        cur.close()

        # Fetch created record
        result = get_cliente(conn, new_id)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create cliente")
        return ClienteDetailDTO(**result)
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=str(e))

# ============ PRODUTOS ============

@app.get("/api/v1/produtos", response_model=list[ProdutoListDTO])
async def list_produtos_route(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ativo: bool = Query(True),
    conn: firebirdsql.Connection = Depends(get_db)
):
    """List produtos"""
    try:
        results = list_produtos(conn, limit=limit, offset=offset, ativo=ativo)
        return [ProdutoListDTO(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/produtos/{produto_id}", response_model=ProdutoDetailDTO)
async def get_produto_route(
    produto_id: int,
    conn: firebirdsql.Connection = Depends(get_db)
):
    """Get produto by ID"""
    try:
        result = get_produto(conn, produto_id)
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
    conn: firebirdsql.Connection = Depends(get_db)
):
    """List pedidos"""
    try:
        results = list_pedidos(conn, limit=limit, offset=offset)
        return [PedidoListDTO(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/pedidos/{pedido_id}", response_model=PedidoDetailDTO)
async def get_pedido_route(
    pedido_id: int,
    conn: firebirdsql.Connection = Depends(get_db)
):
    """Get pedido by ID"""
    try:
        result = get_pedido(conn, pedido_id)
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
    conn: firebirdsql.Connection = Depends(get_db)
):
    """List parcelas abertas"""
    try:
        results = list_parcelas(conn, limit=limit, offset=offset)
        return [ParcelaListDTO(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/parcelas/{parcela_id}", response_model=ParcelaDetailDTO)
async def get_parcela_route(
    parcela_id: int,
    conn: firebirdsql.Connection = Depends(get_db)
):
    """Get parcela by ID"""
    try:
        result = get_parcela(conn, parcela_id)
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
    conn: firebirdsql.Connection = Depends(get_db)
):
    """List fornecedores"""
    try:
        results = list_fornecedores(conn, limit=limit, offset=offset, ativo=ativo)
        return [FornecedorListDTO(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/fornecedores/{fornecedor_id}", response_model=FornecedorDetailDTO)
async def get_fornecedor_route(
    fornecedor_id: int,
    conn: firebirdsql.Connection = Depends(get_db)
):
    """Get fornecedor by ID"""
    try:
        result = get_fornecedor(conn, fornecedor_id)
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
    conn: firebirdsql.Connection = Depends(get_db)
):
    """Create novo fornecedor (POST)"""
    try:
        cur = conn.cursor()
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
        conn.commit()
        cur.close()

        result = get_fornecedor(conn, new_id)
        if not result:
            raise HTTPException(status_code=500, detail="Failed to create fornecedor")
        return FornecedorDetailDTO(**result)
    except Exception as e:
        conn.rollback()
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
