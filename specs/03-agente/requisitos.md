# 03 — Agente, prompt e traço: requisitos

**Estado:** aprovado em 10/11/2026 · **Módulos:** `app/agente.py`, `app/prompts.py`, `app/traco.py` ·
**Testes:** `tests/test_agente.py`, `tests/test_traco.py`

## 1. Objetivo e escopo

O agente recebe a pergunta em linguagem natural, deixa o modelo (Llama via Ollama) decidir **quais aeródromos**
consultar e **redigir a explicação**, e força em código tudo o que importa para a segurança: pré-filtro,
veredito, verificação da explicação e registro de cada passo.

| Quem | Decide |
|---|---|
| Modelo | nome do aeródromo → ICAO; quais ferramentas chamar e em que ordem; texto da explicação |
| Código | se a pergunta entra; o veredito de cada aeródromo e o geral; se a explicação é aceita; o que entra na janela; quando parar |

**Fora do escopo:** HTTP/interface (módulo 04); decodificação do TAF e janela VFR (módulo 05); avaliação em lote
(`avaliacao/`).

## 2. Perigos preliminares mitigados

H1 (VMC quando é IMC), H3 (explicação contradiz o veredito), H4 (fora do escopo), H5 (dado inventado) — ver
módulos 01 e 02. Novos neste módulo: **H6 — sistema dá resposta sem ter consultado dado algum**; **H7 — o modelo
mapeia o nome para o aeródromo errado** (seção 5).

## 3. Requisitos

### Entrada e pré-filtro

**REQ-A-01 — Pré-filtro antes do modelo** (H4)
- QUANDO a pergunta chegar, o agente DEVE chamar `harness.prefiltrar_pergunta` **antes** de qualquer chamada ao
  modelo.
- SE o pré-filtro recusar, ENTÃO o agente DEVE responder `RECUSA` com a categoria e o motivo, sem chamar o
  modelo, e registrar no traço.
- SE a pergunta estiver vazia ou passar de 500 caracteres, ENTÃO o agente DEVE recusar com `pergunta_invalida`
  sem chamar o modelo.

### Ferramentas expostas ao modelo

**REQ-A-02 — Conjunto de ferramentas** *[Decisão D1]*
- O agente DEVE expor ao modelo exatamente duas ferramentas, no formato de *tool calling* do Ollama:
  - `buscar_metar(icao)`: busca o METAR (módulo 02), passa pelo harness (módulo 01) e devolve **só o resumo
    compacto** do harness;
  - `buscar_taf(icao)`: devolve o TAF bruto, marcado como informativo (não entra no veredito).
- O agente DEVE recusar chamadas de ferramenta desconhecida ou com argumentos inválidos devolvendo ao modelo uma
  mensagem de erro curta (a chamada conta como iteração).

**REQ-A-03 — O que entra na janela** (Context Engineering)
- A janela de cada chamada ao modelo DEVE conter só: prompt de sistema, pergunta, mensagens anteriores do
  modelo, e resultados de ferramenta compactos.
- O resultado de `buscar_metar` na janela DEVE ser exatamente o `Resumo.para_dict()` do harness (ou, quando a
  busca falhar, `{icao, status, veredito: "RECUSA", motivo}`).
- O resultado de `buscar_taf` na janela DEVE ser `{icao, status, taf_bruto, aviso}`.
- O JSON bruto da API (`resposta_api`) NÃO DEVE entrar na janela em nenhum caso; ele vai só para o traço.
- *Revisão 10/11/2026 (seção 5):* o resultado de `buscar_metar` com sucesso leva também `nome_estacao`.

### Loop

**REQ-A-04 — Limite de iterações** (H6)
- O agente DEVE parar depois de **5** chamadas de ferramenta e responder `RECUSA` com `limite_iteracoes`.

**REQ-A-05 — Resposta sem consulta** (H6) *[Decisão D2]*
- QUANDO o modelo responder sem ter chamado `buscar_metar` com sucesso, o agente DEVE pedir uma vez que ele use
  a ferramenta.
- SE mesmo assim não houver nenhuma avaliação, ENTÃO o agente DEVE responder `RECUSA` com `sem_avaliacao` e
  descartar o texto do modelo.

**REQ-A-06 — Falha do modelo**
- SE o Ollama estiver inacessível, demorar mais que `OLLAMA_TIMEOUT_S` (padrão 300 s), responder erro ou
  devolver formato inesperado, ENTÃO o agente DEVE responder `RECUSA` com `erro_modelo`, sem exceção para quem
  chamou, e registrar o erro no traço.

### Veredito e explicação

**REQ-A-07 — Veredito geral em código** (H1)
- O veredito de cada aeródromo DEVE ser o do harness. O agente considera, por ICAO, a **última** avaliação
  de `buscar_metar` (tentativas com `icao_invalido` não contam: são erro de digitação do modelo).
- O veredito geral DEVE ser: `RECUSA` se algum aeródromo avaliado for `RECUSA`; senão `IMC` se algum for `IMC`;
  senão `VMC`.
- O veredito exibido DEVE vir sempre desse cálculo, nunca do texto do modelo.

**REQ-A-08 — Recusa não é "consertada" pelo modelo** (H1, H4)
- QUANDO o veredito geral for `RECUSA`, o agente DEVE responder com o texto-modelo de recusa (motivos de cada
  aeródromo recusado) e descartar a explicação do modelo.

**REQ-A-09 — Verificação da explicação** (H3)
- QUANDO o veredito geral for `VMC` ou `IMC`, o agente DEVE passar a explicação final do modelo por
  `harness.verificar_explicacao` contra o veredito geral. *[Decisão D3]*
- SE a explicação citar um código ICAO brasileiro que não foi avaliado, ENTÃO o agente DEVE bloqueá-la com a
  regra `icao_nao_avaliado` (o modelo inventou um aeródromo). *[Decisão D4]*
- Explicação bloqueada DEVE ser substituída pelo texto-modelo de todos os aeródromos avaliados.

**REQ-A-10 — Resposta**
- O agente DEVE devolver: `id_traco`, `veredito`, `motivo`, `avaliacoes` (lista de resumos do harness),
  `explicacao` (texto final), `origem_explicacao` (`modelo` / `texto_modelo`), `bloqueio`
  (`{regra, trecho}` ou `null`), `aviso` fixo ("Ferramenta acadêmica. Não substitui o briefing meteorológico
  oficial."), `duracao_ms`.
- *Revisão 10/11/2026 (seção 5):* cada item de `avaliacoes` leva também `nome_estacao`.

### Modelo e prompt

**REQ-A-11 — Chamada ao Ollama** (reprodutibilidade)
- O agente DEVE chamar `POST {OLLAMA_URL}/api/chat` com `stream: false`, as ferramentas, `temperature` de
  `OLLAMA_TEMPERATURA` (padrão 0.1) e `seed` fixa (42).
- O agente DEVE mandar `num_thread` de `OLLAMA_NUM_THREAD` (padrão 4) nas opções.
- URL, modelo, temperatura, threads e tempo limite DEVEM vir de variáveis de ambiente (`OLLAMA_URL`
  padrão `http://localhost:11434`, `OLLAMA_MODEL` padrão `llama3.1:8b`).
- *Revisão 10/11/2026:* `num_thread` acrescentado. No M3 (4 núcleos de desempenho + 4 de eficiência) o padrão
  do Ollama (8 threads) derrubou a geração do `llama3.2:3b` para 0,49 tok/s; com 4 threads, 31,7 tok/s
  (medição em `tarefas.md`, seção "Achados com o modelo real").

**REQ-A-12 — Prompt de sistema versionado** (Prompt Engineering)
- O prompt de sistema DEVE ficar em `app/prompts.py` como constante com identificador de versão
  (ex.: `PROMPT_SISTEMA_V1`), e o traço DEVE registrar qual versão foi usada.
- O prompt DEVE instruir o modelo a: consultar `buscar_metar` para cada aeródromo citado; usar o campo
  `veredito` sem recalculá-lo; citar teto, visibilidade e o METAR das ferramentas; não inventar dados; responder
  em português, em até 4 frases; lembrar que não substitui o briefing oficial.
- O prompt NÃO DEVE conter tabela de nomes → ICAO. *[Decisão D5]* (O mapeamento é o que o modelo decide e é
  medido na avaliação.)
- *Revisão 10/11/2026 (seção 5):* prompt atual passa a ser o `PROMPT_SISTEMA_V2` (`VERSAO_PROMPT = "v2"`), que
  pede para conferir `nome_estacao`; o v1 continua no código.

### Traço

**REQ-A-13 — Conteúdo do traço** (prova de que rodou)
- Toda execução, inclusive recusa e erro, DEVE gerar `traces/<AAAAMMDDTHHMMSSZ>_<id>.json` com: `id`, `inicio`,
  `pergunta`, `modelo`, `versao_prompt`, `passos`, `resposta`, `duracao_ms`.
- Cada passo DEVE ter `tipo` ∈ {`prefiltro`, `modelo`, `ferramenta`, `harness`, `verificador`, `erro`} e:
  - `modelo`: as mensagens enviadas (o que entrou na janela), a resposta, `prompt_eval_count` e `eval_count`
    do Ollama, estimativa de tokens (caracteres / 4) e duração;
  - `ferramenta`: nome, argumentos, `ResultadoBusca.para_dict()` completo (com `resposta_api`) e o que foi
    devolvido à janela;
  - `harness` / `verificador` / `prefiltro`: passou ou bloqueou, regra e motivo.
- O `id` DEVE ser gerado pelo código (12 caracteres hexadecimais aleatórios), nunca vindo da pergunta.
- A pasta de traços DEVE vir de `TRACES_DIR` (padrão `traces/`).

### Testabilidade

**REQ-A-14 — Testes sem modelo**
- O cliente do Ollama, as ferramentas, o relógio e a pasta de traços DEVEM ser injetáveis, para testar o loop
  com um modelo roteirizado (respostas pré-definidas).
- Testes contra o Ollama real DEVEM ficar marcados (`@pytest.mark.ollama`) fora da execução padrão.

## 4. Decisões (confirmadas em 10/11/2026, opção proposta)

| ID | Decisão proposta | Alternativa | Efeito |
|---|---|---|---|
| D1 | Duas ferramentas: `buscar_metar` já devolve o resumo do harness; `buscar_taf` informativo. O `avaliar_condicoes` da tabela do CLAUDE.md some (fica implícito em `buscar_metar`; no módulo 05 entra `avaliar_janela`) | Três ferramentas (`buscar_metar` bruto + `avaliar_condicoes`) | Menos chances do modelo 8b pular a avaliação; o METAR nunca chega à janela sem veredito. **Exige ajustar a tabela do CLAUDE.md** |
| D2 | Um lembrete se o modelo responder sem consultar | Recusar direto | Demo mais robusta; custa uma chamada a mais |
| D3 | Com vários aeródromos, verificar a explicação contra o veredito **geral** | Verificar frase a frase por aeródromo | Simples; em rota mista (um VMC, outro IMC), "Guarulhos está VMC" é bloqueado e trocado pelo texto-modelo (erro para o lado seguro). Limite para o AI Assurance |
| D4 | Bloquear explicação que cita ICAO brasileiro não avaliado | Não checar | Pega um tipo de invenção com regra simples |
| D5 | Sem tabela nome → ICAO no prompt | Tabela com ~20 aeródromos | Mantém a métrica de acerto de ICAO honesta |
| D6 | `buscar_taf` entra só como informativo até o módulo 05; o verificador não checa o que o modelo diz do TAF | Tirar o TAF até o módulo 05 | O modelo pode errar ao ler o TAF; limite registrado para o AI Assurance |

## 5. Revisão 1 — mitigação do H7 (aprovada em 10/11/2026)

**Perigo H7 — o modelo mapeia o nome para o aeródromo errado.** Achado com o modelo real em 10/11/2026: o
`llama3.1:8b` converte "Guarulhos" em `SBKP` (Campinas) de forma reprodutível; o veredito sai para Campinas e a
explicação fala de Guarulhos. Nenhuma checagem atual pega: o ICAO é válido, brasileiro e foi avaliado.

**Restrição encontrada:** o nome da estação que a API devolve não serve para comparação automática. Para
`SBGR` ela diz `"Sao Paulo Intl, PR, BR"` (sem "Guarulhos" e com o estado errado); para `SBSP`,
`"Sao Paulo/Congonhas, SP, BR"`; para `SBKP`, `"Campinas/Viracopos Arpt, SP, BR"`. Uma regra "o nome da
pergunta tem que aparecer no nome da estação" bloquearia o próprio SBGR correto.

Por isso a mitigação proposta é de **transparência**, e não de bloqueio: deixar o erro visível para o modelo
(que pode se corrigir) e para o piloto (que confere o que foi avaliado).

### Requisitos novos

**REQ-A-15 — Nome da estação** (H7)
- QUANDO `buscar_metar` tiver sucesso, o agente DEVE ler o nome da estação do campo `name` do primeiro elemento
  de `resposta_api` (só para identificação; não entra no veredito, REQ-H-11).
- O agente DEVE acrescentar `nome_estacao` ao que vai para a janela do modelo e a cada item de `avaliacoes` da
  resposta. Sem nome na API → `nome_estacao = null`.
- O agente NÃO DEVE usar `nome_estacao` para bloquear, aprovar ou mudar o veredito. *[Decisão D7]*

### Requisitos alterados

**REQ-A-03 — O que entra na janela** — a frase "exatamente o `Resumo.para_dict()` do harness" passa a ser
"exatamente o `Resumo.para_dict()` do harness mais `nome_estacao`". O JSON bruto continua fora da janela.

**REQ-A-10 — Resposta** — cada item de `avaliacoes` passa a ter `nome_estacao` além das chaves do resumo.

**REQ-A-12 — Prompt v2** — novo prompt `PROMPT_SISTEMA_V2` (`VERSAO_PROMPT = "v2"`), igual ao v1 mais uma
instrução: conferir se `nome_estacao` corresponde ao aeródromo da pergunta e, se não corresponder, chamar
`buscar_metar` de novo com o código certo antes de responder. Continua sem tabela nome → ICAO (D5). O v1 fica no
código para comparação na avaliação. *[Decisão D8]*

### Critério de aceite com o modelo real

- `test_req_a14_ollama_real` ("Dá pra ir VFR em Guarulhos agora?") passa a exigir que `SBGR` esteja avaliado.
  Se o v2 não corrigir o `SBKP`, o teste continua falhando e o resultado vai para o AI Assurance como perigo
  **não mitigado pelo modelo** (só pela transparência na interface). *[Decisão D9]*

### Decisões da revisão 1 (confirmadas em 10/11/2026, opção proposta)

| ID | Decisão proposta | Alternativa | Efeito |
|---|---|---|---|
| D7 | Nome da estação só informa (modelo e piloto); não bloqueia | Bloquear quando o nome da pergunta não aparece no nome da estação | A alternativa bloquearia o SBGR correto (a API diz "Sao Paulo Intl"); a proposta não garante a correção, mas torna o erro visível |
| D8 | Prompt v2 pede ao modelo para conferir a estação; v1 preservado | Manter v1 e confiar só na interface | Dá ao modelo a chance de se corrigir e rende uma comparação v1 × v2 na avaliação |
| D9 | Se o v2 não resolver, registrar H7 como não mitigado pelo modelo; nada de tabela de apelidos em código | Tabela de apelidos em código (ex.: Guarulhos → SBGR) para conferir o mapeamento | A tabela cobre só os nomes listados e mexe na métrica de acerto de ICAO; fica como trabalho futuro no artigo |

## 6. Revisão 2 — chat conversacional (aprovada em 13/11/2026)

**Motivo:** na interface em chat (spec 09), uma pergunta sem aeródromo ("oi", "o que é VMC?") terminava em
`RECUSA` `sem_avaliacao`, com o cartão cinza de veredito. O grupo pediu que, sem veredito definitivo, a resposta
saia só como mensagem de texto. As recusas do harness e do pré-filtro continuam com cartão.

### O que o teste ao vivo mostrou

Com o prompt v3, o llama3.1:8b chamou `buscar_metar(SBKP)` até para "Oi, tudo bem?" e mostrou "VMC em Campinas".
Com o prompt v4 sem ferramenta nova, ele passou o ICAO "NULL" (RECUSA "fora do Brasil"). Quando há ferramentas na
chamada, o modelo quase sempre chama alguma, e o Ollama não tem opção para proibir isso. Por isso o v4 ganhou a
ferramenta `conversar(mensagem)`: uma saída sem consulta que o modelo pode escolher.

### Requisito novo

**REQ-A-16 — Conversa sem consulta** (H1, H6)
- O prompt v4 (`PROMPT_SISTEMA_V4`, `LEMBRETE_FERRAMENTA_V4`, `FERRAMENTAS_V4`) DEVE oferecer a ferramenta
  `conversar(mensagem)` para perguntas sem aeródromo. v1 a v3 continuam com o lembrete e as ferramentas de antes
  (a avaliação troca os três juntos).
- QUANDO o modelo chamar `conversar` **sozinha** e antes de qualquer consulta, o agente DEVE encerrar o laço e usar
  `mensagem` como texto da conversa. Se `conversar` vier junto com outra ferramenta ou depois de uma consulta, o
  agente DEVE ignorá-la e devolver um erro ao modelo (conta no limite de 5 chamadas).
- QUANDO, depois do lembrete do REQ-A-05, o modelo responder de novo sem ter chamado **nenhuma** ferramenta,
  o texto também vira conversa.
- Nos dois casos, SE a pergunta não estiver no tema (`harness.pergunta_no_tema`, REQ-H-16), o agente DEVE
  descartar o texto do modelo e responder `RECUSA` com o motivo `fora_do_tema` (passo `conversa` com
  `regra = "fora_do_tema"`). Senão, DEVE passar o texto pela trava de conversa (REQ-H-16) e registrar o passo
  `conversa` no traço (`passou`, `regra`, `trecho`).
- Assunto desconexo óbvio (integral, código, receita…) já é recusado antes do modelo pelo pré-filtro
  (REQ-H-13, categoria `fora_do_tema`).
- SE a trava não pegar nada, ENTÃO o agente DEVE responder `veredito = "CONVERSA"`, `avaliacoes = []`,
  `explicacao` = texto do modelo e `origem_explicacao = "modelo"`.
- SE a trava pegar algo, ou se alguma ferramenta foi chamada (mesmo sem sucesso), ENTÃO vale o REQ-A-05: `RECUSA`
  `sem_avaliacao`, com o texto descartado.
- A interface DEVE mostrar `CONVERSA` como balão de texto, sem cartão de veredito, sem aeródromos e sem previsão.
- Teste ao vivo em 13/11/2026 (v4): "Oi, tudo bem?", "O que significa VMC?" e "Como você funciona?" → `CONVERSA`
  (2–14 s); "Dá pra ir VFR em Guarulhos agora?" → `buscar_metar(SBGR)`, VMC.
- Na avaliação (`avaliacao/avaliar.py`), `CONVERSA` conta como "sem veredito": recusa correta nas perguntas de
  recusa e falsa recusa nas normais. O juiz não avalia `CONVERSA`.

### Requisito alterado

**REQ-A-05** — o segundo item passa a valer só quando o REQ-A-16 não se aplica.

### Limite (AI Assurance)

A trava é por regras (códigos de 4 letras, grupos de METAR, as expressões do verificador nos dois sentidos e frases
de ir/não ir). Uma paráfrase pode passar e afirmar condição sem consulta, do mesmo jeito que no verificador de
contradição. O texto aparece como conversa, sem cartão de veredito.

A lista de termos do tema também é por regras: uma pergunta desconexa que use uma palavra da lista ("tempo",
"previsão") chega à conversa. O texto ainda passa pela trava e não vira veredito. E uma pergunta legítima sem
nenhum termo da lista é recusada como fora do tema.

O modelo também pode escolher `conversar` numa pergunta que cita aeródromo e não consultar nada (falsa recusa, sem
risco de veredito errado). Por isso a avaliação compara v3 × v4 (`avaliacao/resultados_v4/`).

### Avaliação v3 × v4 (13/11/2026, `avaliacao/resultados_v4/`, mesmo conjunto fixo de dados)

| Métrica | v3 | v4 |
|---|---|---|
| ICAO exato | 6/14 | 8/14 |
| Recusa correta (12 casos, com R11 e R12 novos) | 10/12 | 12/12 |
| Falsa recusa | 4/14 | 5/14 |
| Tempo médio por pergunta | 22,1 s | 27,9 s |

Nenhuma pergunta normal caiu em `conversar`. A falsa recusa a mais vem da escolha de ICAO (P14: Joinville → SBJJ).
No v3, "Quanto é 15 vezes 23?" (R12) consultou SBSP e mostrou **IMC**, e "Como está o tempo?" (R09) mostrou VMC de
SBGR. No v4, o R12 é recusado como fora do tema e o R09 vira conversa ("Qual aeródromo você gostaria de
consultar?"). A trava aceita as siglas ICAO, IATA, ANAC, ATIS e AFIS: um teste ao vivo mostrou "código ICAO" sendo
barrado como se fosse aeródromo. Esse ajuste veio depois da rodada e só deixa passar mais conversa.
