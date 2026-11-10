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
| 01 | Harness (decodificação, regra VMC/IMC, recusas, verificador) | `01-harness/` | concluído (155 testes verdes) |
| 02 | Ferramentas (API aviationweather + cache) | `02-ferramentas/` | requisitos aprovados; design em revisão |
| 03 | Agente (loop, prompt, traço) | `03-agente/` | — |
| 04 | Interface + Docker | `04-interface/` | — |
| 05 | Janela VFR pelo TAF (etapa 4b) | `05-janela-taf/` | — |

## Matriz de rastreabilidade

Preenchida no passo 5 de cada módulo.

### 01 — Harness (`tests/test_harness.py`, 155 testes verdes em 10/11/2026)

| Requisito | Perigo | Testes | Código (`app/harness.py`) |
|---|---|---|---|
| Aceite (CLAUDE.md) | H1, H2, H4 | `test_aceite_*` (10) | `avaliar_metar` |
| REQ-H-01 formato | H1 | `test_req_h01_*` (13) | `avaliar_metar` (cabeçalho) |
| REQ-H-02 ordem das checagens | H1, H2, H4 | `test_req_h02_*` (6) | `avaliar_metar` (sequência de `recusa(...)`) |
| REQ-H-03 escopo geográfico | H4 | `test_req_h03_*` (12) | `PREFIXOS_BR` |
| REQ-H-04 ICAO divergente | H1 | `test_req_h04_*` (2) | `avaliar_metar` |
| REQ-H-05 NIL | H1 | `test_req_h05_*` (1) + aceite | `avaliar_metar` |
| REQ-H-06 idade | H2 | `test_req_h06_*` (10) | `_resolver_horario`, `IDADE_MAX_MIN`, `TOLERANCIA_FUTURO_MIN` |
| REQ-H-07 parte decodificada | H1 | `test_req_h07_*` (6) | `_FIM_DA_OBSERVACAO` |
| REQ-H-08 visibilidade | H1 | `test_req_h08_*` (7) | `_RE_VIS`, `_RE_VIS_MINIMA` |
| REQ-H-09 teto | H1 | `test_req_h09_*` (18) | `_RE_NUVEM`, `_RE_VV`, `_partes_camada` |
| REQ-H-10 regra VMC/IMC | H1 | `test_req_h10_*` (11) | `TETO_MIN_FT`, `VIS_MIN_M`, `_motivo` |
| REQ-H-11 independência do modelo | H1, H3 | `test_req_h11_*` (2) | imports só da biblioteca padrão |
| REQ-H-12 resumo compacto | — (Context Eng.) | `test_req_h12_*` (7) | `Resumo`, `_recusa` |
| REQ-H-13 pré-filtro | H4 | `test_req_h13_*` (27) | `TERMOS_FORA_DE_ESCOPO`, `prefiltrar_pergunta` |
| REQ-H-14 contradição | H3 | `test_req_h14_*` (17) | `_FAVORAVEL`, `_DESFAVORAVEL`, `verificar_explicacao` |
| REQ-H-15 substituição | H3 | `test_req_h15_*` (6) | `texto_modelo` |
