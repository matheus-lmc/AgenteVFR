# 01 — Harness: tarefas

Cada tarefa só é marcada quando os testes citados passam.

## Portão 3 — testes (vermelho)

- [ ] T1. `pyproject.toml` (pythonpath), `app/__init__.py`, `app/harness.py` só com assinaturas
      (`raise NotImplementedError`) — para os testes importarem
- [ ] T2. `tests/test_harness.py`: helper `metar(texto, minutos_atras)` e `AGORA` fixo
- [ ] T3. Testes dos 10 casos obrigatórios (aceite)
- [ ] T4. Testes de H-01 a H-12 (`avaliar_metar`, `Resumo`)
- [ ] T5. Testes de H-13 (`prefiltrar_pergunta`)
- [ ] T6. Testes de H-14 e H-15 (`verificar_explicacao`, `texto_modelo`)
- [ ] T7. Rodar `pytest` e registrar que todos falham (`NotImplementedError`)

## Portão 4 — implementação (verde)

- [ ] T8. Constantes, `Veredito`, dataclasses — H-10, H-12
- [ ] T9. Normalização + cabeçalho + ordem das checagens — H-01 a H-06
- [ ] T10. Corpo: corte em RMK/TEMPO/BECMG/NOSIG, visibilidade, nuvens — H-07 a H-09
- [ ] T11. Regra VMC/IMC + motivo + resumo — H-10 a H-12
- [ ] T12. `prefiltrar_pergunta` — H-13
- [ ] T13. `verificar_explicacao` + `texto_modelo` — H-14, H-15
- [ ] T14. `pytest` todo verde

## Portão 5 — fechamento

- [ ] T15. Conferir os 10 casos obrigatórios contra METARs reais da API (campo `rawOb`), só como sanidade
- [ ] T16. Preencher a matriz de rastreabilidade em `specs/README.md`
- [ ] T17. Commit
