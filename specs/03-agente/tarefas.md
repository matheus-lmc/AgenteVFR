# 03 — Agente, prompt e traço: tarefas

Cada tarefa só é marcada quando os testes citados passam.

## Antes do portão 3

- [ ] T1. Ollama no Compose de pé com `llama3.1:8b` e `llama3.2:3b`; confirmar o formato real de
      `/api/chat` com ferramentas (seção 3 do design) e ajustar o design se diferir

## Portão 3 — testes (vermelho)

- [ ] T2. `pyproject.toml`: marcador `ollama` fora da execução padrão
- [ ] T3. Esqueletos de `prompts.py`, `traco.py`, `agente.py`
- [ ] T4. `tests/test_prompts.py`, `tests/test_traco.py`, `tests/test_agente.py`
- [ ] T5. Rodar `pytest`: novos falham; os 216 anteriores continuam verdes

## Portão 4 — implementação (verde)

- [ ] T6. `prompts.py` — A-12
- [ ] T7. `traco.py` — A-13
- [ ] T8. `ClienteOllama` — A-06, A-11
- [ ] T9. Loop, `_executar`, veredito geral e verificação — A-01 a A-10
- [ ] T10. `pytest` todo verde

## Portão 5 — fechamento

- [ ] T11. Teste `ollama` com o modelo real; medir tempo por pergunta com `llama3.1:8b` e `llama3.2:3b`
- [ ] T12. Rodar à mão os 3 exemplos da demo (VMC, IMC/recusa, Miami) e guardar os traços
- [ ] T13. Matriz de rastreabilidade e commit
