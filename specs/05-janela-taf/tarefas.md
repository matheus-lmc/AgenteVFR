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

- [x] T10. Ollama real: pergunta de janela em Congonhas; guardar traço em `traces/demo/` — 11/11/2026 00:29Z,
      `llama3.1:8b`, prompt v3, 42 s: o modelo chamou `avaliar_janela(SBSP)` e, após o lembrete, `buscar_metar(SBSP)`;
      explicação aceita ("melhor janela … de 07Z a 12Z (5 horas)"); traço `049c3dd3476c` em `traces/demo/`.
      `test_req_j09_ollama_real_janela` passou (41 s).
- [x] T11. Conferência no navegador (linha do tempo, 375 px) — linha do tempo, melhor janela contornada, lista
      textual e TAF bruto conferidos; em 375 px a faixa rola por dentro, sem rolagem horizontal na página.
- [x] T12. Matriz de rastreabilidade e commit

## Achados com o modelo real e o navegador (11/11/2026)

- **Bug do verificador, achado com o modelo real:** "a melhor janela é de 07Z a 12Z" foi bloqueada como
  `horario_fora_da_validade` porque 12Z é o **fim** da validade (limite exclusivo). Corrigido: o fim exato da
  validade vale pela última hora prevista. Teste de regressão em `test_req_j11_passa`.
- **Rótulo enganoso, achado no navegador:** com o TAF real de SBSP aparecia "04Z–07Z IMC (BECMG 1102/1104)", mas
  esse BECMG só muda o vento — o IMC vinha da base (`BKN011`). Corrigido: BECMG que não muda visibilidade nem
  nuvens não vira o "grupo responsável". Teste `test_req_j05_becmg_so_de_vento_nao_vira_o_grupo_responsavel`.
- **Bom exemplo de H10 para a demo:** às 00Z o METAR de SBSP estava VMC (`OVC015`, no limite), enquanto o TAF
  previa IMC até 07Z (`BKN011`). Observação e previsão discordam — por isso a previsão fica separada do veredito.
- O modelo chamou `avaliar_janela` antes de `buscar_metar` e só consultou o METAR depois do lembrete (REQ-A-05):
  a pergunta de janela leva ~40 s (3–4 chamadas ao modelo).
