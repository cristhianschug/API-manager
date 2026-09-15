"""SQLAlchemy models for Anexar ERP tables"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.sql import func
from database import Base

class Tbcliente(Base):
    """Cliente table"""
    __tablename__ = "TBCLIENTE"

    idcliente = Column(Integer, primary_key=True, index=True, name="IDCLIENTE")
    nomecliente = Column(String(150), nullable=False, name="NOMECLIENTE")
    cpfcnpj = Column(String(20), nullable=True, name="CPFCNPJ")
    email = Column(String(150), nullable=True, name="EMAIL")
    telefone = Column(String(20), nullable=True, name="TELEFONE")
    idtbempresa = Column(Integer, nullable=False, name="IDTBEMPRESA")
    limitecredito = Column(Float, default=0.0, name="LIMITECREDITO")
    saldodevedor = Column(Float, default=0.0, name="SALDODEVEDOR")
    ativo = Column(Boolean, default=True, name="ATIVO")
    datacadastro = Column(DateTime, server_default=func.now(), name="DATACADASTRO")

class Tbproduto(Base):
    """Produto table"""
    __tablename__ = "TBPRODUTO"

    idproduto = Column(Integer, primary_key=True, index=True, name="IDPRODUTO")
    codproduto = Column(String(30), unique=True, nullable=False, name="CODPRODUTO")
    nomeproduto = Column(String(200), nullable=False, name="NOMEPRODUTO")
    idtbcategoria = Column(Integer, nullable=True, name="IDTBCATEGORIA")
    preco = Column(Float, default=0.0, name="PRECO")
    custounit = Column(Float, default=0.0, name="CUSTOUNIT")
    idtbempresa = Column(Integer, nullable=False, name="IDTBEMPRESA")
    ativo = Column(Boolean, default=True, name="ATIVO")
    datacadastro = Column(DateTime, server_default=func.now(), name="DATACADASTRO")

class Tbpedido(Base):
    """Pedido (Order) table"""
    __tablename__ = "TBPEDIDO"

    idpedido = Column(Integer, primary_key=True, index=True, name="IDPEDIDO")
    numpedido = Column(String(20), unique=True, nullable=False, name="NUMPEDIDO")
    idcliente = Column(Integer, nullable=False, index=True, name="IDCLIENTE")
    idtbempresa = Column(Integer, nullable=False, name="IDTBEMPRESA")
    datapedido = Column(DateTime, server_default=func.now(), name="DATAPEDIDO")
    valortotal = Column(Float, default=0.0, name="VALORTOTAL")
    status = Column(String(20), default="ABERTO", name="STATUS")
    observacao = Column(Text, nullable=True, name="OBSERVACAO")

class Tbparcelas(Base):
    """Parcelas (Installments) table"""
    __tablename__ = "TBPARCELAS"

    idparcela = Column(Integer, primary_key=True, index=True, name="IDPARCELA")
    idpedido = Column(Integer, nullable=False, index=True, name="IDPEDIDO")
    idtbempresa = Column(Integer, nullable=False, name="IDTBEMPRESA")
    numero = Column(Integer, nullable=False, name="NUMERO")
    valor = Column(Float, default=0.0, name="VALOR")
    vencimento = Column(DateTime, nullable=True, name="VENCIMENTO")
    status = Column(String(20), default="ABERTA", name="STATUS")
    datapagamento = Column(DateTime, nullable=True, name="DATAPAGAMENTO")

class Tbfornecedor(Base):
    """Fornecedor (Supplier) table"""
    __tablename__ = "TBFORNECEDOR"

    idfornecedor = Column(Integer, primary_key=True, index=True, name="IDFORNECEDOR")
    nomefornecedor = Column(String(150), nullable=False, name="NOMEFORNECEDOR")
    cpfcnpj = Column(String(20), nullable=True, name="CPFCNPJ")
    email = Column(String(150), nullable=True, name="EMAIL")
    telefone = Column(String(20), nullable=True, name="TELEFONE")
    idtbempresa = Column(Integer, nullable=False, name="IDTBEMPRESA")
    ativo = Column(Boolean, default=True, name="ATIVO")
    datacadastro = Column(DateTime, server_default=func.now(), name="DATACADASTRO")
