# 02 — Ferramentas: design

**Estado:** aprovado em 10/11/2026 · **Requisitos:** [requisitos.md](requisitos.md) (aprovado)

## 1. Princípios

- **Uma dependência só**: `httpx` (vai em `requirements.txt`, versão fixada). Nada de decisão meteorológica
  aqui; a única coisa importada do harness é `PREFIXOS_BR` (REQ-F-02).
- **Nunca lança exceção para o agente**: toda falha vira um `ResultadoBusca` com `status` e `erro` (REQ-F-06).
  A exceção é erro de programação (ex.: `tipo` desconhecido), que pode quebrar.
- **Tudo injetável**: cliente HTTP, relógio, URL base e tempo limite (REQ-F-07, REQ-F-09).
- **Síncrono** (D7): `httpx.Client`; o cache usa `threading.Lock` só para ler/gravar o dicionário, não durante
  a chamada de rede. Duas buscas simultâneas do mesmo ICAO podem ir à API duas vezes; é aceitável.

## 2. Arquivos

```
requirements.txt                    # httpx==0.28.1 (fastapi/pydantic entram no módulo 04)
app/ferramentas.py
tests/test_ferramentas.py
tests/fixtures/awc/metar_SBGR.json  # resposta real gravada (1 boletim)
tests/fixtures/awc/metar_SBGR_3h.json  # resposta real com hours=3 (3 boletins, mais novo primeiro)
tests/fixtures/awc/taf_SBGR.json
tests/fixtures/awc/erro_400.json
pyproject.toml                      # + marcador "rede", fora da execução padrão
```

## 3. API pública

```python
BASE_URL_PADRAO = "https://aviationweather.gov/api/data"
TIMEOUT_PADRAO_S = 10.0
USER_AGENT = "AgenteVFR/0.1 (projeto academico TE251)"
CACHE_TTL_S = 300               # 5 min (REQ-F-07)
CACHE_IDADE_MAX_METAR_MIN = 55  # D3
MAX_TENTATIVAS = 2              # D5
STATUS = {"ok", "sem_dado", "icao_invalido", "fora_do_escopo", "erro_api", "limite_api"}

@dataclass(frozen=True)
class ResultadoBusca:            # REQ-F-08 — os campos SÃO as chaves
    icao: str                   # já normalizado (ou o texto recebido, se inválido)
    tipo: str                   # "metar" | "taf"
    status: str
    texto_bruto: str | None     # vai para o harness
    resposta_api: list | dict | None   # vai só para o traço
    url: str | None             # URL completa com parâmetros; None se não houve chamada
    http_status: int | None
    de_cache: bool
    tentativas: int             # 0 = não chamou a API (validação ou cache)
    buscado_em: str             # ISO 8601 UTC, ex.: "2026-11-10T13:10:00Z"
    duracao_ms: int
    erro: str | None
    def para_dict(self) -> dict: ...

class ClienteAWC:
    def __init__(self, *, base_url: str | None = None, timeout_s: float | None = None,
                 http: httpx.Client | None = None,
                 relogio: Callable[[], datetime] = agora_utc): ...
    def buscar_metar(self, icao: str) -> ResultadoBusca: ...
    def buscar_taf(self, icao: str) -> ResultadoBusca: ...
    def limpar_cache(self) -> None: ...

# Atalhos usados pelo agente como ferramentas (instância padrão criada na primeira chamada)
def buscar_metar(icao: str) -> ResultadoBusca: ...
def buscar_taf(icao: str) -> ResultadoBusca: ...
```

`base_url` e `timeout_s` = `None` → lidos de `AWC_BASE_URL` e `AWC_TIMEOUT_S`, com os padrões acima.

## 4. Fluxo de `_buscar(tipo, icao)`

| # | Passo | Resultado | Tentativas |
|---|---|---|---|
| 1 | `icao.strip().upper()`; não casa `^[A-Z]{4}$` (ou não é `str`) | `icao_invalido` | 0 |
| 2 | não começa com `PREFIXOS_BR` | `fora_do_escopo` | 0 |
| 3 | entrada válida no cache (seção 5) | cópia com `de_cache=True` | 0 |
| 4 | `GET {base}/{tipo}?ids={ICAO}&format=json`, com `User-Agent` e `timeout` **em cada requisição** (vale também para cliente injetado) | — | 1 |
| 5 | tempo esgotado / erro de conexão (`httpx.TransportError`) ou HTTP 5xx → repete o passo 4 uma vez, sem espera | — | 2 |
| 6 | ainda falhou | `erro_api` (`erro` = tipo da exceção ou `HTTP 503`) | 1–2 |
| 7 | HTTP 429 | `limite_api` (sem nova tentativa) | 1 |
| 8 | HTTP 204 | `sem_dado` | 1–2 |
| 9 | outro 4xx | `erro_api` (`erro` = `HTTP 400: <campo "error" do JSON, se houver>`) | 1–2 |
| 10 | 200 com JSON inválido ou que não é lista | `erro_api` | 1–2 |
| 11 | 200 com `[]` | `sem_dado` | 1–2 |
| 12 | 200: primeiro elemento sem `rawOb`/`rawTAF`, vazio ou não-texto | `erro_api` | 1–2 |
| 13 | 200: primeiro elemento com texto | `ok`, `texto_bruto` = texto exato; grava no cache | 1–2 |

`resposta_api` guarda o JSON decodificado sempre que houver (inclusive no 400), para o traço.
`duracao_ms` mede do início do passo 1 ao fim (`time.perf_counter`), inclusive quando vem do cache.

## 5. Cache

- Dicionário `{(tipo, icao): (resultado, guardado_em)}` dentro da instância de `ClienteAWC`.
- Válido se `relogio() - guardado_em < CACHE_TTL_S` **e**, para METAR,
  `relogio() - obsTime ≤ 55 min` (`obsTime` = epoch do primeiro elemento de `resposta_api`).
  METAR sem `obsTime` legível → cache ignorado (busca de novo).
- Ao servir do cache: `dataclasses.replace(resultado, de_cache=True, tentativas=0, buscado_em=agora,
  duracao_ms=...)`. `texto_bruto`, `resposta_api`, `url` e `http_status` são os da busca original.
- Só `ok` entra no cache (D2). Uma falha depois do cache vencer **não** devolve o conteúdo antigo.

## 6. Plano de testes

Transporte simulado: `httpx.MockTransport(handler)`, com o handler registrando cada requisição (para contar
chamadas e conferir URL, parâmetros e cabeçalhos). Relógio falso ajustável. Agora padrão dos testes:
`2026-11-10T13:10:00Z` (10 min depois do `obsTime` da fixture de SBGR).

| Requisito | Testes previstos |
|---|---|
| F-01 | `" sbgr "` normaliza para `SBGR`; `SB;GR`, `SBGR,KJFK`, `SBG`, `SBGR1`, `""`, `None` → `icao_invalido` **com 0 requisições** |
| F-02 | `KMIA`, `KJFK`, `SAEZ` → `fora_do_escopo` com 0 requisições; prefixos vêm de `harness.PREFIXOS_BR` |
| F-03 | caminho `/api/data/metar` e `/api/data/taf`; parâmetros `ids` e `format=json`; `User-Agent` do projeto; `AWC_BASE_URL` e `AWC_TIMEOUT_S` do ambiente; timeout aplicado na requisição |
| F-04 | METAR `ok` com `rawOb` exato; TAF `ok` com `rawTAF`; lista com 3 boletins usa o primeiro; `rawOb` ausente / vazio / não-texto → `erro_api` |
| F-05 | 204 → `sem_dado`; `[]` → `sem_dado` |
| F-06 | tempo esgotado 2× → `erro_api`, 2 tentativas; tempo esgotado e depois 200 → `ok`, 2 tentativas; 500 e depois 200 → `ok`; 500 2× → `erro_api`; 429 → `limite_api`, 1 tentativa; 400 → `erro_api` com a mensagem da API, 1 tentativa; JSON inválido → `erro_api`; JSON objeto (não lista) → `erro_api`; nenhuma falha lança exceção nem tem `texto_bruto` |
| F-07 | 2ª chamada em 4 min → cache (1 requisição); em 6 min → nova requisição; METAR com 56 min desde `obsTime` ignora cache; TAF não tem a regra dos 55 min; `sem_dado` e `erro_api` não vão para o cache; METAR e TAF do mesmo ICAO não se misturam; falha depois do cache vencer não devolve o texto antigo; `limpar_cache` |
| F-08 | chaves exatas de `para_dict()` em `ok`, `sem_dado`, `icao_invalido`, `erro_api`; `status` ∈ `STATUS`; `buscado_em` em ISO com `Z`; `duracao_ms` inteiro ≥ 0; `url` com `ids=SBGR`; `resposta_api` = lista da fixture |
| F-09 | atalhos `buscar_metar`/`buscar_taf` usam a instância padrão; teste ao vivo `@pytest.mark.rede` (SBGR `ok`) fora da execução padrão |

Estimativa: ~45 testes.
