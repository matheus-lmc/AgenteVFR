# 02 — Ferramentas: tarefas

Cada tarefa só é marcada quando os testes citados passam.

## Portão 3 — testes (vermelho)

- [x] T1. `requirements.txt` com `httpx` fixado; instalar na `.venv`
- [x] T2. Gravar fixtures da API real em `tests/fixtures/awc/` (METAR SBGR, METAR SBGR `hours=3`, TAF SBGR, 400)
- [x] T3. `pyproject.toml`: marcador `rede` fora da execução padrão
- [x] T4. `app/ferramentas.py` só com assinaturas e constantes
- [x] T5. `tests/test_ferramentas.py` (F-01 a F-09)
- [x] T6. Rodar `pytest` e registrar que os testes novos falham e os 155 do harness continuam verdes — 10/11/2026: 61 falham (60 `NotImplementedError`, 1 `PREFIXOS_BR` ausente), 155 verdes, 1 `rede` fora da execução

## Portão 4 — implementação (verde)

- [x] T7. `ResultadoBusca` e validações sem rede — F-01, F-02, F-08
- [x] T8. Requisição, tentativas e tratamento de respostas — F-03 a F-06
- [x] T9. Cache com relógio injetável e regra dos 55 min — F-07
- [x] T10. Atalhos de módulo — F-09
- [x] T11. `pytest` todo verde (harness + ferramentas)

## Portão 5 — fechamento

- [x] T12. Rodar o teste `rede` contra a API real — 10/11/2026: passou. Ponta a ponta com o harness: SBGR e SBSP `ok` → VMC; SBXX `sem_dado` (204); KMIA `fora_do_escopo` e `SB;GR` `icao_invalido` sem chamar a API; 2ª busca de SBGR veio do cache
- [x] T13. Matriz de rastreabilidade em `specs/README.md`
- [x] T14. Commit
