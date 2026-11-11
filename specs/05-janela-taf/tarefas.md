# 05 — Janela VFR pelo TAF: tarefas

Cada tarefa só é marcada quando os testes citados passam.

## Portão 3 — testes (vermelho)

- [x] T1. Esqueleto de `app/harness_taf.py`; `RespostaAgente.janelas`; ferramenta e prompt v3 só como assinatura
- [x] T2. `tests/test_taf.py` (J-01 a J-08 + 14 TAFs reais)
- [x] T3. Testes do agente (J-09 a J-12) e da página (J-13)
- [x] T4. Rodar `pytest`: novos falham; os anteriores continuam verdes — 10/11/2026: 92 falham (testes novos do TAF, do agente e da página, mais os testes alterados pela troca `buscar_taf` → `avaliar_janela` e pelo prompt v3); 324 passam

## Portão 4 — implementação (verde)

- [x] T5. Refatorar `harness.ler_condicoes` e `harness.contradicao` sem quebrar os 155 testes do harness
- [x] T6. `harness_taf.avaliar_taf`, períodos, melhor janela, texto-modelo — J-01 a J-08
- [x] T7. Agente: `avaliar_janela`, `janelas`, verificador por horário, prompt v3, pré-filtro — J-09 a J-12
- [x] T8. Página: linha do tempo da previsão — J-13
- [x] T9. `pytest` todo verde

## Portão 5 — fechamento

- [ ] T10. Ollama real: pergunta de janela em Congonhas; guardar traço em `traces/demo/`
- [ ] T11. Conferência no navegador (linha do tempo, 375 px)
- [ ] T12. Matriz de rastreabilidade e commit
