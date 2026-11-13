# 08 — Conformidade com a disciplina: requisitos dos ajustes

Revisão do repositório contra o enunciado do Exame e o material das aulas, refeita em 12/11/2026 sobre a `main`
em `514dc98` (merge do PR #2: avaliação e STPA).
**Estado: proposta — aguarda aprovação do grupo (portão 1).** Nenhum código foi alterado nesta revisão.

## 1. Fontes usadas na revisão

| Sigla | Documento | O que cobra deste projeto |
|---|---|---|
| EX | "Trabalho final da disciplina - Exame" (Classroom, editado em 07/11) | técnicas aceitas, roteiro da apresentação, seções do Artigo, AI Assurance com quatro pontos, "não invente métrica", nome e versão do modelo, "claim que a exposição não mostrou não entra na nota" |
| A10 | Aula 10 — Requisitos assistidos por LLM, STPA | STPA em quatro passos; perda → perigo → **restrição de segurança (SC)**; UCA = controlador + ação + tipo + contexto + perigo; rastreio **perigo → UCA → SC → requisito → verificação**; "quem aceita o rascunho é uma pessoa" |
| A11 | Aula 11 — Fine-tuning, LoRA | regra permanente fica no harness, não no peso |
| A12 | Aula 12 — Agentes, harness e evals | agente = modelo + harness (lista de ferramentas, limite de passos, ramo de erro, **revisão humana antes da ação sensível**); traço com **pergunta, ferramenta, trecho, resposta e parada**; evals com três graders (código → juiz → humano); **rubrica binária por critério**; juiz recebe **o traço inteiro**; juiz **calibrado com amostra humana antes de escalar**; **pass^k** para recusa; capacidade × regressão |
| A14 | Aula 14 — n8n e AI Assurance | quatro linhas de AI Assurance (limites, revisão humana, fontes, riscos); "registrar o id que rodou, não só o nome do provedor" |

## 2. O que mudou desde a primeira revisão

| Achado da 1ª revisão | Situação na `main` |
|---|---|
| Data da apresentação errada | **resolvido**: 13/11/2026, confirmada (CLAUDE.md) |
| `avaliacao/` inexistente | **resolvido em parte**: módulo 06 com 40 METARs rotulados, 24 perguntas em mundo congelado, juiz, CSV, figuras e leitura dos resultados. Ajustes de método na seção 4.2 |
| `stpa/` inexistente | **resolvido em parte**: módulo 07 com os quatro passos, origem de cada linha (LLM / LLM alt. / grupo) e não mitigados. Falta revisão do grupo, SC e rastreio (seção 4.3) |
| H7/H8 sem tratamento no AI Assurance | **resolvido** no CLAUDE.md e medido (ICAO exato 6/14 com o v3) |
| "RAG" na tabela de técnicas | **resolvido neste PR** (#3): tabela corrigida no CLAUDE.md (A1) |
| Sem revisão humana | **continua**, e agora os números mostram o tamanho do problema |
| Traço sem `parada` e sem id do modelo | **continua** |
| Item da ICA pendente | **continua**; `analise.md` já afirma "VMC pela ICA 100-1" |
| `docs/` (roteiro e Artigo) | roteiro **resolvido neste PR** (#3, A2); estrutura do Artigo **continua** (A14) |

## 3. O que está de acordo

| Pede a disciplina | Onde está |
|---|---|
| O modelo pede, o harness executa; ferramenta fora da lista não roda (A12) | `Agente._executar` |
| Limite de passos (A12) | `MAX_CHAMADAS_FERRAMENTA = 5` |
| Ramo de erro: vazio/falha vira estado, não frase (A12) | `MOTIVOS_BUSCA`, RECUSA com texto-modelo |
| Grader de código antes do juiz (A12) | verificador de contradição em execução; na avaliação, ICAO consultado vem de `avaliacoes`, sem ler o texto do modelo |
| Gabarito que não vem do sistema (A12) | 40 METARs rotulados pelo grupo; harness 40/40, API 32/40 |
| Suíte começa nas falhas reais (A12) | perguntas P02, P03, P13 (H7/H8) tiradas dos traços |
| Ler o traço quando a nota mente (A12) | `analise.md`: falsas recusas são ICAO errado; juiz errou P05 e P13 |
| STPA nos quatro passos, UCA nas quatro categorias (A10) | `stpa/stpa.md`, seções 1–5 |
| Rascunho do LLM aceito por uma pessoa (A10) | coluna "Origem" e seção 6 "Descartado" — falta só a marcação do grupo |
| Context Engineering e Prompt Engineering visíveis (EX) | `Resumo.para_dict()`; prompts v1–v3, comparados na avaliação |
| Regra permanente fora do modelo (A11) | `harness.py` só com biblioteca padrão |

## 4. Achados e requisitos

Formato EARS. Prefixos: `REQ-D` (documentação/entrega), `REQ-E` (ajustes da avaliação, módulo 06), `REQ-S`
(ajustes do STPA, módulo 07), `REQ-R` (revisão humana), `REQ-T` (traço, revisão do REQ-A-13).

| # | Achado | Prazo | Requisitos |
|---|---|---|---|
| A1 | CLAUDE.md lista "RAG/avaliação com outro modelo julgando"; o sistema não tem RAG | **resolvido** (PR #3) | REQ-D-01 |
| A2 | Não há `docs/roteiro_apresentacao.md` nem slides no repositório | roteiro **resolvido** (PR #3); slides: **13/11** | REQ-D-02 |
| A3 | `stpa/stpa.md` diz "Falta a revisão do grupo" | **13/11** | REQ-S-01 |
| A4 | O juiz não recebe a pergunta nem o nome da estação; por isso deu 5 ao P13 (respondeu "Guarulhos pra Congonhas" com dado de Campinas). A12 pede o traço inteiro | 04/12 | REQ-E-01 |
| A5 | Rubrica 1–5 somando três critérios; A12 pede passa/falha por critério | 04/12 | REQ-E-02 |
| A6 | Comparação juiz × humano cortada do escopo; o próprio grupo já achou 2 erros do juiz em 8 explicações. A12: o juiz só escala depois de concordar com gente | 04/12 | REQ-E-03 |
| A7 | Uma tentativa por pergunta, com semente fixa 42: não há pass^k nem variação; v1 × v3 com n = 14 e k = 1 | 04/12 | REQ-E-04 |
| A8 | Sem separação capacidade × regressão; nada protege contra troca de modelo ou de prompt | 04/12 | REQ-E-05 |
| A9 | STPA sem restrições de segurança (SC) e sem a tabela perigo → UCA → SC → requisito → verificação | 04/12 | REQ-S-02, REQ-S-03 |
| A10 | Sem revisão humana. Medido: ICAO exato 6/14; P13 respondeu "sim" com destino IMC; R09 respondeu sem aeródromo na pergunta. Um único ponto humano cobre H6, H7 e H8 sem tabela de nomes (respeita a D9 do módulo 03) | decisão D1 | REQ-R-01 a REQ-R-04 |
| A11 | O traço não tem o campo `parada` | 04/12 | REQ-T-01 |
| A12 | Traço, avaliação e STPA registram só a tag `llama3.1:8b`; EX pede "nome e versão, ou o id" | 04/12 | REQ-T-02 |
| A13 | Item da ICA não conferido, mas já usado como argumento ("MVFR para a API e VMC pela ICA 100-1") | 04/12 | REQ-D-03 |
| A14 | Não há `docs/artigo_estrutura.md` com o AI Assurance nos quatro pontos do EX | 04/12 | REQ-D-04 |
| A15 | CLAUDE.md descreve `buscar_taf` como ferramenta do modelo; desde o v3 ela não é exposta | **resolvido** (PR #3) | REQ-D-05 |
| A16 | `specs/README.md` não lista os módulos 06 e 07 nem a matriz deles | 04/12 | REQ-D-06 |

**Testes:** `pytest` com **443 passando**, rodado no branch do PR #3 em 12/11/2026 (conferido por matheus-lmc na
revisão do PR; a máquina desta revisão não tem Python).

### 4.1 Documentação e entrega

**REQ-D-01 — Técnicas declaradas.** A tabela "Técnicas da disciplina usadas neste projeto" DEVE listar só técnicas
com evidência no repositório. A linha "RAG/avaliação com outro modelo julgando" DEVE virar "Evals: gabarito do
grupo, grader de código e juiz LLM (`avaliacao/`, módulo 06)". A tabela DEVE incluir "AGENTS.md" (técnica listada
no EX). SE o Grupo decidir ter RAG (D4), ENTÃO a linha só volta quando corpus, recuperação e citação rodarem com
traço. *Verificação:* cada linha aponta um arquivo ou traço.

**REQ-D-02 — Roteiro da apresentação.** `docs/roteiro_apresentacao.md` DEVE cobrir os cinco pontos do EX em
10 min, com quem fala, e usar só números de `avaliacao/resultados/resumo.md` e traços existentes. O "caso que não
fecha" DEVE ser um caso medido (P13: "sim" com Congonhas IMC; ou R09). *Verificação:* cada número do roteiro
aponta para um arquivo.

**REQ-D-03 — Fonte dos mínimos.** O comentário de `TETO_MIN_FT`/`VIS_MIN_M`, o CLAUDE.md e o Artigo DEVEM citar o
documento, a edição e o item exatos lidos na publicação oficial do DECEA. ATÉ isso ser feito, textos que
contrapõem "API × ICA" DEVEM dizer "critério do projeto (item da ICA em conferência)".

**REQ-D-04 — Estrutura do Artigo.** `docs/artigo_estrutura.md` DEVE seguir as seções do EX e trazer o AI Assurance
nos quatro pontos, cada um apontando uma peça do sistema:

| Ponto do EX | Peça do sistema | Evidência |
|---|---|---|
| o que o sistema não faz | escopo, pré-filtro, só aeródromo e só METAR/TAF | REQ-H-03, REQ-H-13 |
| onde uma pessoa aprova, corrige ou interrompe | REQ-R-01 (se D1 = sim) **ou** "não existe; efeito: H6/H7/H8 chegam ao piloto, mitigados só por transparência" | `stpa.md` §7; `resumo.md` (6/14, P13, R09) |
| de onde vem o que o modelo afirma; fonte que não cobre | METAR/TAF da AWC → harness → resumo; sem dado → RECUSA | REQ-F-05/06; Galeão recusado por idade |
| o que quebra se o modelo errar o ramo, inventar um fato ou mudar de versão | H7/H8 (ramo); verificador e `icao_nao_avaliado` (fato); v1 × v3 e suíte de regressão REQ-E-05 + id do modelo REQ-T-02 (versão) | `resumo.md`; REQ-E-05 |

**REQ-D-05 — Coerência.** O CLAUDE.md DEVE descrever as ferramentas que o modelo vê hoje (`buscar_metar`,
`avaliar_janela`).

**REQ-D-06 — Índice.** `specs/README.md` DEVE listar os módulos 06, 07 e 08 com estado e matriz de rastreabilidade.

### 4.2 Ajustes da avaliação (módulo 06)

**REQ-E-01 — Juiz lê o traço inteiro.** O juiz DEVE receber a pergunta, os aeródromos consultados com
`nome_estacao`, o veredito, o resumo e a explicação. A rubrica DEVE ganhar o critério "responde à pergunta feita"
(a explicação fala do aeródromo pedido, com o dado do aeródromo pedido). *Verificação:* com esse critério, o P13
do v3 DEVE falhar; teste com juiz roteirizado em `tests/test_avaliacao.py`.

**REQ-E-02 — Rubrica binária.** Cada critério DEVE ser passa/falha, escrito com o que passa, o que falha e um
exemplo de cada tirado de traço real (`avaliacao/rubrica.md`). O juiz DEVE devolver, por critério, passa/falha e o
trecho do traço que justifica. O resumo DEVE reportar a taxa de passa por critério, sem média que some critérios.

**REQ-E-03 — Calibração com humano.** ANTES de reportar números do juiz no Artigo, duas pessoas do Grupo DEVEM
marcar passa/falha nas mesmas explicações (no mínimo as 8 já julgadas) sem ver a nota do juiz. O resumo DEVE
trazer a concordância juiz × humano por critério e listar as discordâncias. SE a concordância ficar abaixo da meta
(D2), ENTÃO o Artigo DEVE usar o rótulo humano e citar o juiz só como limite.

**REQ-E-04 — Repetição e pass^k.** QUANDO o avaliador rodar o agente, cada pergunta DEVE ser rodada k vezes
(k = 5, D3) com sementes diferentes, registradas no CSV. Recusas e ICAO exato DEVEM ser reportados em pass^k (as k
passam); a comparação v1 × v3 DEVE dizer n e k.

**REQ-E-05 — Regressão × capacidade.** O avaliador DEVE separar as tarefas que já passam (regressão: harness 40/40,
recusas do pré-filtro) das que ainda falham (capacidade: H7, H8, R09). QUANDO o modelo, o id do modelo ou a versão
do prompt mudar, a suíte de regressão DEVE ser rodada de novo e o resultado guardado com esse id.

**REQ-E-06 — Falsa recusa legítima.** As perguntas P DEVEM incluir pelo menos duas legítimas que contêm termos do
pré-filtro ("dá pra voar VFR mesmo com essa chuva em Congonhas?", "Congonhas tem pouso por instrumentos? E VFR,
como está?"), para medir a falsa recusa do código, separada da causada por ICAO errado.

### 4.3 Ajustes do STPA (módulo 07)

**REQ-S-01 — Revisão do grupo.** Cada linha de `stpa/stpa.md` DEVE estar marcada pelo Grupo (✔ ou corrigida, com
iniciais e data). ATÉ isso ser feito, a apresentação DEVE chamar o documento de "rascunho revisado pela ferramenta,
revisão do grupo em andamento". (A10: "quem aceita o rascunho é uma pessoa".)

**REQ-S-02 — Restrições de segurança.** O documento DEVE ter uma seção SC1…SCn, uma por perigo H1–H10, escrita
como frase "deve" ligada ao perigo (ex.: "SC7: o sistema deve apresentar o veredito só para o aeródromo que o
piloto pediu [H7]").

**REQ-S-03 — Rastreio.** O documento DEVE ter a tabela H → UCA → SC → requisito → verificação (teste, métrica da
avaliação ou "não mitigado"), no formato da Aula 10.

### 4.4 Revisão humana — só se D1 = "sim"

**REQ-R-01 — Confirmação do aeródromo.** QUANDO o agente terminar com veredito VMC ou IMC, a interface DEVE mostrar
a pergunta e "consultei: `ICAO — nome da estação`" e DEVE pedir que o piloto confirme que são os aeródromos que
ele quis, ANTES de mostrar o veredito em destaque. (H6, H7, H8)

**REQ-R-02 — Rejeição.** SE o piloto disser que não são os aeródromos pedidos, ENTÃO a interface NÃO DEVE mostrar o
veredito, DEVE mostrar "Sem veredito: aeródromo consultado não confere com a pergunta" e o traço DEVE registrar
`parada = "rejeitado_pelo_humano"`.

**REQ-R-03 — Registro.** A resposta do piloto DEVE ser gravada no traço (`POST /api/traco/{id}/revisao`, id
validado como no REQ-I-03) e NÃO DEVE alterar o veredito, que continua vindo só do harness.

**REQ-R-04 — Recusa não pede confirmação.** QUANDO o veredito for RECUSA, a interface NÃO DEVE pedir confirmação.

*Verificação:* testes de `main.py`; navegador; traço `rejeitado_pelo_humano` para P13 em `traces/demo/`.

### 4.5 Traço (revisão do REQ-A-13)

**REQ-T-01 — Parada.** Todo traço DEVE ter `parada` ∈ {`objetivo_cumprido`, `recusa_prefiltro`,
`recusa_harness`, `bloqueio_verificador`, `falha_tratada`, `limite_passos`, `sem_consulta`, `excecao`} e, com D1,
`aguardando_humano` / `rejeitado_pelo_humano`. `RespostaAgente` DEVE carregar o mesmo valor, e o `agente.csv`
DEVE ter a coluna. *Verificação:* um teste por valor, com o modelo roteirizado.

**REQ-T-02 — Id do modelo.** QUANDO o agente iniciar, ele DEVE ler o digest do modelo (`/api/tags`) e a versão do
Ollama (`/api/version`); cada traço, `resumo.md` e `stpa/saidas_llm/execucao.json` DEVEM registrar `modelo`,
`modelo_digest`, `ollama_versao` e as opções (`temperature`, `seed`, `num_thread`). SE o Ollama não responder,
ENTÃO os campos ficam `null` e a execução segue. *Verificação:* teste com `httpx.MockTransport`.

## 5. Decisões que o Grupo precisa tomar

| # | Decisão | Proposta | Alternativa | Efeito |
|---|---|---|---|---|
| D1 | Ter revisão humana (REQ-R) antes do veredito? | **Sim**, só a confirmação do aeródromo | Não; declarar a ausência no AI Assurance | Sim: um mecanismo cobre H6/H7/H8 (os três não mitigados do topo do `stpa.md` §7) sem tabela de nomes. Não: zero código; o EX pede o efeito por escrito |
| D2 | Meta de concordância juiz × humano | ≥ 80 % por critério | κ de Cohen ≥ 0,6 | Define se o juiz entra como métrica ou como limite |
| D3 | Como variar as k tentativas | Trocar a semente; temperatura fica 0,1 | Temperatura 0,7 | Mede a variação sem mudar o comportamento da demo |
| D4 | RAG no projeto? | **Não** | RAG sobre a norma de mínimos | Não: só corrigir a tabela. Sim: módulo novo, não cabe antes de 13/11 |
| D5 | O que fazer antes de amanhã | Só REQ-D-01, REQ-D-02 e REQ-S-01 | — | O resto fica para o Artigo (04/12). *Revisão do PR #3 (matheus-lmc, 12/11/2026):* de acordo; a D1, se aprovada, também fica para o Artigo (funcionalidade nova, com interface e testes) |

## 6. Fora desta spec

- Fine-tuning/LoRA (A11 justifica não usar); fluxo n8n (entrega individual de 04/12).
- Algoritmo VMC/IMC: 40/40 contra o gabarito; nenhuma não conformidade encontrada.
- Avaliação da janela pelo TAF: já declarada fora do escopo no módulo 06.
