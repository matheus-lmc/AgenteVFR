# 01 — Harness: tarefas

Cada tarefa só é marcada quando os testes citados passam.

## Portão 3 — testes (vermelho)

- [x] T1. `pyproject.toml` (pythonpath), `app/__init__.py`, `app/harness.py` só com assinaturas
      (`raise NotImplementedError`) — para os testes importarem
- [x] T2. `tests/test_harness.py`: helper `metar(texto, minutos_atras)` e `AGORA` fixo
- [x] T3. Testes dos 10 casos obrigatórios (aceite)
- [x] T4. Testes de H-01 a H-12 (`avaliar_metar`, `Resumo`)
- [x] T5. Testes de H-13 (`prefiltrar_pergunta`)
- [x] T6. Testes de H-14 e H-15 (`verificar_explicacao`, `texto_modelo`)
- [x] T7. Rodar `pytest` e registrar que todos falham — 10/11/2026: 155 testes, 153 falham (152 `NotImplementedError`, 1 `TERMOS_FORA_DE_ESCOPO` ausente); passam só `test_req_h10_constantes` e `test_req_h11_so_biblioteca_padrao`, que o esqueleto já satisfaz

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
