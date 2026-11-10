# 03 — Agente, prompt e traço: tarefas

Cada tarefa só é marcada quando os testes citados passam.

## Antes do portão 3

- [ ] T1. Ollama no Compose de pé com `llama3.1:8b` e `llama3.2:3b`; confirmar o formato real de
      `/api/chat` com ferramentas (seção 3 do design) e ajustar o design se diferir

## Portão 3 — testes (vermelho)

- [x] T2. `pyproject.toml`: marcador `ollama` fora da execução padrão
- [x] T3. Esqueletos de `prompts.py`, `traco.py`, `agente.py`
- [x] T4. `tests/test_prompts.py`, `tests/test_traco.py`, `tests/test_agente.py`
- [x] T5. Rodar `pytest`: novos falham; os 216 anteriores continuam verdes — 10/11/2026: 58 falham (54 `NotImplementedError`, 4 asserções sobre o esqueleto vazio); passam os 216 anteriores e 2 novos que o esqueleto já satisfaz (`TIPOS_PASSO`, prompt sem ICAO)

## Portão 4 — implementação (verde)

- [x] T6. `prompts.py` — A-12
- [x] T7. `traco.py` — A-13
- [x] T8. `ClienteOllama` — A-06, A-11
- [x] T9. Loop, `_executar`, veredito geral e verificação — A-01 a A-10
- [x] T10. `pytest` todo verde

## Portão 5 — fechamento

- [ ] T11. Teste `ollama` com o modelo real; medir tempo por pergunta com `llama3.1:8b` e `llama3.2:3b`
- [ ] T12. Rodar à mão os 3 exemplos da demo (VMC, IMC/recusa, Miami) e guardar os traços
- [ ] T13. Matriz de rastreabilidade e commit
