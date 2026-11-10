# 04 — Interface e Docker: requisitos

**Estado:** aprovado em 10/11/2026 · **Módulos:** `app/main.py`, `app/static/index.html`, `Dockerfile`, `docker-compose.yml` ·
**Testes:** `tests/test_main.py` + conferência no navegador

## 1. Objetivo e escopo

Pôr o agente na frente do piloto (e da banca): uma página que faz a pergunta, mostra o veredito **calculado em
código**, a explicação, o que foi consultado e o traço da execução. Tudo sobe com `docker compose up`.

**Fora do escopo:** janela pelo TAF (módulo 05); autenticação, múltiplos usuários, hospedagem pública.

## 2. Perigos mitigados

| Perigo | Como a interface mitiga |
|---|---|
| H1 (VMC quando é IMC) | o veredito exibido é o campo `veredito` da resposta, nunca lido do texto do modelo |
| H3 (explicação contradiz) | bloqueio do verificador aparece em destaque, com a regra |
| H7 (aeródromo errado) / H8 (aeródromo omitido) | **só transparência**: lista visível dos aeródromos consultados, com ICAO e nome da estação |
| H9 (novo) — texto do modelo executado como código na página | o texto do modelo é sempre exibido como texto, nunca como HTML |

## 3. Requisitos

### API (FastAPI)

**REQ-I-01 — Página**
- `GET /` DEVE responder 200 com `app/static/index.html` (`text/html`).

**REQ-I-02 — Pergunta**
- `POST /api/perguntar` com corpo `{"pergunta": "<texto>"}` DEVE chamar o agente e responder 200 com
  `RespostaAgente.para_dict()` — inclusive quando o veredito é `RECUSA`.
- SE o corpo não tiver `pergunta` em texto, ENTÃO a API DEVE responder 422 sem chamar o agente.
  (Pergunta vazia ou longa demais é texto válido: quem recusa é o agente, REQ-A-01.)
- SE o agente lançar exceção, ENTÃO a API DEVE responder 500 com `{"erro": "<mensagem curta>"}`, sem expor a
  pilha de chamadas. (O traço já é gravado pelo agente, REQ-A-13.)

**REQ-I-03 — Traço**
- `GET /api/traco/{id}` DEVE devolver o JSON do traço `*_{id}.json` da pasta de traços.
- SE `id` não casar `^[0-9a-f]{12}$`, ENTÃO a API DEVE responder 404 **sem acessar o disco** (impede ler outro
  arquivo, ex.: `../../etc/passwd`).
- SE o traço não existir, ENTÃO a API DEVE responder 404.

**REQ-I-04 — Execuções gravadas** *[Decisão D1]*
- `GET /api/demo` DEVE listar os traços de `traces/demo/` (id, pergunta, veredito, início), e
  `GET /api/traco/{id}` DEVE encontrá-los também.

**REQ-I-05 — Saúde** *[Decisão D3]*
- `GET /api/saude` DEVE informar se o Ollama responde e se o modelo configurado está baixado
  (`{"ollama": bool, "modelo": "<nome>", "modelo_baixado": bool}`), em até 5 s, sem lançar exceção.

**REQ-I-06 — Configuração**
- A aplicação DEVE ser criada por uma fábrica (`criar_app(agente=..., pasta_traces=...)`) para os testes
  injetarem um agente falso; o padrão usa o `Agente` real e `TRACES_DIR`.

### Página (`app/static/index.html`, HTML + CSS + JS puro)

**REQ-I-07 — Pergunta e exemplos**
- A página DEVE ter campo de pergunta (máximo 500 caracteres, contador visível) e botão; Enter envia.
- A página DEVE ter exemplos clicáveis que preenchem e enviam: "Dá pra ir VFR em Congonhas agora?",
  "Posso decolar de Congonhas mesmo assim?" e "Qual o melhor dia pra ir pra Miami nos próximos 5 dias?".
- ENQUANTO a resposta não chega, a página DEVE desabilitar o envio e mostrar "consultando…" com os segundos
  decorridos (uma pergunta leva ~15–40 s na CPU).

**REQ-I-08 — Veredito** (H1)
- A página DEVE mostrar o veredito em destaque: **VMC** (verde), **IMC** (vermelho), **RECUSA** (cinza), com o
  motivo logo abaixo.
- O veredito exibido DEVE vir só do campo `veredito` da resposta. A página NÃO DEVE inferir veredito do texto.
- A cor NÃO DEVE ser o único sinal: o veredito aparece escrito e com ícone (acessibilidade).

**REQ-I-09 — O que foi consultado** (H7, H8)
- A página DEVE listar cada aeródromo avaliado como `ICAO — nome da estação — veredito`, com teto, visibilidade e
  METAR bruto (fonte monoespaçada).
- QUANDO nenhum aeródromo tiver sido consultado, a página DEVE dizer isso explicitamente.

**REQ-I-10 — Explicação e bloqueio** (H3)
- A página DEVE mostrar a explicação e de onde ela veio: "Explicação do modelo" ou "Texto gerado pelo sistema".
- QUANDO houver `bloqueio`, a página DEVE destacar que a explicação do modelo foi bloqueada, com a regra e o trecho.

**REQ-I-11 — Texto do modelo como texto** (H9)
- Todo conteúdo vindo da resposta ou do traço DEVE ser inserido como texto (`textContent`), nunca como HTML.

**REQ-I-12 — Traço da execução**
- A página DEVE ter um painel recolhível "Traço da execução" que busca `/api/traco/{id}` e mostra, em ordem: tipo do
  passo, tempo, e o conteúdo de cada um (mensagens que entraram na janela, contagem de tokens, chamadas de
  ferramenta com argumentos e janela devolvida, checagens do harness e do verificador).
- Passos que bloquearam ou falharam (`passou: false`, `erro`) DEVEM aparecer em destaque.

**REQ-I-13 — Execuções gravadas na página** *[Decisão D1]*
- A página DEVE oferecer as execuções gravadas (`/api/demo`), que abrem o resultado e o traço sem chamar o modelo —
  plano B da apresentação se a rede ou o Ollama falharem. Elas DEVEM vir marcadas como "gravada em <data/hora>".

**REQ-I-14 — Avisos e erros**
- O aviso "Ferramenta acadêmica. Não substitui o briefing meteorológico oficial." DEVE ficar sempre visível.
- SE a chamada à API falhar (rede, 500, tempo esgotado no navegador > 330 s), ENTÃO a página DEVE mostrar uma
  mensagem de erro que **não** se parece com veredito.
- A página DEVE mostrar o estado de `/api/saude` (Ollama/modelo pronto ou indisponível).

**REQ-I-15 — Acessibilidade e idioma**
- `lang="pt-BR"`; contraste mínimo WCAG AA; tudo operável por teclado com foco visível; resultado anunciado por
  `aria-live`; respeitar `prefers-reduced-motion`; legível de 360 px de largura em diante.

**REQ-I-16 — Sem recursos externos** *[Decisão D2]*
- A página NÃO DEVE carregar nada de fora (CDN, fonte web, script de terceiros): funciona sem internet, desde que
  o METAR já esteja em cache ou se use execução gravada.

### Docker

**REQ-I-17 — Imagem do app**
- `Dockerfile` com imagem Python de tag fixa, dependências de `requirements.txt` (versões fixadas), usuário sem
  privilégio de root, servindo `uvicorn app.main:app` na porta 8000.

**REQ-I-18 — Compose**
- O serviço `app` DEVE depender do `ollama` saudável e receber `OLLAMA_URL=http://ollama:11434`,
  `OLLAMA_MODEL`, `OLLAMA_NUM_THREAD=4` e `TRACES_DIR`; `./traces` montado no contêiner; porta publicada só em
  `127.0.0.1:8000`.
- `docker compose up` DEVE subir os dois serviços e a demo DEVE funcionar em `http://localhost:8000`.

**REQ-I-19 — Tempo por pergunta**
- O tempo médio por pergunta com tudo no Compose DEVE ser medido (≥ 5 perguntas) e registrado em `tarefas.md`
  para o artigo e o roteiro.

## 4. Decisões (confirmadas em 10/11/2026, opção proposta)

| ID | Decisão proposta | Alternativa | Efeito |
|---|---|---|---|
| D1 | Exemplos ao vivo: Congonhas, "mesmo assim", Miami. **IMC não tem exemplo ao vivo garantido** (depende do tempo real); execuções gravadas reais (`traces/demo/`) servem de plano B e para mostrar IMC quando a coleta pegar um | Inventar um METAR IMC para a demo | Nada fabricado na demo; o exemplo IMC depende de gravar uma execução real com tempo ruim |
| D2 | Nenhum recurso externo; fontes do sistema | Fonte web (Google Fonts) | Funciona offline na sala; tipografia menos escolhida |
| D3 | Endpoint `/api/saude` para a página saber se o Ollama/modelo está pronto | Sem checagem | Evita esperar 5 min por um modelo que não está carregado |
| D4 | Sem streaming: "consultando…" com segundos decorridos | Streaming de tokens | Mais simples; a resposta inteira passa pelo verificador antes de aparecer (o streaming mostraria texto ainda não verificado) |
| D5 | Página única em HTML/CSS/JS puro (como no CLAUDE.md), desenhada com a skill UI UX Pro Max | Framework (React etc.) | Sem etapa de build; menos dependências |
| D6 | Um único `Agente` por processo; rota síncrona (o FastAPI usa threads) | Fila/assíncrono | O Ollama atende uma pergunta por vez; para a demo basta |
