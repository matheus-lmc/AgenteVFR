# 02 — Ferramentas: tarefas

Cada tarefa só é marcada quando os testes citados passam.

## Portão 3 — testes (vermelho)

- [ ] T1. `requirements.txt` com `httpx` fixado; instalar na `.venv`
- [ ] T2. Gravar fixtures da API real em `tests/fixtures/awc/` (METAR SBGR, METAR SBGR `hours=3`, TAF SBGR, 400)
- [ ] T3. `pyproject.toml`: marcador `rede` fora da execução padrão
- [ ] T4. `app/ferramentas.py` só com assinaturas e constantes
- [ ] T5. `tests/test_ferramentas.py` (F-01 a F-09)
- [ ] T6. Rodar `pytest` e registrar que os testes novos falham e os 155 do harness continuam verdes

## Portão 4 — implementação (verde)

- [ ] T7. `ResultadoBusca` e validações sem rede — F-01, F-02, F-08
- [ ] T8. Requisição, tentativas e tratamento de respostas — F-03 a F-06
- [ ] T9. Cache com relógio injetável e regra dos 55 min — F-07
- [ ] T10. Atalhos de módulo — F-09
- [ ] T11. `pytest` todo verde (harness + ferramentas)

## Portão 5 — fechamento

- [ ] T12. Rodar o teste `rede` contra a API real
- [ ] T13. Matriz de rastreabilidade em `specs/README.md`
- [ ] T14. Commit
