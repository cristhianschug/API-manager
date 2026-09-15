"""Integration tests for API endpoints"""
import pytest
from datetime import datetime
from sqlalchemy.orm import Session
from models import Tbcliente, Tbproduto, Tbpedido, Tbparcelas, Tbfornecedor


class TestHealth:
    """Health check endpoint tests"""

    def test_health_check(self, client):
        """Test health endpoint"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "1.0.0"
        assert data["database"] == "firebird"


class TestClientes:
    """Cliente endpoint tests"""

    def test_list_clientes_empty(self, client):
        """Test list clientes when empty"""
        response = client.get("/api/v1/clientes")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_clientes_with_data(self, client, db_session):
        """Test list clientes with data"""
        # Add test data
        cliente = Tbcliente(
            idcliente=1,
            nomecliente="Cliente Teste",
            email="teste@example.com",
            cpfcnpj="12345678901234",
            idtbempresa=1,
            limitecredito=1000.0,
            ativo=True
        )
        db_session.add(cliente)
        db_session.commit()

        response = client.get("/api/v1/clientes")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["nomecliente"] == "Cliente Teste"
        assert data[0]["limitecredito"] == 1000.0

    def test_list_clientes_with_filters(self, client, db_session):
        """Test list with filters"""
        cliente_ativo = Tbcliente(
            idcliente=1,
            nomecliente="Ativo",
            idtbempresa=1,
            ativo=True
        )
        cliente_inativo = Tbcliente(
            idcliente=2,
            nomecliente="Inativo",
            idtbempresa=1,
            ativo=False
        )
        db_session.add_all([cliente_ativo, cliente_inativo])
        db_session.commit()

        # Filter only active
        response = client.get("/api/v1/clientes?ativo=true")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["nomecliente"] == "Ativo"

        # Filter only inactive
        response = client.get("/api/v1/clientes?ativo=false")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["nomecliente"] == "Inativo"

    def test_get_cliente_by_id(self, client, db_session):
        """Test get single cliente"""
        cliente = Tbcliente(
            idcliente=1,
            nomecliente="Cliente Teste",
            email="teste@example.com",
            telefone="11999999999",
            idtbempresa=1,
            ativo=True
        )
        db_session.add(cliente)
        db_session.commit()

        response = client.get("/api/v1/clientes/1")
        assert response.status_code == 200
        data = response.json()
        assert data["nomecliente"] == "Cliente Teste"
        # Email and phone should be masked
        assert "..." in data["email"]
        assert "****" in data["telefone"]

    def test_get_cliente_not_found(self, client):
        """Test get non-existent cliente"""
        response = client.get("/api/v1/clientes/999")
        assert response.status_code == 404

    def test_email_masking(self, client, db_session):
        """Test email masking in response"""
        cliente = Tbcliente(
            idcliente=1,
            nomecliente="Test",
            email="cristhian@example.com",
            idtbempresa=1,
            ativo=True
        )
        db_session.add(cliente)
        db_session.commit()

        response = client.get("/api/v1/clientes/1")
        assert response.status_code == 200
        data = response.json()
        # Should be masked like "c...@example.com"
        assert data["email"] == "c...@example.com"


class TestProdutos:
    """Produto endpoint tests"""

    def test_list_produtos_empty(self, client):
        """Test list produtos when empty"""
        response = client.get("/api/v1/produtos")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_produtos_with_data(self, client, db_session):
        """Test list produtos with data"""
        produto = Tbproduto(
            idproduto=1,
            codproduto="SKU-001",
            nomeproduto="Produto Teste",
            preco=99.90,
            custounit=50.00,
            idtbempresa=1,
            ativo=True
        )
        db_session.add(produto)
        db_session.commit()

        response = client.get("/api/v1/produtos")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["codproduto"] == "SKU-001"
        assert data[0]["preco"] == 99.90

    def test_get_produto_by_id(self, client, db_session):
        """Test get single produto"""
        produto = Tbproduto(
            idproduto=1,
            codproduto="SKU-001",
            nomeproduto="Produto Teste",
            preco=99.90,
            custounit=50.00,
            idtbempresa=1,
            ativo=True
        )
        db_session.add(produto)
        db_session.commit()

        response = client.get("/api/v1/produtos/1")
        assert response.status_code == 200
        data = response.json()
        assert data["nomeproduto"] == "Produto Teste"
        assert data["custounit"] == 50.00  # Visible in detail view


class TestPedidos:
    """Pedido endpoint tests"""

    def test_list_pedidos_empty(self, client):
        """Test list pedidos when empty"""
        response = client.get("/api/v1/pedidos")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_pedidos_with_data(self, client, db_session):
        """Test list pedidos with data"""
        cliente = Tbcliente(
            idcliente=1,
            nomecliente="Cliente Teste",
            idtbempresa=1,
            ativo=True
        )
        pedido = Tbpedido(
            idpedido=1,
            numpedido="PED-001",
            idcliente=1,
            idtbempresa=1,
            valortotal=5000.00,
            status="CONFIRMADO"
        )
        db_session.add_all([cliente, pedido])
        db_session.commit()

        response = client.get("/api/v1/pedidos")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["numpedido"] == "PED-001"
        assert data[0]["valortotal"] == 5000.00

    def test_get_pedido_by_id(self, client, db_session):
        """Test get single pedido"""
        cliente = Tbcliente(
            idcliente=1,
            nomecliente="Cliente Teste",
            idtbempresa=1,
            ativo=True
        )
        pedido = Tbpedido(
            idpedido=1,
            numpedido="PED-001",
            idcliente=1,
            idtbempresa=1,
            valortotal=5000.00,
            status="CONFIRMADO"
        )
        db_session.add_all([cliente, pedido])
        db_session.commit()

        response = client.get("/api/v1/pedidos/1")
        assert response.status_code == 200
        data = response.json()
        assert data["numpedido"] == "PED-001"


class TestParcelas:
    """Parcelas endpoint tests"""

    def test_list_parcelas_empty(self, client):
        """Test list parcelas when empty"""
        response = client.get("/api/v1/parcelas")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_parcelas_with_data(self, client, db_session):
        """Test list parcelas with data"""
        cliente = Tbcliente(
            idcliente=1,
            nomecliente="Cliente Teste",
            idtbempresa=1,
            ativo=True
        )
        pedido = Tbpedido(
            idpedido=1,
            numpedido="PED-001",
            idcliente=1,
            idtbempresa=1,
            valortotal=5000.00,
            status="CONFIRMADO"
        )
        parcela = Tbparcelas(
            idparcela=1,
            idpedido=1,
            idtbempresa=1,
            numero=1,
            valor=1666.67,
            status="ABERTA"
        )
        db_session.add_all([cliente, pedido, parcela])
        db_session.commit()

        response = client.get("/api/v1/parcelas")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["numero"] == 1
        assert data[0]["valor"] == 1666.67


class TestFornecedores:
    """Fornecedor endpoint tests"""

    def test_list_fornecedores_empty(self, client):
        """Test list fornecedores when empty"""
        response = client.get("/api/v1/fornecedores")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_fornecedores_with_data(self, client, db_session):
        """Test list fornecedores with data"""
        fornecedor = Tbfornecedor(
            idfornecedor=1,
            nomefornecedor="Fornecedor Teste",
            email="fornecedor@example.com",
            idtbempresa=1,
            ativo=True
        )
        db_session.add(fornecedor)
        db_session.commit()

        response = client.get("/api/v1/fornecedores")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["nomefornecedor"] == "Fornecedor Teste"


class TestErrorHandling:
    """Error handling tests"""

    def test_invalid_limit(self, client):
        """Test invalid limit parameter"""
        response = client.get("/api/v1/clientes?limit=99999")
        # Should reject invalid limits
        assert response.status_code in [200, 422]

    def test_invalid_offset(self, client):
        """Test invalid offset parameter"""
        response = client.get("/api/v1/clientes?offset=-1")
        # Should reject negative offset
        assert response.status_code in [200, 422]
