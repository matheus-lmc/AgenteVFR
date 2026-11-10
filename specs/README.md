# Especificações do AgenteVFR

O projeto é desenvolvido **orientado a especificação** (spec-driven): nenhum código de produção é escrito
antes de existir um requisito aprovado que o justifique e um teste que o verifique.

## Fluxo de cada módulo

| Passo | Artefato | Portão |
|---|---|---|
| 1 | `requisitos.md` — requisitos numerados em formato EARS | aprovação do grupo |
| 2 | `design.md` — API pública, estruturas de dados, decisões | aprovação do grupo |
| 3 | testes derivados dos requisitos, todos falhando (vermelho) | conferência |
| 4 | implementação até os testes passarem (verde) | `pytest` passando |
| 5 | matriz de rastreabilidade atualizada (abaixo) e `tarefas.md` concluído | revisão |

### Formato EARS (Easy Approach to Requirements Syntax)

| Padrão | Forma |
|---|---|
| Ubíquo | O harness DEVE … |
| Evento | QUANDO \<gatilho\>, o harness DEVE … |
| Indesejado | SE \<condição indesejada\>, ENTÃO o harness DEVE … |

### Convenções

- IDs: `REQ-H-xx` (harness), `REQ-F-xx` (ferramentas), `REQ-A-xx` (agente), `REQ-I-xx` (interface).
- Cada teste cita o requisito no nome: `test_req_h10_teto_1500_inclusivo_vmc`.
- Cada requisito aponta o perigo preliminar que mitiga (H1–H4); a análise completa fica em `stpa/`.

## Módulos

| # | Módulo | Pasta | Estado |
|---|---|---|---|
| 01 | Harness (decodificação, regra VMC/IMC, recusas, verificador) | `01-harness/` | requisitos e design aprovados; testes em andamento |
| 02 | Ferramentas (API aviationweather + cache) | `02-ferramentas/` | — |
| 03 | Agente (loop, prompt, traço) | `03-agente/` | — |
| 04 | Interface + Docker | `04-interface/` | — |
| 05 | Janela VFR pelo TAF (etapa 4b) | `05-janela-taf/` | — |

## Matriz de rastreabilidade

Preenchida no passo 5 de cada módulo.

| Requisito | Perigo | Teste(s) | Código |
|---|---|---|---|
| — | — | — | — |
