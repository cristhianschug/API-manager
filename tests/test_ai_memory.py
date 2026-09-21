"""
Retroalimentação do chat: captura automática de lições, validação humana,
e uso do conhecimento validado no planejamento e na narrativa.
"""
import os
import json
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("PLATFORM_ENCRYPTION_KEY", "cnQhmA9c0dVdmLTzSJz0nEExrH3fR4GHT3E64TGFfRs=")

import ai_router
from platform_repository import add_ai_memory, list_ai_memory, update_ai_memory, find_ai_lesson


@pytest.fixture
def db(tmp_path, monkeypatch):
    import platform_db
    monkeypatch.setattr(platform_db, "PLATFORM_DB_PATH", tmp_path / "platform.db")
    monkeypatch.setenv("ADMIN_BOOTSTRAP_PASSWORD", "x")
    platform_db.init_platform_db()
    ai_router._cache.clear()
    from platform_repository import create_client
    with patch("platform_repository.encrypt_password", return_value="enc"):
        return create_client("Acme", "acme", "h", 3050, "/db", "u", "p")["id"]


CATALOG = [{"path": "/api/v1/data/tbpedido", "table": "TBPEDIDO", "purpose": "", "columns": {"VALORTOTAL": "numeric"}}]
PLAN_OK = '{"calls":[{"path":"/api/v1/data/tbpedido","params":{"agg":"sum:VALORTOTAL"}}]}'


async def _ask(client_id, question, history=None, fetch=None, plans=None, narrative="resposta"):
    calls = list(plans or [PLAN_OK]) + [narrative]
    with patch("ai_router.build_catalog", return_value=CATALOG), \
         patch("ai_router.query_ai", side_effect=calls) as qa, \
         patch("ai_router.fetch_endpoint", side_effect=fetch or (lambda *a, **k: {"mode": "group", "data": [{"VALOR": 10}]})):
        res = await ai_router.ask(MagicMock(), 1, client_id, {"*": {"read": True}}, question, history or [])
    return res, qa


# ── Captura automática ─────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_resposta_boa_vira_candidato_pendente(db):
    res, _ = await _ask(db, "Qual o faturamento total?")
    mem = list_ai_memory(db, kind='lesson')
    assert len(mem) == 1
    assert mem[0]['status'] == 'pending', "nada entra no prompt sem validação humana"
    assert mem[0]['plan'] == [{"path": "/api/v1/data/tbpedido", "params": {"agg": "sum:VALORTOTAL"}}]
    assert res['memory'] == {"id": mem[0]['id'], "status": "pending"}


@pytest.mark.anyio
async def test_mesma_pergunta_nao_duplica_e_conta_uso(db):
    await _ask(db, "Qual o faturamento total?")
    await _ask(db, "qual o FATURAMENTO total???")   # mesma pergunta normalizada
    mem = list_ai_memory(db, kind='lesson')
    assert len(mem) == 1 and mem[0]['uses'] == 1


@pytest.mark.anyio
async def test_plano_corrigido_pelo_reparo_e_marcado_como_tal(db):
    from fastapi import HTTPException
    bad = '{"calls":[{"path":"/api/v1/data/tbpedido","params":{"agg":"sum:NAOEXISTE"}}]}'
    def fetch(conn, cid, scopes, path, params):
        if "NAOEXISTE" in json.dumps(params):
            raise HTTPException(400, "Coluna 'NAOEXISTE' não existe")
        return {"mode": "group", "data": [{"VALOR": 10}]}
    await _ask(db, "faturamento do ano", fetch=fetch, plans=[bad, PLAN_OK])
    mem = list_ai_memory(db, kind='lesson')[0]
    assert mem['source'] == 'repair'
    assert mem['plan'][0]['params'] == {"agg": "sum:VALORTOTAL"}, "guarda o plano que funcionou"


@pytest.mark.anyio
async def test_falha_ao_gravar_memoria_nao_derruba_a_resposta(db):
    with patch("ai_router.add_ai_memory", side_effect=RuntimeError("disco cheio")):
        res, _ = await _ask(db, "faturamento")
    assert res['answer'] == "resposta" and res['memory'] == {}


# ── Uso do que foi validado ────────────────────────────────────────────────

@pytest.mark.anyio
async def test_pendente_nao_entra_no_prompt_validado_entra(db):
    await _ask(db, "Qual o faturamento total?")
    lesson = list_ai_memory(db, kind='lesson')[0]

    _, qa = await _ask(db, "Qual o faturamento total?")
    assert "Exemplos validados" not in qa.call_args_list[0].args[0], "pendente não guia o planejador"

    update_ai_memory(lesson['id'], status='validated')
    _, qa = await _ask(db, "Qual o faturamento total?")
    prompt = qa.call_args_list[0].args[0]
    assert "Exemplos validados" in prompt and "sum:VALORTOTAL" in prompt


@pytest.mark.anyio
async def test_instrucao_validada_vai_para_planejador_e_narrador(db):
    add_ai_memory(db, 'instruction', content="Faturamento é a soma de VALORTOTAL em TBPEDIDO.",
                  status='validated', created_by='admin')
    _, qa = await _ask(db, "faturamento de 2026")
    planner, narrator = qa.call_args_list[0].args[0], qa.call_args_list[1].args[0]
    assert "Regras deste cliente" in planner and "VALORTOTAL em TBPEDIDO" in planner
    assert "Regras deste cliente" in narrator, "regras de estilo também valem na resposta"


@pytest.mark.anyio
async def test_licao_de_outro_assunto_nao_e_recuperada(db):
    add_ai_memory(db, 'lesson', question="quantos clientes?", terms=ai_router.question_key("quantos clientes?"),
                  plan=[{"path": "/api/v1/data/tbcliente", "params": {"count": True}}], status='validated')
    _, qa = await _ask(db, "faturamento do mês")
    assert "Exemplos validados" not in qa.call_args_list[0].args[0], "sem sobreposição de termos, não injeta"


@pytest.mark.anyio
async def test_licao_usada_tem_uso_contabilizado(db):
    m = add_ai_memory(db, 'lesson', question="faturamento total", terms=ai_router.question_key("faturamento total"),
                      plan=[{"path": "/api/v1/data/tbpedido", "params": {"agg": "sum:VALORTOTAL"}}], status='validated')
    await _ask(db, "faturamento total do ano passado")
    assert list_ai_memory(db, kind='lesson')[0]['uses'] >= 1


def test_tabela_citada_em_instrucao_entra_no_catalogo_mesmo_sem_casar_termos():
    big = [{"path": f"/api/v1/data/t{i}", "table": f"T{i}", "purpose": "", "columns": {}} for i in range(100)]
    big.append({"path": "/api/v1/data/tbfat", "table": "TBFAT", "purpose": "", "columns": {}})
    instr = [{"kind": "instruction", "content": "Use a tabela TBFAT para faturamento."}]
    sel = ai_router.select_catalog("faturamento", [], big, limit=5, pinned=ai_router._memory_tables(instr, []))
    assert "/api/v1/data/tbfat" in [c['path'] for c in sel]


def test_question_key_normaliza_e_ignora_ruido():
    k = ai_router.question_key
    assert k("Quantos clientes temos cadastrados?") == k("quantos CLIENTES cadastrados")
    assert k("faturamento") != k("clientes")


# ── Repositório ────────────────────────────────────────────────────────────

def test_ciclo_de_vida_da_memoria(db):
    m = add_ai_memory(db, 'instruction', content="regra", status='pending', created_by='admin')
    assert find_ai_lesson(db, 'x') is None
    assert update_ai_memory(m['id'], status='validated')['status'] == 'validated'
    assert update_ai_memory(m['id'], content="regra nova")['content'] == "regra nova"
    assert [x['id'] for x in list_ai_memory(db, status='validated')] == [m['id']]
    from platform_repository import delete_ai_memory
    assert delete_ai_memory(m['id']) is True and list_ai_memory(db) == []
