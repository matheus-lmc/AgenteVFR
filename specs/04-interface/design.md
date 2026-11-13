# 04 — Interface e Docker: design

> **Nota (13/11/2026):** desde a spec 09 (interface em chat), DD1, DD5, DD7, DD9, DD16 e DD17 valem para a página
> anterior, servida em `/classico`. A página principal segue `specs/09-chat/design.md`.

**Estado:** aprovado em 10/11/2026 (variações visuais em escolha, seção 8) · **Requisitos:** [requisitos.md](requisitos.md) (aprovado)

Direção visual pesquisada com a skill **UI UX Pro Max** (`.claude/skills/ui-ux-pro-max`, consulta
`"aviation weather safety tool dashboard" --design-system`, dials variance 3 / motion 2 / density 6, e buscas
`--domain ux` sobre cor, carregamento, região viva e conteúdo recolhível).

## 1. Decisões de design para validar

| ID | Decisão | Origem | Alternativa descartada |
|---|---|---|---|
| DD1 | **Estilo "Apple" discreto** (revisão de 10/11/2026): tipografia SF/`-apple-system`, cartões agrupados com cantos de 10 px (8 px em campos, botões e chips) e sombra suave no lugar de bordas, material translúcido na faixa de aviso; sem enfeite além do fundo (DD16) | skills `apple-design` e `emil-design-eng` | "Minimalism & Swiss" original (grade, bordas, alto contraste) |
| DD2 | **Não usar o padrão "Hero-Centric"** sugerido pela skill | ajuste nosso | hero de landing page: a página é ferramenta, não vitrine |
| DD3 | **Paleta**: base da skill (azul-céu + âmbar) + cores semânticas do veredito, todas conferidas no contraste (seção 4) | skill + cálculo WCAG | primário da skill `#0284C7` atrás de texto branco (4,10:1, reprovado) |
| DD4 | **Tipografia do sistema** (`system-ui` no texto; `ui-monospace` em METAR, ICAO e traço) | D2 (sem recurso externo) | Fira Sans/Fira Code do Google Fonts, sugeridas pela skill |
| DD5 | **Tema claro por padrão; escuro opcional** (botão no cabeçalho, lembrado no navegador; não segue o `prefers-color-scheme`, para o projetor da sala sempre abrir claro). Contrastes do escuro conferidos (≥ 4,5:1 no texto) | escolha do grupo, 10/11/2026 | só tema claro; escuro automático |
| DD6 | **Ícones SVG embutidos** + texto ao lado (✓ VMC, ⨯ IMC, ⊘ RECUSA desenhados em SVG, nunca emoji) | skill (sem emoji; cor não é o único sinal) | só cor |
| DD7 | **Movimento curto e discreto**: pressão do botão `scale(.97)` em 120 ms, entrada do resultado em 220 ms (`opacity` + `translateY(8px)`, `cubic-bezier(0.23,1,0.32,1)`), só `transform`/`opacity`/cores; nada em ação de teclado; tudo desligado com `prefers-reduced-motion`; `prefers-reduced-transparency` e `prefers-contrast: more` tratados | skills + REQ-I-15 | scroll reveal/GSAP |
| DD8 | **Coluna única, até 880 px**, nesta ordem: aviso → pergunta → veredito → aeródromos consultados → explicação → traço → execuções gravadas | nosso (leitura de cima para baixo na apresentação) | duas colunas |
| DD9 | **Aviso fixo como faixa translúcida (blur) no topo, presa ao rolar**; sólida com `prefers-reduced-transparency` | REQ-I-14 | rodapé (some ao rolar); faixa âmbar chapada (versão anterior) |
| DD10 | **Painéis recolhíveis com `<details>`/`<summary>` nativos** (teclado e leitor de tela de graça) | skill (acessibilidade) | componente próprio em JS |
| DD11 | **Veredito: selo grande + números lado a lado** (escolha 1C): selo colorido com ícone e palavra; ao lado, teto e visibilidade contra o mínimo; o cartão é a região `aria-live` | REQ-I-08, escolha visual | cartão inteiro colorido (1A); cartão branco com faixa (1B) |
| DD12 | **Aeródromos consultados: um cartão por aeródromo, nome da estação em destaque** (escolha 2B), com faixa lateral na cor do veredito, ICAO ao lado do nome, teto, visibilidade e METAR; título "confira se é o que você pediu" | H7/H8, escolha visual | tabela (2A) |
| DD13 | **Bloqueio: antes × depois** (escolha 3B): alerta âmbar com a regra; o texto que o modelo escreveu aparece riscado, com o trecho marcado; abaixo, o texto gerado pelo sistema | REQ-I-10, escolha visual | só alerta + texto do sistema (3A) |
| DD14 | **Espera: cartão no lugar do resultado** (escolha 5B) com "Consultando… N s" e uma frase explicando o que está acontecendo; botão desabilitado | escolha visual | contador só no botão (5A) |
| DD15 | **Versões**: `fastapi==0.162.0` (23/10), `uvicorn==0.54.0` (25/09), `pydantic==2.14.1` (11/10), imagem `python:3.12.15-slim` | regra das 2 semanas | versões mais novas (menos de 2 semanas) |
| DD16 | **Fundo decorativo único**: um SVG de traço fino (uma nuvem e um avião cruzando), fixo no canto inferior direito, 11–12 % de opacidade, `aria-hidden`, sem interação, escondido com `prefers-contrast: more`. A carta sinótica da primeira versão foi tirada (poluía) | pedido do grupo, 10/11/2026 | rosa dos ventos com avião; carta sinótica |
| DD17 | **Logo do grupo no cabeçalho** (`docs/imagens/logo_com_fundo.jpeg` → PNG de fundo transparente, ~70 KB, embutido na página como `data:`; segue valendo REQ-I-16). Feita para o escuro; no tema claro a página inverte a luminosidade mantendo o matiz (`filter: invert(1) hue-rotate(180deg)`). Fica dentro do `<h1>` com `alt` "AgenteVFR — meteorologia de aviação" | pedido do grupo, 10/11/2026 | texto "AgenteVFR"; faixa escura só para a logo |

## 2. Arquivos

```
app/main.py               # criar_app(); rotas
app/static/index.html     # página única (HTML + CSS + JS)
tests/test_main.py        # rotas com agente falso (TestClient)
Dockerfile
.dockerignore             # .venv, .git, .claude, tests, specs, traces
docker-compose.yml        # + serviço app
requirements.txt          # + fastapi, uvicorn, pydantic
```

## 3. API (`app/main.py`)

```python
def criar_app(*, agente=None, pasta_traces: Path | None = None, pasta_demo: Path | None = None,
              verificar_saude: Callable[[], dict] | None = None) -> FastAPI
app = criar_app()   # usado pelo uvicorn
```

| Rota | Comportamento |
|---|---|
| `GET /` | `FileResponse(app/static/index.html)` |
| `POST /api/perguntar` | corpo validado por `class Pergunta(BaseModel): pergunta: StrictStr` (número ou `null` → 422); `agente.perguntar()` → `para_dict()`; exceção → 500 `{"erro": "falha interna ao processar a pergunta"}` |
| `GET /api/traco/{id}` | `re.fullmatch(r"[0-9a-f]{12}", id)` **antes** de qualquer acesso ao disco; procura `*_{id}.json` em `pasta_traces` e `pasta_demo`; senão 404 |
| `GET /api/demo` | lista `{id, pergunta, veredito, inicio}` dos traços de `pasta_demo`, do mais novo para o mais antigo |
| `GET /api/saude` | `GET {OLLAMA_URL}/api/tags` com tempo limite de 5 s → `{ollama, modelo, modelo_baixado}`; qualquer falha → `ollama: false` |

`pasta_traces` padrão = `TRACES_DIR` ou `traces/`; `pasta_demo` padrão = `<pasta_traces>/demo`.
Um único `Agente` por processo (D6), criado em `criar_app`.

## 4. Tokens visuais (CSS)

| Token | Valor | Contraste conferido |
|---|---|---|
| `--fundo` | `#F0F9FF` | — |
| `--cartao` | `#FFFFFF` | — |
| `--texto` | `#0F172A` | 16,75:1 sobre `--fundo` |
| `--texto-apagado` | `#475569` | 7,11:1 sobre `--fundo` |
| `--borda` | `#64748B` | ≥ 3:1 (componentes) — troca o `#94A3B8` da skill, que dava 2,56:1 |
| `--primario` (botão) | `#0369A1` + texto branco | 5,93:1 |
| `--foco` | contorno 3 px `#0369A1` | 5,57:1 |
| `--vmc` | `#15803D` + texto branco | 5,02:1 |
| `--imc` | `#B91C1C` + texto branco | 6,47:1 |
| `--recusa` | `#475569` + texto branco | 7,58:1 |
| `--aviso` | `#F59E0B` + texto `#0F172A` | 8,31:1 |
| `--bloqueio` | fundo `#FEF3C7`, texto `#78350F` | 8,15:1 |
| `--erro` | fundo `#FEE2E2`, texto `#7F1D1D` | 8,20:1 |

Espaçamento em múltiplos de 8 px; texto base 16 px, altura de linha 1,5; alvos clicáveis ≥ 44 px (exceção pedida pelo grupo: chips de exemplo e execuções gravadas com 34 px, fonte 13 px).

## 5. Página: comportamento

- **Envio:** `fetch` com `AbortController` de 330 s; contador de segundos no botão; campo e exemplos
  desabilitados durante a espera.
- **Renderização:** só `document.createElement` + `textContent` para dados da resposta e do traço; nenhum
  `innerHTML` com dado (REQ-I-11). Os SVG dos ícones são fixos no HTML.
- **Veredito:** classe CSS escolhida pelo campo `veredito` (`VMC`/`IMC`/`RECUSA`); qualquer outro valor → erro.
- **Traço (escolha 6B — tabela compacta):** ao abrir o `<details>`, busca `/api/traco/{id}` uma vez e monta uma
  tabela `t | passo | resultado | tokens`; cada linha tem um `<details>` com o conteúdo completo (mensagens da
  janela, argumentos, JSON) em `<pre>`; linhas com `passou: false` ou `erro` em destaque.
- **Execuções gravadas:** lista de `/api/demo`; ao clicar, monta o resultado a partir de `traco.resposta` e
  mostra a etiqueta "Execução gravada em <data/hora UTC>".
- **Saúde:** ao carregar, `GET /api/saude`; selo no cabeçalho "Modelo pronto" / "Ollama indisponível".

## 6. Docker

- `Dockerfile`: `python:3.12.15-slim`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`, usuário `app`
  (uid 1000), `pip install --no-cache-dir -r requirements.txt`, copia só `app/`,
  `CMD uvicorn app.main:app --host 0.0.0.0 --port 8000`.
- Compose, serviço `app`: `build: .`, `depends_on: ollama (service_healthy)`, ambiente
  `OLLAMA_URL=http://ollama:11434`, `OLLAMA_MODEL=llama3.1:8b`, `OLLAMA_NUM_THREAD=4`, `TRACES_DIR=/app/traces`;
  volume `./traces:/app/traces`; porta `127.0.0.1:8000:8000`.

## 7. Plano de testes

`tests/test_main.py` com `fastapi.testclient.TestClient`, agente falso e traços em `tmp_path`.

| Requisito | Testes previstos |
|---|---|
| I-01 | `GET /` → 200, `text/html`, contém o aviso fixo e `lang="pt-BR"` |
| I-02 | pergunta → resposta do agente falso; RECUSA também é 200; sem `pergunta`, número, `null` → 422 sem chamar o agente; exceção → 500 sem pilha |
| I-03 | traço existente → JSON; inexistente → 404; `../etc/passwd`, `ABCDEF012345`, 11 ou 13 caracteres → 404 sem tocar no disco |
| I-04 | `/api/demo` lista em ordem; traço de `demo/` abre por `/api/traco/{id}` |
| I-05 | saúde com Ollama falso ok / sem o modelo / fora do ar → valores corretos, nunca exceção |
| I-11 | `index.html` sem `innerHTML` recebendo dado (checagem textual: nenhuma ocorrência de `innerHTML =`) |
| I-16 | `index.html` sem `http://`/`https://` em `src`, `href` ou `@import` |
| I-07–I-15 | conferência no navegador do app (capturas em 360 px e 1280 px, teclado, os 3 exemplos, execução gravada, Ollama desligado) |
| I-17–I-19 | `docker compose up`; 5 perguntas pela página; tempo médio registrado |

## 8. Escolhas visuais (10/11/2026, companheiro visual do superpowers)

| Grupo | Escolha | Opção descartada |
|---|---|---|
| 1. Cartão do veredito | **C — selo grande + teto e visibilidade contra o mínimo** | A cartão cheio colorido; B cartão branco com faixa |
| 2. Aeródromos consultados | **B — um cartão por aeródromo, nome da estação em destaque** | A tabela |
| 3. Bloqueio do verificador | **B — antes × depois (texto do modelo riscado + texto do sistema)** | A só alerta + texto do sistema |
| 4. Aviso fixo | **A — faixa âmbar presa no topo** | B linha discreta repetida junto do veredito |
| 5. Espera | **B — cartão de espera no lugar do resultado, explicando o que acontece** | A contador só no botão |
| 6. Traço da execução | **B — tabela compacta** (cada linha expande o conteúdo) | A linha do tempo vertical |

Mockups em `.superpowers/brainstorm/` (fora do git).

**Consequência da escolha 3B:** a resposta do agente (`RespostaAgente`) não traz o texto bloqueado — só
`bloqueio = {regra, trecho}`. A página busca o texto original no traço (`/api/traco/{id}`, conteúdo da última
resposta do passo `modelo`, formato definido no REQ-A-13). Se o traço não abrir, mostra só o trecho. O módulo 03
não muda.
