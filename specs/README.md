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
| 02 | Ferramentas (API aviationweather + cache) | `02-ferramentas/` | concluído (61 testes verdes + 1 ao vivo) |
| 03 | Agente (loop, prompt, traço) | `03-agente/` | concluído (73 testes verdes; teste com Ollama real falha por H7, registrado) |
| 04 | Interface + Docker | `04-interface/` | concluído (36 testes verdes; Compose medido: 15,2 s por pergunta) |
| 05 | Janela VFR pelo TAF (etapa 4b) | `05-janela-taf/` | concluído (95 testes verdes + 1 com Ollama real) |

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

### 02 — Ferramentas (`tests/test_ferramentas.py`, 61 testes verdes + 1 ao vivo em 10/11/2026)

| Requisito | Perigo | Testes | Código (`app/ferramentas.py`) |
|---|---|---|---|
| REQ-F-01 validação do ICAO | H4 | `test_req_f01_*` (9) | `_RE_ICAO` em `_buscar` |
| REQ-F-02 escopo antes da rede | H4 | `test_req_f02_*` (7) | `PREFIXOS_BR` importado do harness |
| REQ-F-03 requisição | H1 | `test_req_f03_*` (6) | `USER_AGENT`, `AWC_BASE_URL`, `AWC_TIMEOUT_S` |
| REQ-F-04 resposta com dado | H1 | `test_req_f04_*` (7) | `_CAMPO_TEXTO` |
| REQ-F-05 sem dado | H1, H5 | `test_req_f05_*` (2) | `_buscar` (204 e `[]`) |
| REQ-F-06 falhas | H5 | `test_req_f06_*` (15) | `MAX_TENTATIVAS`, `_buscar` |
| REQ-F-07 cache | H2 | `test_req_f07_*` (10) | `CACHE_TTL_S`, `CACHE_IDADE_MAX_METAR_MIN`, `_cache_valido` |
| REQ-F-08 resultado | — (traço) | `test_req_f08_*` (4) | `ResultadoBusca` |
| REQ-F-09 testes sem rede | — | `test_req_f09_*` (2, 1 ao vivo) | `ClienteAWC(http=..., relogio=...)`, atalhos |

### 03 — Agente, prompt e traço (`tests/test_agente.py`, `test_traco.py`, `test_prompts.py`; 73 testes verdes + 1 com Ollama real em 10/11/2026)

| Requisito | Perigo | Testes | Código |
|---|---|---|---|
| REQ-A-01 pré-filtro antes do modelo | H4 | `test_req_a01_*` (5) | `Agente._responder` + `harness.prefiltrar_pergunta` |
| REQ-A-02 ferramentas | — | `test_req_a02_*` (8) | `prompts.FERRAMENTAS`, `Agente._executar` |
| REQ-A-03 janela (Context Eng.) | — | `test_req_a03_*` (4) | `Agente._executar` (só resumo + `nome_estacao`) |
| REQ-A-04 limite de 5 chamadas | H6 | `test_req_a04_*` (2) | `MAX_CHAMADAS_FERRAMENTA` |
| REQ-A-05 resposta sem consulta | H6 | `test_req_a05_*` (2) | `LEMBRETE_FERRAMENTA`, `sem_avaliacao` |
| REQ-A-06 falha do modelo | — | `test_req_a06_*` (7) | `ClienteOllama`, `ErroModelo` |
| REQ-A-07 veredito geral em código | H1 | `test_req_a07_*` (6) | `Agente._responder` |
| REQ-A-08 recusa não é consertada | H1, H4 | `test_req_a08_*` (1) | `Agente._responder` |
| REQ-A-09 verificação da explicação | H3 | `test_req_a09_*` (4) | `harness.verificar_explicacao`, `_RE_ICAO_BR` |
| REQ-A-10 resposta | — | `test_req_a10_*` (2) | `RespostaAgente` |
| REQ-A-11 chamada ao Ollama (rev.: `num_thread`) | — | `test_req_a11_*` (4) | `ClienteOllama.conversar` |
| REQ-A-12 prompt versionado (rev.: v2) | — | `test_req_a12_*` (6) | `prompts.PROMPT_SISTEMA_V1/V2` |
| REQ-A-13 traço | — | `test_req_a13_*` (11) | `app/traco.py` |
| REQ-A-14 testes sem modelo / Ollama real | — | `test_req_a14_ollama_real` (**falha: H7**) | `ModeloRoteirizado` |
| REQ-A-15 nome da estação | H7 (só transparência) | `test_req_a15_*` (11) | `_nome_estacao` |

### 04 — Interface e Docker (`tests/test_main.py`, 36 testes verdes + conferência no navegador em 10/11/2026)

| Requisito | Perigo | Testes / verificação | Código |
|---|---|---|---|
| REQ-I-01 página | — | `test_req_i01_*` (1) | `pagina()` em `app/main.py` |
| REQ-I-02 pergunta | — | `test_req_i02_*` (10) | `perguntar()`, `Pergunta(StrictStr)` |
| REQ-I-03 traço (id validado antes do disco) | — | `test_req_i03_*` (10) | `_RE_ID_TRACO`, `traco()` |
| REQ-I-04 execuções gravadas | — | `test_req_i04_*` (3) | `demo()` |
| REQ-I-05 saúde | — | `test_req_i05_*` (8) | `verificar_saude_ollama()` |
| REQ-I-06 fábrica | — | `test_req_i06_*` (1) | `criar_app()` |
| REQ-I-07 pergunta e exemplos | — | `test_req_i07_*` (1) + navegador | `index.html` |
| REQ-I-08 veredito (1C) | H1 | navegador | `cartaoVeredito()` |
| REQ-I-09 aeródromos consultados (2B) | H7, H8 (transparência) | navegador | `cartaoAerodromos()` |
| REQ-I-10 explicação e bloqueio (3B) | H3 | navegador (simulado) | `cartaoExplicacao()`, `preencherTextoBloqueado()` |
| REQ-I-11 texto como texto | H9 | `test_req_i11_*` (1) | `el()` com `textContent` |
| REQ-I-12 traço (6B) | — | navegador | `abrirTraco()` |
| REQ-I-13 execuções gravadas na página | — | navegador | `carregarDemo()`, `abrirGravada()` |
| REQ-I-14 avisos e erros (4A, 5B) | — | navegador (parcial) | `.aviso`, `mostrarEspera()`, `mostrarErro()` |
| REQ-I-15 acessibilidade | — | contraste calculado; 375 px conferido | CSS |
| REQ-I-16 sem recurso externo | — | `test_req_i16_*` (1) | `index.html` |
| REQ-I-17 imagem | — | `docker compose build` | `Dockerfile` |
| REQ-I-18 Compose | — | `docker compose up` + saúde no contêiner | `docker-compose.yml` |
| REQ-I-19 tempo por pergunta | — | 5 perguntas: média 15,2 s | `tarefas.md` |

### 05 — Janela VFR pelo TAF (`tests/test_taf.py` + partes de `test_agente.py`, `test_prompts.py`, `test_main.py`; 11/11/2026)

| Requisito | Perigo | Testes | Código |
|---|---|---|---|
| REQ-J-01 formato | H1 | `test_req_j01_*` (12) | `harness_taf._avaliar` (cabeçalho) |
| REQ-J-02 TAF sem uso / datas | H2 | `test_req_j02_*` (9) | `_periodo`, `_dia_hora` |
| REQ-J-03 condições | H1 | `test_req_j03_*` (9) | `_cond` + `harness.ler_condicoes` |
| REQ-J-04 grupos de mudança (pior caso) | H1 | `test_req_j04_*` (10) | `_aplicar`, `_avaliar_hora` |
| REQ-J-05 veredito por hora | H1 | `test_req_j05_*` (6) | `_avaliar_hora` + `harness.eh_vmc` |
| REQ-J-06 períodos e melhor janela | — | `test_req_j06_*` (3) + reais | `_periodos`, `_melhor_janela` |
| REQ-J-07 resumo compacto | — (Context Eng.) | `test_req_j07_*` (4) | `ResumoJanela` |
| REQ-J-08 independência do modelo | H1, H3 | `test_req_j08_*` (2) | imports |
| TAFs reais (14) | — | `test_reais_*` (16) | — |
| REQ-J-09 ferramenta `avaliar_janela` | H10 | `test_req_j09_*` (5, 1 com Ollama real) | `Agente._executar` |
| REQ-J-10 prompt v3 | — | `test_req_j10_*` (1) | `PROMPT_SISTEMA_V3` |
| REQ-J-11 verificação com horário | H3 | `test_req_j11_*` (13) | `_verificar_com_horario`, `_veredito_previsto` |
| REQ-J-12 pré-filtro oferece a janela | H4 | `test_req_j12_*` (1) | `MOTIVOS_PERGUNTA` |
| REQ-J-13 linha do tempo | H10 | `test_req_j13_*` (1) + navegador | `cartaoPrevisao()` |
