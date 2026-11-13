# 08 — Conformidade com a disciplina: tarefas

Apresentação em **13/11/2026** (amanhã); Artigo em **04/12/2026**. Tarefas que mexem em código seguem os portões do
AGENTS.md. Marcar só quando a verificação citada passar.

## Portão 1

- [ ] T0. Grupo aprova `requisitos.md` e decide D1–D5

## Antes da apresentação (13/11) — só documentação

- [x] T1. CLAUDE.md: tabela de técnicas sem "RAG", com Evals e AGENTS.md — REQ-D-01 — 12/11/2026 (também
      corrigida a linha do agente: `avaliar_janela` no lugar de `buscar_taf`, REQ-D-05)
- [x] T2. `docs/roteiro_apresentacao.md` com os números de `avaliacao/resultados/resumo.md` e o P13 como caso que
      não fecha — REQ-D-02 — 12/11/2026; traços P01 (`b772ba60ca80`) e P13 (`b15eca68c99a`) copiados para
      `traces/demo/`; falta preencher "quem fala"
- [ ] T3. Grupo marca as linhas de `stpa/stpa.md` (ou a apresentação diz que a revisão está em andamento) — REQ-S-01
      — 12/11/2026: tabela "Revisão do grupo" criada no topo do `stpa.md`; falta o grupo preencher
- [x] T4. Rodar `pytest` e anotar o total — 12/11/2026: 443 passando no branch do PR #3 (rodado por matheus-lmc)

## Para o Artigo (04/12)

- [ ] T5. Juiz com pergunta e nome da estação; critério "responde à pergunta feita" — REQ-E-01
- [ ] T6. `avaliacao/rubrica.md` e juiz passa/falha por critério — REQ-E-02
- [ ] T7. Rótulo humano duplo das explicações e concordância com o juiz — REQ-E-03
- [ ] T8. k = 5 com semente variando; pass^k — REQ-E-04
- [ ] T9. Suítes de regressão e capacidade — REQ-E-05
- [ ] T10. Perguntas legítimas com termos do pré-filtro — REQ-E-06
- [ ] T11. STPA: seção de SC e tabela de rastreio — REQ-S-02, REQ-S-03
- [ ] T12. Traço com `parada` (testes antes) — REQ-T-01
- [ ] T13. Traço com digest, versão do Ollama e opções (testes antes) — REQ-T-02
- [ ] T14. Revisão humana, se D1 = sim (requisitos → design → testes → código) — REQ-R-01 a REQ-R-04
- [ ] T15. Conferir o item da norma dos mínimos e atualizar código, CLAUDE.md e `analise.md` — REQ-D-03
- [ ] T16. `docs/artigo_estrutura.md` com o AI Assurance nos quatro pontos — REQ-D-04
- [x] T17. CLAUDE.md: ferramentas atuais — REQ-D-05 — feito junto com a T1 (PR #3)
- [ ] T18. `specs/README.md`: módulos 06, 07, 08 e matrizes — REQ-D-06
- [ ] T19. Rodar a avaliação de novo depois de T5–T13 e atualizar `resumo.md` e `analise.md`
