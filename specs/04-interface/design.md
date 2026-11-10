# 04 — Interface e Docker: design

**Estado:** aprovado em 10/11/2026 (variações visuais em escolha, seção 8) · **Requisitos:** [requisitos.md](requisitos.md) (aprovado)

Direção visual pesquisada com a skill **UI UX Pro Max** (`.claude/skills/ui-ux-pro-max`, consulta
`"aviation weather safety tool dashboard" --design-system`, dials variance 3 / motion 2 / density 6, e buscas
`--domain ux` sobre cor, carregamento, região viva e conteúdo recolhível).

## 1. Decisões de design para validar

| ID | Decisão | Origem | Alternativa descartada |
|---|---|---|---|
| DD1 | **Estilo "Minimalism & Swiss"**: limpo, grade, alto contraste, sem enfeite | skill (indicado para ferramentas profissionais/dashboards) | — |
| DD2 | **Não usar o padrão "Hero-Centric"** sugerido pela skill | ajuste nosso | hero de landing page: a página é ferramenta, não vitrine |
| DD3 | **Paleta**: base da skill (azul-céu + âmbar) + cores semânticas do veredito, todas conferidas no contraste (seção 4) | skill + cálculo WCAG | primário da skill `#0284C7` atrás de texto branco (4,10:1, reprovado) |
| DD4 | **Tipografia do sistema** (`system-ui` no texto; `ui-monospace` em METAR, ICAO e traço) | D2 (sem recurso externo) | Fira Sans/Fira Code do Google Fonts, sugeridas pela skill |
| DD5 | **Só tema claro** | projetor da sala | modo escuro automático (`prefers-color-scheme`) |
| DD6 | **Ícones SVG embutidos** + texto ao lado (✓ VMC, ⨯ IMC, ⊘ RECUSA desenhados em SVG, nunca emoji) | skill (sem emoji; cor não é o único sinal) | só cor |
| DD7 | **Sem animação de rolagem nem GSAP**; só transições CSS de 150–200 ms, desligadas com `prefers-reduced-motion` | skill (motion 2) + D2 | "scroll reveal" com GSAP sugerido pela skill |
| DD8 | **Coluna única, até 880 px**, nesta ordem: aviso → pergunta → veredito → aeródromos consultados → explicação → traço → execuções gravadas | nosso (leitura de cima para baixo na apresentação) | duas colunas |
| DD9 | **Aviso fixo como faixa âmbar no topo, presa ao rolar** | REQ-I-14 | rodapé (some ao rolar) |
| DD10 | **Painéis recolhíveis com `<details>`/`<summary>` nativos** (teclado e leitor de tela de graça) | skill (acessibilidade) | componente próprio em JS |
| DD11 | **Veredito em cartão grande** com a cor do veredito, ícone, palavra (VMC/IMC/RECUSA) e motivo; o cartão é a região `aria-live` | REQ-I-08, skill (região viva com mensagem completa) | só um selo pequeno |
| DD12 | **"Aeródromos consultados" como tabela** (ICAO, estação, veredito, teto, visibilidade, METAR) logo abaixo do veredito, com aviso "Confira se é o aeródromo que você pediu" | H7/H8 | esconder dentro do traço |
| DD13 | **Bloqueio do verificador como alerta âmbar** acima da explicação: "A explicação do modelo foi bloqueada (regra …, trecho …). Abaixo, texto gerado pelo sistema." | REQ-I-10 | só um ícone |
| DD14 | **Espera**: botão vira "Consultando… 12 s" com contador; resto da página continua legível | skill (espera longa explicada) | spinner sem tempo |
| DD15 | **Versões**: `fastapi==0.162.0` (23/10), `uvicorn==0.54.0` (25/09), `pydantic==2.14.1` (11/10), imagem `python:3.12.15-slim` | regra das 2 semanas | versões mais novas (menos de 2 semanas) |

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

Espaçamento em múltiplos de 8 px; texto base 16 px, altura de linha 1,5; alvos clicáveis ≥ 44 px.

## 5. Página: comportamento

- **Envio:** `fetch` com `AbortController` de 330 s; contador de segundos no botão; campo e exemplos
  desabilitados durante a espera.
- **Renderização:** só `document.createElement` + `textContent` para dados da resposta e do traço; nenhum
  `innerHTML` com dado (REQ-I-11). Os SVG dos ícones são fixos no HTML.
- **Veredito:** classe CSS escolhida pelo campo `veredito` (`VMC`/`IMC`/`RECUSA`); qualquer outro valor → erro.
- **Traço:** ao abrir o `<details>`, busca `/api/traco/{id}` uma vez; cada passo vira um cartão com tipo, tempo e
  conteúdo; mensagens da janela e JSON em `<pre>` recolhível; passos com `passou: false` ou `erro` em vermelho/âmbar.
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
