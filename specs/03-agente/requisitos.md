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
módulos 01 e 02. Novo neste módulo: **H6 — sistema dá resposta sem ter consultado dado algum.**

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

### Modelo e prompt

**REQ-A-11 — Chamada ao Ollama** (reprodutibilidade)
- O agente DEVE chamar `POST {OLLAMA_URL}/api/chat` com `stream: false`, as ferramentas, `temperature` de
  `OLLAMA_TEMPERATURA` (padrão 0.1) e `seed` fixa (42).
- URL, modelo, temperatura e tempo limite DEVEM vir de variáveis de ambiente (`OLLAMA_URL`
  padrão `http://localhost:11434`, `OLLAMA_MODEL` padrão `llama3.1:8b`).

**REQ-A-12 — Prompt de sistema versionado** (Prompt Engineering)
- O prompt de sistema DEVE ficar em `app/prompts.py` como constante com identificador de versão
  (ex.: `PROMPT_SISTEMA_V1`), e o traço DEVE registrar qual versão foi usada.
- O prompt DEVE instruir o modelo a: consultar `buscar_metar` para cada aeródromo citado; usar o campo
  `veredito` sem recalculá-lo; citar teto, visibilidade e o METAR das ferramentas; não inventar dados; responder
  em português, em até 4 frases; lembrar que não substitui o briefing oficial.
- O prompt NÃO DEVE conter tabela de nomes → ICAO. *[Decisão D5]* (O mapeamento é o que o modelo decide e é
  medido na avaliação.)

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
