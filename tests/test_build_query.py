"""
build_query é a fronteira de segurança dos endpoints dinâmicos: só identificadores do snapshot,
valores sempre por bind param. Função pura — sem banco.
"""
import pytest
from fastapi import HTTPException
from dynamic_router import build_query

COLS = {"PKCODCLI", "RAZAOSOCIAL", "STATUS", "DATACAD", "VALOR"}


def test_lista_padrao():
    sql, params, mode = build_query("TBCLIENTE", COLS)
    assert sql == "SELECT FIRST 50 SKIP 0 * FROM TBCLIENTE" and params == [] and mode == 'list'


def test_count_com_filtros_usa_bind_params():
    sql, params, mode = build_query("TBCLIENTE", COLS, count=True, filters=["STATUS:eq:1", "DATACAD:gte:2026-01-01"])
    assert sql == "SELECT COUNT(*) FROM TBCLIENTE WHERE STATUS = ? AND DATACAD >= ?"
    assert params == ["1", "2026-01-01"] and mode == 'count'


def test_valor_com_dois_pontos_e_preservado():
    _, params, _ = build_query("T", COLS, filters=["DATACAD:lt:2026-01-01 12:30:00"])
    assert params == ["2026-01-01 12:30:00"]


def test_like_envolve_com_curinga_e_ignora_caixa():
    sql, params, _ = build_query("T", COLS, filters=["RAZAOSOCIAL:like:silva"])
    assert "UPPER(RAZAOSOCIAL) LIKE UPPER(?)" in sql and params == ["%silva%"]


def test_isnull_nao_gera_parametro():
    sql, params, _ = build_query("T", COLS, filters=["DATACAD:isnull"])
    assert sql.endswith("WHERE DATACAD IS NULL") and params == []


def test_ordenacao_e_fields_e_limite_maximo():
    sql, _, _ = build_query("T", COLS, fields=["razaosocial", "DATACAD"], order_by="datacad", order="DESC", limit=9999, offset=-5)
    assert sql == "SELECT FIRST 500 SKIP 0 RAZAOSOCIAL, DATACAD FROM T ORDER BY DATACAD DESC"


def test_group_by_categoria_ordena_pelo_maior():
    sql, _, mode = build_query("T", COLS, group_by="STATUS", agg="sum:VALOR", limit=10)
    assert sql == "SELECT FIRST 10 SKIP 0 STATUS, SUM(VALOR) AS VALOR FROM T GROUP BY 1 ORDER BY 2 DESC" and mode == 'group'


def test_group_by_mes_ordem_cronologica():
    sql, _, _ = build_query("T", COLS, group_by="month:DATACAD", agg="count")
    assert "EXTRACT(YEAR FROM DATACAD) AS ANO, EXTRACT(MONTH FROM DATACAD) AS MES, COUNT(*) AS VALOR" in sql
    assert sql.endswith("GROUP BY 1, 2 ORDER BY 1, 2")


def test_agg_sem_group_devolve_total_unico():
    sql, _, mode = build_query("T", COLS, agg="sum:VALOR", filters=["STATUS:eq:1"])
    assert sql == "SELECT SUM(VALOR) AS VALOR FROM T WHERE STATUS = ?" and mode == 'group'


@pytest.mark.parametrize("kwargs", [
    {"filters": ["NAOEXISTE:eq:1"]},
    {"filters": ["STATUS:drop:1"]},
    {"filters": ["STATUS"]},
    {"filters": ["STATUS; DROP TABLE X:eq:1"]},
    {"order_by": "RAZAOSOCIAL; --"},
    {"order_by": "RDB$RELATIONS"},
    {"fields": ["*"]},
    {"fields": ["RAZAOSOCIAL, (SELECT 1 FROM RDB$DATABASE)"]},
    {"group_by": "week:DATACAD", "agg": "count"},
    {"group_by": "STATUS", "agg": "exec:VALOR"},
    {"group_by": "STATUS", "agg": "sum:SENHA"},
    {"filters": [f"STATUS:eq:{i}" for i in range(9)]},
])
def test_entradas_maliciosas_ou_invalidas_sao_400(kwargs):
    with pytest.raises(HTTPException) as e:
        build_query("TBCLIENTE", COLS, **kwargs)
    assert e.value.status_code == 400


def test_valor_malicioso_vai_como_parametro_nunca_no_sql():
    sql, params, _ = build_query("T", COLS, filters=["RAZAOSOCIAL:eq:x' OR '1'='1"])
    assert "OR" not in sql and params == ["x' OR '1'='1"]


def test_tabela_invalida():
    with pytest.raises(HTTPException):
        build_query("T; DROP", COLS)


def test_sem_snapshot_de_colunas_valida_so_formato():
    sql, _, _ = build_query("T", None, order_by="QUALQUER")
    assert sql.endswith("ORDER BY QUALQUER ASC")
    with pytest.raises(HTTPException):
        build_query("T", None, order_by="A B")
