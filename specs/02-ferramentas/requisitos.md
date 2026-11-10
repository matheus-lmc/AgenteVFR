# 02 — Ferramentas: requisitos

**Estado:** aprovado em 10/11/2026 · **Módulo:** `app/ferramentas.py` · **Testes:** `tests/test_ferramentas.py`

## 1. Objetivo e escopo

As ferramentas buscam o METAR e o TAF de **um** aeródromo na API pública aviationweather.gov e devolvem o
texto bruto para o harness, junto com tudo o que o traço precisa para provar o que aconteceu.

| Função | Entrada | Saída |
|---|---|---|
| `buscar_metar` | ICAO (texto vindo do modelo) | resultado da busca: status, METAR bruto, JSON da API, metadados |
| `buscar_taf` | ICAO (texto vindo do modelo) | idem, com o TAF bruto |

**Fora do escopo deste módulo:** decidir VMC/IMC (harness, módulo 01); montar o que entra na janela do modelo
(agente, módulo 03); decodificar o TAF (módulo 05); coleta em lote para a avaliação (`avaliacao/`).

## 2. Fonte: o que foi confirmado na API (10/11/2026)

Schema OpenAPI oficial: `https://aviationweather.gov/data/schema/openapi.yaml` (v4.0), cópia em
[`openapi_aviationweather_v4.yaml`](openapi_aviationweather_v4.yaml).

| Pergunta | Resposta confirmada |
|---|---|
| Endpoint do METAR | `GET /api/data/metar?ids=<ICAO>&format=json` |
| Endpoint do TAF | `GET /api/data/taf?ids=<ICAO>&format=json` (pendência do CLAUDE.md resolvida) |
| Campo do texto bruto | METAR: `rawOb` (sem `=` no final); TAF: `rawTAF` |
| Sem `hours` | METAR: só o mais recente; com `hours=N`, lista do mais novo para o mais antigo |
| ICAO sem METAR (`SBXX`, `ZZZZ`, `SDCO`) | **HTTP 204, corpo vazio** |
| ICAO sem TAF | **HTTP 200, `[]`** |
| `ids` vazio ou malformado (`SB;GR`) | HTTP 400, `{"status":"error","error":"..."}` |
| Cache do servidor | `cache-control: max-age=60` |
| Chegada do METAR | 0,4–4,7 min **antes** da hora nominal (SBGR, 24 boletins) |
| Limite de uso (CLAUDE.md) | 100 req/min |

## 3. Perigos preliminares mitigados

H1 (VMC quando é IMC), H2 (dado desatualizado), H4 (fora do escopo) — ver módulo 01.
Novo neste módulo: **H5 — sistema apresenta dado inventado ou de outra fonte quando a API falha.**

## 4. Requisitos

### Entrada

**REQ-F-01 — Validação do ICAO antes da rede** (H4)
- A ferramenta DEVE remover espaços das pontas e converter para maiúsculas o ICAO recebido.
- SE o ICAO não tiver exatamente 4 letras (`^[A-Z]{4}$`), ENTÃO a ferramenta DEVE devolver `icao_invalido`
  **sem** chamar a API. (Impede que texto do modelo, como `SB;GR` ou `SBGR,KJFK`, vá parar na URL.)

**REQ-F-02 — Escopo antes da rede** (H4) *[Decisão D1]*
- SE o ICAO não começar por um dos prefixos de `harness.PREFIXOS_BR`, ENTÃO a ferramenta DEVE devolver
  `fora_do_escopo` sem chamar a API.
- A lista de prefixos DEVE ser a do harness (um só lugar no código).

### Chamada

**REQ-F-03 — Requisição** (H1)
- A ferramenta DEVE consultar um único ICAO por chamada, com `format=json`, na URL base de
  `AWC_BASE_URL` (padrão `https://aviationweather.gov/api/data`).
- A ferramenta DEVE enviar `User-Agent` genérico do projeto (`AgenteVFR/0.1 (projeto academico TE251)`),
  sem dado pessoal.
- A ferramenta DEVE usar tempo limite de `AWC_TIMEOUT_S` segundos (padrão 10).

**REQ-F-04 — Resposta com dado** (H1)
- QUANDO a API responder 200 com lista não vazia, a ferramenta DEVE usar o **primeiro** elemento e devolver
  `ok` com o texto de `rawOb` (METAR) ou `rawTAF` (TAF).
- SE o campo de texto bruto estiver ausente ou vazio, ENTÃO a ferramenta DEVE devolver `erro_api`.
- A ferramenta NÃO DEVE alterar o texto bruto (nada de completar, corrigir ou juntar boletins).

**REQ-F-05 — Sem dado** (H1, H5)
- QUANDO a API responder 204 ou 200 com `[]`, a ferramenta DEVE devolver `sem_dado`.

**REQ-F-06 — Falhas** (H5)
- SE houver tempo esgotado, erro de conexão, HTTP 4xx/5xx ou JSON inválido, ENTÃO a ferramenta DEVE devolver
  `erro_api` com a descrição do erro, sem lançar exceção para quem chamou.
- SE a API responder 429, ENTÃO a ferramenta DEVE devolver `limite_api`.
- QUANDO a falha for tempo esgotado, erro de conexão ou 5xx, a ferramenta DEVE tentar **uma** vez mais antes
  de desistir. *[Decisão D5]*
- Em nenhuma falha a ferramenta DEVE devolver texto de METAR/TAF (nem do cache vencido, nem inventado).

### Cache

**REQ-F-07 — Cache por ICAO** (H2)
- A ferramenta DEVE manter, em memória do processo, um cache por (tipo, ICAO) com validade de 5 min.
- Só resultados `ok` DEVEM ir para o cache. *[Decisão D2]*
- QUANDO houver entrada válida no cache, a ferramenta DEVE devolvê-la sem chamar a API e marcar `de_cache`.
- SE o METAR em cache tiver mais de 55 min desde a observação (campo `obsTime` da API), ENTÃO a ferramenta
  DEVE ignorar o cache e buscar de novo. *[Decisão D3]* O `obsTime` é usado só para isso; o veredito continua
  saindo do texto bruto (REQ-H-11).
- O relógio usado pelo cache DEVE ser injetável (testes sem espera real).

### Saída

**REQ-F-08 — Resultado da busca** (traço / Context Engineering)
- Toda chamada DEVE devolver um resultado com: `icao`, `tipo` (`metar`/`taf`), `status`, `texto_bruto`
  (ou `null`), `resposta_api` (JSON bruto, ou `null`), `url`, `http_status` (ou `null`), `de_cache`,
  `tentativas`, `buscado_em` (ISO 8601 UTC), `duracao_ms`, `erro` (ou `null`).
- `status` ∈ {`ok`, `sem_dado`, `icao_invalido`, `fora_do_escopo`, `erro_api`, `limite_api`}.
- `texto_bruto` e `resposta_api` DEVEM ficar em campos separados: o agente manda ao harness só o primeiro;
  o segundo vai só para o traço.

### Testabilidade

**REQ-F-09 — Testes sem rede**
- O cliente HTTP DEVE ser injetável, para os testes usarem transporte simulado (`httpx.MockTransport`).
- Os testes DEVEM usar respostas gravadas da API real (`tests/fixtures/awc/`): METAR e TAF de SBGR, 204,
  `[]`, 400. *[Decisão D6]*
- Um teste opcional contra a API real DEVE ficar marcado (`@pytest.mark.rede`) e fora da execução padrão.

## 5. Decisões (confirmadas em 10/11/2026, opção proposta)

| ID | Decisão proposta | Alternativa | Efeito |
|---|---|---|---|
| D1 | Recusar fora do escopo antes da rede, com os prefixos do harness | Buscar e deixar o harness recusar | `KMIA` sem METAR na API daria `sem_dado` em vez de `fora_do_escopo`; a proposta garante o motivo certo |
| D2 | Cachear só `ok` | Cachear também `sem_dado` por 1 min | Mais chamadas para ICAO inexistente, mas sem "esconder" um boletim que acabou de chegar |
| D3 | Cache ignora METAR com mais de 55 min | TTL fixo de 5 min | Evita recusa por idade causada pelo próprio cache |
| D4 | Sem limitador global de taxa; proteção = cache + 1 ICAO por chamada + máx. 2 tentativas | Contador de 90 req/min | Simples; a demo faz poucas chamadas. A coleta da avaliação controla o próprio ritmo |
| D5 | 1 nova tentativa em tempo esgotado, conexão ou 5xx | Sem nova tentativa | Demo mais robusta a uma falha pontual; no pior caso 2 × 10 s |
| D6 | Fixtures gravadas da API real; teste ao vivo opcional | Só fixtures escritas à mão | Testes refletem o formato real (ex.: `rawOb` sem `=`) |
| D7 | Cliente síncrono (`httpx.Client`) com `threading.Lock` no cache | Assíncrono (`httpx.AsyncClient`) | Mais simples de testar; o FastAPI roda rotas síncronas em threads |
