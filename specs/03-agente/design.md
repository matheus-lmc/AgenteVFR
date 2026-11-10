# 03 — Agente, prompt e traço: design

**Estado:** aprovado em 10/11/2026 · **Requisitos:** [requisitos.md](requisitos.md) (aprovado)

## 1. Princípios

- **O modelo propõe, o código dispõe**: o loop só deixa o modelo escolher ferramenta, argumento e texto.
  Veredito, recusa, bloqueio e limite saem de código (harness + agente).
- **Sem dependência nova**: Ollama via `httpx` (`POST /api/chat`), como nas ferramentas.
- **Tudo injetável**: cliente do Ollama, funções de busca, relógio e pasta de traços (REQ-A-14).
- **O traço é gravado sempre**, inclusive se uma exceção inesperada escapar (bloco `finally`).

## 2. Arquivos

```
app/prompts.py        # VERSAO_PROMPT, PROMPT_SISTEMA_V1, LEMBRETE_FERRAMENTA, FERRAMENTAS (schemas)
app/traco.py          # Traco: acumula passos e grava traces/<AAAAMMDDTHHMMSSZ>_<id>.json
app/agente.py         # ClienteOllama, Agente, RespostaAgente
tests/test_agente.py  # loop com modelo roteirizado e ferramentas falsas
tests/test_traco.py
tests/test_prompts.py
pyproject.toml        # + marcador "ollama", fora da execução padrão
```

## 3. Formato do Ollama (`/api/chat`, não-streaming)

> A confirmar contra o Ollama 0.40.11 real assim que o contêiner subir (tarefa T1); o design será ajustado se
> o formato diferir.

```jsonc
// requisição
{"model": "llama3.1:8b", "stream": false,
 "options": {"temperature": 0.1, "seed": 42, "num_thread": 4},
 "tools": [{"type": "function", "function": {"name": "buscar_metar", "description": "...",
            "parameters": {"type": "object", "properties": {"icao": {"type": "string", "description": "..."}},
                           "required": ["icao"]}}}],
 "messages": [{"role": "system", "content": "..."}, {"role": "user", "content": "..."},
              {"role": "assistant", "content": "", "tool_calls": [...]},
              {"role": "tool", "tool_name": "buscar_metar", "content": "{...resumo...}"}]}
// resposta
{"message": {"role": "assistant", "content": "...",
             "tool_calls": [{"function": {"name": "buscar_metar", "arguments": {"icao": "SBGR"}}}]},
 "done": true, "prompt_eval_count": 412, "eval_count": 37, "total_duration": 5123456789}
```

`arguments` pode chegar como objeto ou como texto JSON (modelos menores fazem isso): o agente aceita os dois.

## 4. `prompts.py`

```python
VERSAO_PROMPT = "v1"
PROMPT_SISTEMA_V1 = """..."""      # texto completo abaixo; vai para slide
PROMPT_SISTEMA = PROMPT_SISTEMA_V1
LEMBRETE_FERRAMENTA = "Antes de responder, consulte buscar_metar para cada aeródromo citado na pergunta."
AVISO = "Ferramenta acadêmica. Não substitui o briefing meteorológico oficial."
FERRAMENTAS = [...]                 # schemas de buscar_metar e buscar_taf
```

Rascunho do prompt v1 (o texto final passa pelos testes de REQ-A-12):

```
Você é um assistente de briefing meteorológico VFR para aeródromos brasileiros, usado em um projeto acadêmico.

Como trabalhar:
1. Identifique os aeródromos citados na pergunta e converta cada um para o código ICAO de 4 letras.
2. Chame buscar_metar para CADA aeródromo antes de responder. Não responda sem consultar.
3. O resultado traz o campo "veredito" (VMC, IMC ou RECUSA), calculado por um módulo de regras.
   Use esse veredito exatamente como veio. Nunca recalcule nem contradiga.
4. Se o veredito for RECUSA, diga apenas o motivo informado.
5. Na explicação, cite o teto (teto_ft), a visibilidade (vis_m) e o METAR (metar_bruto) que vieram da
   ferramenta. Não invente nenhum dado que não esteja no resultado.
6. buscar_taf é só informativo: o TAF não muda o veredito.

Responda em português do Brasil, em no máximo 4 frases. Termine lembrando que a consulta não substitui o
briefing oficial (REDEMET/AIS) nem a decisão do piloto em comando.
```

Schemas das ferramentas: `icao` com descrição "Código ICAO de 4 letras do aeródromo brasileiro (ex.: o
código de Guarulhos)". *(O exemplo não dá o código, para não virar tabela — D5.)*

## 5. `traco.py`

```python
class Traco:
    def __init__(self, pergunta: str, *, modelo: str, versao_prompt: str,
                 relogio: Callable[[], datetime], pasta: Path): ...
    id: str            # secrets.token_hex(6) → 12 hex
    def passo(self, tipo: str, **dados) -> None   # acrescenta {"tipo", "t_ms", **dados}
    def gravar(self, resposta: dict | None) -> Path
```

- Arquivo: `{pasta}/{inicio:%Y%m%dT%H%M%SZ}_{id}.json`, UTF-8, indentado, `ensure_ascii=False`,
  `default=str` (datas e objetos não-JSON viram texto em vez de quebrar a gravação).
- `TIPOS_PASSO = {"prefiltro", "modelo", "ferramenta", "harness", "verificador", "erro"}`; tipo fora disso →
  `ValueError` (erro de programação).
- `pasta` padrão = `TRACES_DIR` ou `traces/`; criada se não existir.

## 6. `agente.py`

```python
class ErroModelo(Exception): ...

class ClienteOllama:
    def __init__(self, *, url=None, modelo=None, temperatura=None, num_thread=None, timeout_s=None,
                 http=None): ...
    modelo: str
    def conversar(self, mensagens: list[dict], ferramentas: list[dict]) -> dict   # lança ErroModelo

@dataclass(frozen=True)
class RespostaAgente:                 # REQ-A-10
    id_traco: str; veredito: str; motivo: str; avaliacoes: list[dict]; explicacao: str
    origem_explicacao: str; bloqueio: dict | None; aviso: str; duracao_ms: int
    def para_dict(self) -> dict

class Agente:
    def __init__(self, *, ollama: ClienteOllama | None = None,
                 buscar_metar=ferramentas.buscar_metar, buscar_taf=ferramentas.buscar_taf,
                 relogio=agora_utc, pasta_traces: Path | None = None): ...
    def perguntar(self, pergunta: str) -> RespostaAgente
```

`ErroModelo` cobre: `httpx.TransportError` (inclui tempo esgotado), HTTP ≠ 200 (mensagem com o corpo, ex.:
modelo não baixado), JSON inválido, resposta sem `message`.

### 6.1 Loop de `perguntar`

```
traco = Traco(...)
1. pergunta vazia ou > 500 caracteres         → RECUSA pergunta_invalida            (passo prefiltro)
2. harness.prefiltrar_pergunta                → RECUSA <categoria>                  (passo prefiltro)
3. mensagens = [system, user]; avaliacoes = {}  (dict ICAO → Resumo, mantém a ordem)
   chamadas = 0; lembrete_usado = False
4. laço:
   resp = ollama.conversar(mensagens, FERRAMENTAS)    ErroModelo → RECUSA erro_modelo   (passo erro)
   passo modelo: mensagens enviadas, message, prompt_eval_count, eval_count, tokens_estimados, duracao_ms
   se message.tool_calls:
       mensagens += assistant(tool_calls)
       para cada tool_call:
           chamadas == 5 → RECUSA limite_iteracoes
           chamadas += 1
           janela = _executar(nome, argumentos)          (passos ferramenta e harness)
           mensagens += {"role": "tool", "tool_name": nome, "content": json(janela)}
       volta ao laço
   senão (texto final):
       sem avaliacoes e não lembrete_usado → mensagens += assistant(texto), user(LEMBRETE); volta ao laço
       sem avaliacoes                       → RECUSA sem_avaliacao (texto descartado)
       sai do laço com texto
5. veredito geral (6.3) e verificação (6.4)
finally: traco.gravar(resposta)
```

O laço termina sempre: cada volta com ferramenta consome ≥ 1 das 5 chamadas, e a volta sem ferramenta só se
repete uma vez (lembrete).

### 6.2 `_executar(nome, argumentos)`

| Caso | O que vai para a janela | Entra em `avaliacoes`? |
|---|---|---|
| `argumentos` não é objeto/JSON, ou sem `icao` texto | `{"erro": "argumento icao (texto) obrigatório"}` | não |
| ferramenta desconhecida | `{"erro": "ferramenta desconhecida: <nome>"}` | não |
| `buscar_metar` → `ok` | `harness.avaliar_metar(texto_bruto, icao, relogio()).resumo.para_dict()` | sim (resumo do harness) |
| `buscar_metar` → `icao_invalido` | `{icao, status, veredito: "RECUSA", motivo: "Use o código ICAO de 4 letras."}` | **não** (REQ-A-07) |
| `buscar_metar` → `sem_dado` / `fora_do_escopo` / `erro_api` / `limite_api` | `{icao, status, veredito: "RECUSA", motivo}` | sim (resumo de recusa montado no agente) |
| `buscar_taf` (qualquer status) | `{icao, status, taf_bruto, aviso: "Informativo: o TAF não entra no veredito."}` | não |

O passo `ferramenta` do traço guarda `ResultadoBusca.para_dict()` inteiro (com `resposta_api`) **e** o que foi
para a janela; o passo `harness` guarda o código de recusa e o resumo.

### 6.3 Veredito geral (REQ-A-07)

```python
vereditos = [r.veredito for r in avaliacoes.values()]
geral = "RECUSA" if "RECUSA" in vereditos else "IMC" if "IMC" in vereditos else "VMC"
motivo = resumo.motivo  (um aeródromo)  |  "SBGR: VMC; SBSP: IMC"  (vários)
```

### 6.4 Explicação (REQ-A-08, REQ-A-09)

- `RECUSA` → `explicacao` = texto-modelo de cada aeródromo recusado (uma linha cada); `origem = texto_modelo`.
- `VMC`/`IMC` →
  1. `harness.verificar_explicacao(texto, resumo_ref)`, com `resumo_ref` = primeiro aeródromo cujo veredito é o
     geral;
  2. se passou: ICAOs brasileiros citados no texto (`\bS[BDIJNSW][A-Z]{2}\b`) que não estão em `avaliacoes` →
     bloqueio `icao_nao_avaliado`, trecho = o código;
  3. bloqueado → `explicacao` = texto-modelo de **todos** os aeródromos avaliados, um por linha;
     `bloqueio = {regra, trecho}`.
- Recusas antes do modelo ou do loop (`pergunta_invalida`, categorias do pré-filtro, `erro_modelo`,
  `limite_iteracoes`, `sem_avaliacao`): `explicacao = motivo + " Consulte o briefing oficial (REDEMET/AIS)."`.

## 7. Plano de testes

Modelo roteirizado: classe falsa com `conversar()` que devolve respostas de uma lista e guarda as mensagens
recebidas. Ferramentas falsas devolvem `ResultadoBusca` montados a partir das fixtures do módulo 02 (METAR
SBGR real) e de METARs sintéticos (IMC, recusa). Relógio fixo = `obsTime` da fixture + 10 min. Traços em
`tmp_path`.

| Requisito | Testes previstos |
|---|---|
| A-01 | pré-filtro recusa sem chamar o modelo; vazia e 501 caracteres → `pergunta_invalida`; passo `prefiltro` no traço |
| A-02 | ferramentas enviadas = `{buscar_metar, buscar_taf}`; ferramenta desconhecida → erro na janela e conta iteração; `icao` ausente / não-texto → erro; `arguments` em texto JSON aceito |
| A-03 | conteúdo da mensagem `tool` = `Resumo.para_dict()`; nenhuma mensagem enviada ao modelo contém `resposta_api`, `fltCat`, `receiptTime`; chaves da janela do TAF e da busca que falhou |
| A-04 | 5 chamadas permitidas; a 6ª → `limite_iteracoes` |
| A-05 | sem ferramenta → lembrete uma vez e depois sucesso; sem ferramenta duas vezes → `sem_avaliacao` com o texto descartado |
| A-06 | `ErroModelo` → `RECUSA erro_modelo` e passo `erro`; `ClienteOllama`: conexão recusada, 404 (modelo não baixado), JSON inválido e resposta sem `message` → `ErroModelo` |
| A-07 | VMC+VMC → VMC; VMC+IMC → IMC; IMC+RECUSA → RECUSA; vale a última avaliação do ICAO; `icao_invalido` não conta; modelo diz "VMC" com harness IMC → veredito IMC |
| A-08 | RECUSA descarta o texto do modelo e mostra o motivo |
| A-09 | contradição → texto-modelo e `bloqueio`; ICAO não avaliado → `icao_nao_avaliado`; explicação coerente → `origem = modelo` |
| A-10 | chaves exatas de `RespostaAgente.para_dict()`; `aviso` fixo |
| A-11 | corpo da requisição ao Ollama (`model`, `stream`, `options.temperature`, `options.seed`, `tools`); URL `/api/chat`; variáveis de ambiente |
| A-12 | `VERSAO_PROMPT` no traço; prompt cita `buscar_metar`, `veredito`, `português`, `REDEMET`; prompt sem nenhum código ICAO |
| A-13 | arquivo com nome no padrão; chaves; tipos dos passos; passo `modelo` com mensagens e contagens; passo `ferramenta` com `resposta_api`; traço gravado também em recusa, erro e exceção inesperada; `id` = 12 hex |
| A-14 | `@pytest.mark.ollama`: "dá pra ir VFR em Guarulhos agora?" no Ollama real → `SBGR` avaliado e veredito VMC/IMC/RECUSA válido |

Estimativa: ~55 testes.

## 8. Revisão 1 — mitigação do H7 (aprovada em 10/11/2026)

Requisitos: seção 5 de [requisitos.md](requisitos.md) (aprovada em 10/11/2026).

### 8.1 Nome da estação (REQ-A-15)

```python
def _nome_estacao(resultado: ResultadoBusca) -> str | None:
    # primeiro elemento de resposta_api, campo "name", texto não vazio → strip(); qualquer outra coisa → None
```

- `avaliacoes` passa a guardar `ICAO → (Resumo, nome_estacao)`; o veredito geral continua lendo só o `Resumo`.
- Janela de `buscar_metar` com sucesso: `{**resumo.para_dict(), "nome_estacao": nome}`.
- Janela de busca que falhou: **sem mudança** (`{icao, status, veredito, motivo}`) — não há estação para mostrar.
- `RespostaAgente.avaliacoes`: `[{**resumo.para_dict(), "nome_estacao": nome}, ...]`; busca que falhou → `null`.
- O passo `harness` do traço ganha `nome_estacao`. `harness.py` não muda (o `Resumo` continua com as chaves
  do REQ-H-12).

### 8.2 Prompt v2 (REQ-A-12)

`PROMPT_SISTEMA_V2` = v1 com um passo novo (o 4) e a numeração ajustada. O v1 fica intacto em `prompts.py`.

```
Você é um assistente de briefing meteorológico VFR para aeródromos brasileiros, usado em um projeto acadêmico.

Como trabalhar:
1. Identifique os aeródromos citados na pergunta e converta cada um para o código ICAO de 4 letras.
2. Chame buscar_metar para CADA aeródromo antes de responder. Não responda sem consultar.
3. O resultado traz o campo "veredito" (VMC, IMC ou RECUSA), calculado por um módulo de regras.
   Use esse veredito exatamente como veio. Nunca recalcule nem contradiga.
4. O resultado traz "nome_estacao", o nome da estação na base meteorológica (pode vir em inglês ou abreviado).
   Confira se é o aeródromo que a pergunta pediu. Se for outro aeródromo, chame buscar_metar de novo com o
   código correto antes de responder.
5. Se o veredito for RECUSA, diga apenas o motivo informado.
6. Na explicação, cite o teto (teto_ft), a visibilidade (vis_m) e o METAR (metar_bruto) que vieram da
   ferramenta. Não invente nenhum dado que não esteja no resultado.
7. buscar_taf é só informativo: o TAF não muda o veredito.

Responda em português do Brasil, em no máximo 4 frases. Termine lembrando que a consulta não substitui o
briefing oficial (REDEMET/AIS) nem a decisão do piloto em comando.
```

Efeito esperado no caso real: o modelo pede `SBKP`, recebe `"nome_estacao": "Campinas/Viracopos Arpt, SP, BR"`,
percebe que não é Guarulhos e chama de novo. Essa nova chamada conta no limite de 5 (REQ-A-04), e a avaliação
que vale é a última por ICAO (REQ-A-07). Como `SBKP` foi avaliado, ele **continua** em `avaliacoes` — a
interface vai mostrar os dois, cada um com seu nome. *(Consequência aceita: o piloto vê exatamente o que foi
consultado.)*

### 8.3 Testes

| Requisito | Testes previstos |
|---|---|
| A-15 | nome lido de `resposta_api[0]["name"]`; ausente, vazio, não-texto ou `resposta_api` vazio → `null`; nome não muda o veredito (mesmo METAR com nome de outra cidade → mesmo veredito) |
| A-03 (alterado) | janela de `buscar_metar` = resumo + `nome_estacao`; janela de busca que falhou continua sem `nome_estacao`; JSON bruto continua fora |
| A-10 (alterado) | cada item de `avaliacoes` tem `nome_estacao` |
| A-12 (alterado) | `VERSAO_PROMPT == "v2"`; `PROMPT_SISTEMA is PROMPT_SISTEMA_V2`; v1 continua existindo; v2 cita `nome_estacao`; nenhum dos dois tem código ICAO |
| A-13 | passo `harness` do traço com `nome_estacao` |
| A-14 | `test_req_a14_ollama_real` sem mudança (exige `SBGR`) — é o critério de aceite com o modelo real |
