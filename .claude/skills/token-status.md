---
name: token-status
description: Relatório completo de consumo de tokens — Anthropic (pago) e OmniRoute (gratuito)
---

Execute o script de status detalhado e apresente o resultado ao usuário.

## Passos

1. Leia o valor atual de `total_tokens` das system reminders do contexto (ex: `<total_tokens>14994000 tokens left</total_tokens>`).

2. Execute o script Python:
```bash
python "D:\API Anexar\.claude\scripts\token_status.py" full <total_tokens_restantes>
```

3. Mostre a saída completa formatada ao usuário.

4. Após o relatório, adicione uma linha de interpretação em português, por exemplo:
   - Se Anthropic > 80%: "Sessão com bastante crédito restante."
   - Se Anthropic 40–80%: "Sessão em andamento, monitore o consumo."
   - Se Anthropic < 40%: "⚠ Sessão com pouco crédito restante — considere iniciar uma nova."
   - Para OmniRoute: interprete os dados diários/semanais mostrando se está próximo do limite.

## Sobre os dados

**Anthropic (pago):**
- `total_tokens` nas system reminders mostra os tokens restantes da sessão atual
- Sessão inicia com 15.000.000 tokens
- Renovação: automática ao iniciar nova conversa

**OmniRoute (gratuito — API Anexar):**
- Gateway local em `http://localhost:20128`
- ~1.47B tokens/mês de provedores gratuitos (Groq, Mistral, Nara, LLM7, etc.)
- Renovação diária: meia-noite (varia por provedor)
- Renovação semanal: segunda-feira meia-noite
- Dados em tempo real: `/api/free-tiers/summary` (se disponível) ou estimativas

## Notas

- Se OmniRoute estiver offline, o script mostra estimativas baseadas nos valores documentados
- Os tokens OmniRoute são dos **provedores externos** (não da Anthropic)
- Tokens Anthropic são do **Claude Code** (suas conversas aqui)
- Os dois sistemas são independentes — um não afeta o outro
