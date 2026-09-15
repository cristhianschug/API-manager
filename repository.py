"""Data access layer using firebirdsql with parametrized queries"""
from decimal import Decimal
from datetime import datetime
from typing import List, Optional, Dict, Any
import firebirdsql

def mask_cpf_cnpj(value: str) -> str:
    """Mask CPF/CNPJ: 12345678901 -> 123.....901"""
    if not value:
        return value
    if len(value) > 6:
        return value[:3] + '.' + '*' * (len(value) - 6) + '.' + value[-3:]
    return value

def mask_email(value: str) -> str:
    """Mask email: name@domain -> n...@domain"""
    if not value or '@' not in value:
        return value
    parts = value.split('@')
    return parts[0][0] + '...' + '@' + parts[1]

# ============ CLIENTES ============

def list_clientes(conn: firebirdsql.Connection, limit: int = 50, offset: int = 0, ativo: Optional[bool] = True) -> List[Dict[str, Any]]:
    """List clientes with pagination"""
    cur = conn.cursor()
    status = 1 if ativo else 0
    # Firebird: FIRST/SKIP must be literals, not bind params
    query = f"""
        SELECT FIRST {limit} SKIP {offset}
            PKCODCLI, RAZAOSOCIAL, NOMEFANTASIA, CNPJCPF, EMAIL,
            FONE1, FONE2, ENDERECO, CEP, BAIRRO, STATUS,
            VALORLIMITEVENDA, LIMITEUTILIZADO, DATACAD
        FROM TBCLIENTE
        WHERE STATUS = ?
        ORDER BY RAZAOSOCIAL
    """
    cur.execute(query, (status,))
    rows = cur.fetchall()

    result = []
    for row in rows:
        result.append({
            'id': row[0],
            'razao_social': row[1],
            'nome_fantasia': row[2],
            'cpf_cnpj': mask_cpf_cnpj(row[3]) if row[3] else None,
            'email': mask_email(row[4]) if row[4] else None,
            'fone1': row[5],
            'fone2': row[6],
            'endereco': row[7],
            'cep': row[8],
            'bairro': row[9],
            'ativo': row[10] == 1,
            'limite_venda': float(row[11]) if row[11] else 0.0,
            'limite_utilizado': float(row[12]) if row[12] else 0.0,
            'data_cadastro': row[13],
        })

    cur.close()
    return result

def get_cliente(conn: firebirdsql.Connection, cliente_id: int) -> Optional[Dict[str, Any]]:
    """Get cliente by ID"""
    cur = conn.cursor()
    query = """
        SELECT PKCODCLI, RAZAOSOCIAL, NOMEFANTASIA, CNPJCPF, EMAIL,
               FONE1, FONE2, ENDERECO, NUM, CEP, BAIRRO, STATUS,
               INSCESTRG, VALORLIMITEVENDA, LIMITEUTILIZADO, DATACAD, DATAATU
        FROM TBCLIENTE
        WHERE PKCODCLI = ?
    """
    cur.execute(query, (cliente_id,))
    row = cur.fetchone()
    cur.close()

    if not row:
        return None

    return {
        'id': row[0],
        'razao_social': row[1],
        'nome_fantasia': row[2],
        'cpf_cnpj': mask_cpf_cnpj(row[3]) if row[3] else None,
        'email': mask_email(row[4]) if row[4] else None,
        'fone1': row[5],
        'fone2': row[6],
        'endereco': row[7],
        'numero': row[8],
        'cep': row[9],
        'bairro': row[10],
        'ativo': row[11] == 1,
        'inscricao': row[12],
        'limite_venda': float(row[13]) if row[13] else 0.0,
        'limite_utilizado': float(row[14]) if row[14] else 0.0,
        'data_cadastro': row[15],
        'data_atualizacao': row[16],
    }

# ============ PRODUTOS ============

def list_produtos(conn: firebirdsql.Connection, limit: int = 100, offset: int = 0, ativo: Optional[bool] = True) -> List[Dict[str, Any]]:
    """List produtos with pagination"""
    cur = conn.cursor()
    status = 1 if ativo else 0
    query = f"""
        SELECT FIRST {limit} SKIP {offset}
            PKCODPROD, REFERENCIA, NOME, STATUS, VALORVENDA, CUSTOMEDIO, DATACAD
        FROM TBPRODUTO
        WHERE STATUS = ?
        ORDER BY NOME
    """
    cur.execute(query, (status,))
    rows = cur.fetchall()

    result = []
    for row in rows:
        result.append({
            'id': row[0],
            'referencia': row[1],
            'nome': row[2],
            'ativo': row[3] == 1,
            'valor_venda': float(row[4]) if row[4] else 0.0,
            'custo_medio': float(row[5]) if row[5] else 0.0,
            'data_cadastro': row[6],
        })

    cur.close()
    return result

def get_produto(conn: firebirdsql.Connection, produto_id: int) -> Optional[Dict[str, Any]]:
    """Get produto by ID"""
    cur = conn.cursor()
    query = """
        SELECT PKCODPROD, REFERENCIA, NOME, STATUS, VALORVENDA, CUSTOMEDIO,
               DESCRICAOGERAL, DATACAD, DATAATU, CODBARRAS
        FROM TBPRODUTO
        WHERE PKCODPROD = ?
    """
    cur.execute(query, (produto_id,))
    row = cur.fetchone()
    cur.close()

    if not row:
        return None

    return {
        'id': row[0],
        'referencia': row[1],
        'nome': row[2],
        'ativo': row[3] == 1,
        'valor_venda': float(row[4]) if row[4] else 0.0,
        'custo_medio': float(row[5]) if row[5] else 0.0,
        'descricao': row[6],
        'data_cadastro': row[7],
        'data_atualizacao': row[8],
        'codigo_barras': row[9],
    }

# ============ PEDIDOS ============

def list_pedidos(conn: firebirdsql.Connection, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """List pedidos with pagination"""
    cur = conn.cursor()
    query = f"""
        SELECT FIRST {limit} SKIP {offset}
            p.PKCODPED, p.DATAPED, c.RAZAOSOCIAL, p.VALORTOTAL, p.STATUS
        FROM TBPEDIDO p
        LEFT JOIN TBCLIENTE c ON p.FKCODCLI = c.PKCODCLI
        ORDER BY p.DATAPED DESC
    """
    cur.execute(query)
    rows = cur.fetchall()

    result = []
    for row in rows:
        result.append({
            'id': row[0],
            'data_pedido': row[1],
            'cliente_nome': row[2],
            'valor_total': float(row[3]) if row[3] else 0.0,
            'status': row[4],
        })

    cur.close()
    return result

def get_pedido(conn: firebirdsql.Connection, pedido_id: int) -> Optional[Dict[str, Any]]:
    """Get pedido by ID"""
    cur = conn.cursor()
    query = """
        SELECT p.PKCODPED, p.DATAPED, c.RAZAOSOCIAL, p.VALORTOTAL, p.STATUS,
               p.DESCONTOORDEM, p.DATACAD, p.DATAATU
        FROM TBPEDIDO p
        LEFT JOIN TBCLIENTE c ON p.FKCODCLI = c.PKCODCLI
        WHERE p.PKCODPED = ?
    """
    cur.execute(query, (pedido_id,))
    row = cur.fetchone()
    cur.close()

    if not row:
        return None

    return {
        'id': row[0],
        'data_pedido': row[1],
        'cliente_nome': row[2],
        'valor_total': float(row[3]) if row[3] else 0.0,
        'status': row[4],
        'desconto_ordem': float(row[5]) if row[5] else 0.0,
        'data_cadastro': row[6],
        'data_atualizacao': row[7],
    }

# ============ FORNECEDORES ============

def list_fornecedores(conn: firebirdsql.Connection, limit: int = 100, offset: int = 0, ativo: Optional[bool] = True) -> List[Dict[str, Any]]:
    """List fornecedores with pagination"""
    cur = conn.cursor()
    status = 1 if ativo else 0
    query = f"""
        SELECT FIRST {limit} SKIP {offset}
            PKCODFORN, RAZAOSOCIAL, NOMEFANTASIA, CNPJCPF, EMAIL, FONE1, STATUS, DATACAD
        FROM TBFORNECEDOR
        WHERE STATUS = ?
        ORDER BY RAZAOSOCIAL
    """
    cur.execute(query, (status,))
    rows = cur.fetchall()

    result = []
    for row in rows:
        result.append({
            'id': row[0],
            'razao_social': row[1],
            'nome_fantasia': row[2],
            'cpf_cnpj': mask_cpf_cnpj(row[3]) if row[3] else None,
            'email': mask_email(row[4]) if row[4] else None,
            'fone': row[5],
            'ativo': row[6] == 1,
            'data_cadastro': row[7],
        })

    cur.close()
    return result

def get_fornecedor(conn: firebirdsql.Connection, fornecedor_id: int) -> Optional[Dict[str, Any]]:
    """Get fornecedor by ID"""
    cur = conn.cursor()
    query = """
        SELECT PKCODFORN, RAZAOSOCIAL, NOMEFANTASIA, CNPJCPF, EMAIL, FONE1, FONE2,
               ENDERECO, CEP, BAIRRO, STATUS, DATACAD, DATAATU
        FROM TBFORNECEDOR
        WHERE PKCODFORN = ?
    """
    cur.execute(query, (fornecedor_id,))
    row = cur.fetchone()
    cur.close()

    if not row:
        return None

    return {
        'id': row[0],
        'razao_social': row[1],
        'nome_fantasia': row[2],
        'cpf_cnpj': mask_cpf_cnpj(row[3]) if row[3] else None,
        'email': mask_email(row[4]) if row[4] else None,
        'fone1': row[5],
        'fone2': row[6],
        'endereco': row[7],
        'cep': row[8],
        'bairro': row[9],
        'ativo': row[10] == 1,
        'data_cadastro': row[11],
        'data_atualizacao': row[12],
    }

# ============ PARCELAS ============

def list_parcelas(conn: firebirdsql.Connection, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    """List parcelas with pagination"""
    cur = conn.cursor()
    query = f"""
        SELECT FIRST {limit} SKIP {offset}
            PKCODPARCELA, DATAVENC, VALOR, STATUS, DATARECEB, DATACAD
        FROM TBPARCELAS
        WHERE STATUS = 0
        ORDER BY DATAVENC
    """
    cur.execute(query)
    rows = cur.fetchall()

    result = []
    for row in rows:
        result.append({
            'id': row[0],
            'data_vencimento': row[1],
            'valor': float(row[2]) if row[2] else 0.0,
            'status': row[3],
            'data_recebimento': row[4],
            'data_cadastro': row[5],
        })

    cur.close()
    return result

def get_parcela(conn: firebirdsql.Connection, parcela_id: int) -> Optional[Dict[str, Any]]:
    """Get parcela by ID"""
    cur = conn.cursor()
    query = """
        SELECT PKCODPARCELA, DATAVENC, VALOR, STATUS, DATARECEB, DATACAD, DATAATU
        FROM TBPARCELAS
        WHERE PKCODPARCELA = ?
    """
    cur.execute(query, (parcela_id,))
    row = cur.fetchone()
    cur.close()

    if not row:
        return None

    return {
        'id': row[0],
        'data_vencimento': row[1],
        'valor': float(row[2]) if row[2] else 0.0,
        'status': row[3],
        'data_recebimento': row[4],
        'data_cadastro': row[5],
        'data_atualizacao': row[6],
    }
