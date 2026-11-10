# AGENTS.md — padrões do AgenteVFR

Guia para qualquer agente de código (Codex, Claude Code, Cursor etc.) que trabalhe neste repositório.
A especificação completa do projeto está em [`CLAUDE.md`](CLAUDE.md); o estado de cada módulo, em
[`specs/README.md`](specs/README.md). Este arquivo diz **como** trabalhar aqui.

## O projeto em três linhas

Agente de briefing meteorológico VFR (projeto do Exame da disciplina TE251). O usuário pergunta em linguagem
natural; o modelo (Llama via Ollama) escolhe os aeródromos e redige a explicação; **o código decide** VMC/IMC/
RECUSA a partir do METAR bruto e bloqueia explicações que contradizem o veredito.

## Regras de trabalho

- Responda em **português do Brasil**. Código e nomes de variáveis podem ser em português (o padrão do repo).
- Antes de cada etapa grande, apresente o plano e espere aprovação.
- Antes de apagar, sobrescrever ou renomear um arquivo existente, mostre o que muda e espere confirmação.
- Não modifique nada fora desta pasta: nada de instalar pacotes no sistema, mexer na configuração global do
  git ou reiniciar Docker/OrbStack sem pedir.
- Não faça push, não crie repositório nem abra PR sem pedido explícito.
- Não escreva código de produção sem um requisito aprovado que o justifique (ver fluxo abaixo).

## Fluxo spec-driven (obrigatório)

Cada módulo tem `specs/NN-modulo/` com três arquivos e passa por cinco portões:

| Portão | Artefato | Quem libera |
|---|---|---|
| 1 | `requisitos.md` — requisitos em formato EARS, numerados, cada um com o perigo que mitiga | o grupo aprova |
| 2 | `design.md` — API pública, algoritmo, decisões, plano de testes | o grupo aprova |
| 3 | testes derivados dos requisitos, **todos falhando** contra um esqueleto (`raise NotImplementedError`) | registrar em `tarefas.md` quantos falham e por quê |
| 4 | implementação até os testes passarem | `pytest` verde (inclusive os módulos anteriores) |
| 5 | sanidade com dado/serviço real, matriz de rastreabilidade em `specs/README.md`, `tarefas.md` marcado | revisão |

- **Formato EARS:** "O sistema DEVE …", "QUANDO <gatilho>, … DEVE …", "SE <indesejado>, ENTÃO … DEVE …".
- **IDs:** `REQ-H-xx` (harness), `REQ-F-xx` (ferramentas), `REQ-A-xx` (agente), `REQ-I-xx` (interface).
- **Decisões** que o grupo precisa confirmar vão numa tabela `D1…Dn` no fim de `requisitos.md`, com alternativa
  e efeito. Depois de aprovadas, marque "confirmadas em DD/MM/AAAA".
- **Mudar um requisito já aprovado:** edite o texto e acrescente no próprio requisito
  `*Revisão DD/MM/AAAA:* o que mudou e por quê` (exemplo: REQ-H-02).
- **Achado durante o trabalho** que afeta outro módulo: registre em "Achados para os próximos módulos" no
  `tarefas.md` do módulo atual.
- **Um commit por portão**, para o histórico mostrar que a spec e os testes vieram antes do código.

## Invariantes de segurança — não quebre

Estes pontos sustentam o argumento do projeto ("o que o modelo decide e o que o sistema força"). Há testes para
quase todos; se um teste destes falhar, a mudança está errada, não o teste.

1. **O veredito sai só de código** (`app/harness.py`). O modelo nunca decide, recalcula ou altera VMC/IMC/RECUSA,
   e o veredito exibido nunca vem do texto do modelo.
2. **`harness.py` usa só a biblioteca padrão**: sem rede, sem relógio interno (o "agora" vem por parâmetro), sem
   LLM. `test_req_h11_so_biblioteca_padrao` verifica os imports.
3. **A janela do modelo recebe só dados compactos** (`Resumo.para_dict()` do harness). O JSON bruto da API
   (`resposta_api`) **nunca** entra na janela; vai só para o traço.
4. **Recusa não é "consertada" pelo modelo**: com veredito RECUSA, o texto do modelo é descartado.
5. **Um só lugar para cada regra:** escopo em `harness.PREFIXOS_BR`; mínimos e limites em constantes nomeadas
   (`TETO_MIN_FT`, `VIS_MIN_M`, `IDADE_MAX_MIN`, `CACHE_TTL_S`, `MAX_CHAMADAS_FERRAMENTA`…); termos do
   pré-filtro em `harness.TERMOS_FORA_DE_ESCOPO`. Nada de número ou lista solta repetida em outro arquivo.
6. **Ferramentas nunca devolvem dado inventado**, nem conteúdo de cache vencido quando a API falha.
7. **Toda execução do agente gera traço** em `traces/`, inclusive recusa, erro do modelo e exceção.
8. **O prompt é versionado:** mudou o texto → nova constante `PROMPT_SISTEMA_Vn` em `app/prompts.py`,
   `PROMPT_SISTEMA` aponta para ela e `VERSAO_PROMPT` muda. O prompt não pode conter tabela nome → ICAO
   (o mapeamento é o que o modelo decide e é medido na avaliação).
9. **Na dúvida, o lado seguro:** bloquear uma explicação correta é aceitável; deixar passar uma contradição não.

## Estrutura

```
app/
  harness.py       # decodificação do METAR, regra VMC/IMC, recusas, pré-filtro, verificador de contradição
  ferramentas.py   # ClienteAWC: METAR/TAF da aviationweather.gov, cache, nova tentativa
  prompts.py       # prompt de sistema versionado e esquemas das ferramentas
  agente.py        # ClienteOllama e loop do agente com tool calling
  traco.py         # traço JSON de cada execução
  main.py          # (módulo 04) FastAPI
  static/index.html
tests/
  test_<modulo>.py
  fixtures/awc/    # respostas REAIS gravadas da API (não editar à mão)
specs/             # requisitos, design e tarefas de cada módulo + matriz de rastreabilidade
avaliacao/ stpa/ docs/ traces/
```

## Ambiente e comandos

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
```

```bash
.venv/bin/python -m pytest              # padrão: sem rede e sem Ollama
.venv/bin/python -m pytest -m rede      # chama a API real
.venv/bin/python -m pytest -m ollama    # chama o Ollama real (precisa do Compose de pé)
```

```bash
docker compose up -d ollama                 # Ollama no Docker (só CPU no Mac)
docker compose run --rm ollama-pull         # baixa llama3.1:8b e llama3.2:3b uma vez
```

| Variável | Padrão | Uso |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | no Compose: `http://ollama:11434` |
| `OLLAMA_MODEL` | `llama3.1:8b` | alternativa leve: `llama3.2:3b` |
| `OLLAMA_TEMPERATURA` | `0.1` | |
| `OLLAMA_NUM_THREAD` | `4` | M3: 4 núcleos de desempenho; 8 threads deixa a geração ~60× mais lenta |
| `OLLAMA_TIMEOUT_S` | `300` | CPU é lenta |
| `AWC_BASE_URL` | `https://aviationweather.gov/api/data` | |
| `AWC_TIMEOUT_S` | `10` | |
| `TRACES_DIR` | `traces/` | |

## Testes

- O nome do teste cita o requisito: `test_req_h10_limites_inclusivos`, `test_req_f07_cache_vence_em_5_min`.
- A execução padrão **não usa rede nem modelo**. Injete as dependências: `httpx.MockTransport` para HTTP,
  relógio falso, modelo roteirizado (`tests/test_agente.py::ModeloRoteirizado`).
- Horários sempre relativos a um "agora" fixo do teste; nunca `datetime.now()` dentro de um teste.
- Fixtures da API só se regravam com resposta real (`curl` com o `User-Agent` do projeto), nunca escritas à mão.
- Teste que precisa de serviço externo leva marcador (`rede`, `ollama`) e fica fora da execução padrão.

## Código

- Python 3.11+, type hints, `@dataclass(frozen=True)` para resultados; `para_dict()` quando vai para JSON.
- **Erro de programação → exceção** (ex.: `agora` sem fuso). **Dado ruim ou serviço fora → status/RECUSA**,
  nunca exceção para quem chamou.
- Dependência nova só com aprovação; versões fixadas em `requirements.txt`. Imagens Docker com tag exata
  publicada há pelo menos duas semanas (nunca `latest`).
- Simples primeiro: nada de abstração, configuração ou tratamento de erro que nenhum requisito pede.
- Comentários e docstrings em português, apontando o requisito quando ajuda (`# REQ-H-07`).

## Git

- Mensagens de commit em português: `<Módulo>: <o que mudou> (portão N, …)`, com corpo curto em tópicos.
- O autor já está configurado **neste repositório** (`git config --local`); não mexa na configuração global.
- Não commite `.venv/`, `__pycache__/`, `.env` nem credenciais. Nenhum dado pessoal em código, fixture ou
  `User-Agent`.
- Remoto: `origin` (GitHub, privado). Push só quando pedido.
