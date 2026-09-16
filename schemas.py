"""Pydantic DTOs for real Firebird schema (DBANEXAR)"""
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import Optional

# ============ HEALTH ============

class HealthDTO(BaseModel):
    status: str
    version: str
    database: str
    platform_db: str

# ============ CLIENTE DTOs (TBCLIENTE) ============

class ClienteListDTO(BaseModel):
    id: int
    razao_social: str
    nome_fantasia: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    email: Optional[str] = None
    fone1: Optional[str] = None
    bairro: Optional[str] = None
    ativo: bool
    limite_venda: float = 0.0
    data_cadastro: Optional[datetime] = None

class ClienteDetailDTO(BaseModel):
    id: int
    razao_social: str
    nome_fantasia: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    email: Optional[str] = None
    fone1: Optional[str] = None
    fone2: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    cep: Optional[str] = None
    bairro: Optional[str] = None
    ativo: bool
    inscricao: Optional[str] = None
    limite_venda: float = 0.0
    limite_utilizado: float = 0.0
    data_cadastro: Optional[datetime] = None
    data_atualizacao: Optional[datetime] = None

class ClienteCreateDTO(BaseModel):
    razao_social: str = Field(..., min_length=1, max_length=80)
    nome_fantasia: Optional[str] = None
    cpf_cnpj: str = Field(..., min_length=11, max_length=18)
    email: Optional[str] = None
    fone1: Optional[str] = None
    endereco: Optional[str] = None
    numero: Optional[str] = None
    cep: Optional[str] = None
    bairro: Optional[str] = None

# ============ PRODUTO DTOs (TBPRODUTO) ============

class ProdutoListDTO(BaseModel):
    id: int
    referencia: Optional[str] = None
    nome: str
    ativo: bool
    valor_venda: float = 0.0
    custo_medio: float = 0.0
    data_cadastro: Optional[datetime] = None

class ProdutoDetailDTO(BaseModel):
    id: int
    referencia: Optional[str] = None
    nome: str
    ativo: bool
    valor_venda: float = 0.0
    custo_medio: float = 0.0
    descricao: Optional[str] = None
    codigo_barras: Optional[str] = None
    data_cadastro: Optional[datetime] = None
    data_atualizacao: Optional[datetime] = None

# ============ PEDIDO DTOs (TBPEDIDO) ============

class PedidoListDTO(BaseModel):
    id: int
    data_pedido: Optional[datetime] = None
    cliente_nome: Optional[str] = None
    valor_total: float = 0.0
    status: Optional[int] = None

class PedidoDetailDTO(BaseModel):
    id: int
    data_pedido: Optional[datetime] = None
    cliente_nome: Optional[str] = None
    valor_total: float = 0.0
    status: Optional[int] = None
    desconto_ordem: float = 0.0
    data_cadastro: Optional[datetime] = None
    data_atualizacao: Optional[datetime] = None

# ============ PARCELA DTOs (TBPARCELAS) ============

class ParcelaListDTO(BaseModel):
    id: int
    data_vencimento: Optional[datetime] = None
    valor: float = 0.0
    status: Optional[int] = None
    data_recebimento: Optional[datetime] = None

class ParcelaDetailDTO(BaseModel):
    id: int
    data_vencimento: Optional[datetime] = None
    valor: float = 0.0
    status: Optional[int] = None
    data_recebimento: Optional[datetime] = None
    data_cadastro: Optional[datetime] = None
    data_atualizacao: Optional[datetime] = None

# ============ FORNECEDOR DTOs (TBFORNECEDOR) ============

class FornecedorListDTO(BaseModel):
    id: int
    razao_social: str
    nome_fantasia: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    email: Optional[str] = None
    fone: Optional[str] = None
    ativo: bool
    data_cadastro: Optional[datetime] = None

class FornecedorDetailDTO(BaseModel):
    id: int
    razao_social: str
    nome_fantasia: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    email: Optional[str] = None
    fone1: Optional[str] = None
    fone2: Optional[str] = None
    endereco: Optional[str] = None
    cep: Optional[str] = None
    bairro: Optional[str] = None
    ativo: bool
    data_cadastro: Optional[datetime] = None
    data_atualizacao: Optional[datetime] = None

class FornecedorCreateDTO(BaseModel):
    razao_social: str = Field(..., min_length=1, max_length=80)
    nome_fantasia: Optional[str] = None
    cpf_cnpj: str = Field(..., min_length=11, max_length=18)
    email: Optional[str] = None
    fone1: Optional[str] = None
    endereco: Optional[str] = None
    cep: Optional[str] = None
    bairro: Optional[str] = None

# ============ ERROR ============

class ErrorResponseDTO(BaseModel):
    error: str
    message: str
    code: int
