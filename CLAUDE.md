# AgenteVFR — Agente de briefing meteorológico VFR com decisão verificada

Projeto do Exame da disciplina TE251 (2026-2). Este arquivo é a especificação do projeto.
Leia inteiro antes de começar.

## Regras de trabalho para o Claude Code

- Antes de cada etapa grande (ver "Ordem de trabalho"), apresente o plano da etapa e espere aprovação.
- Antes de apagar, sobrescrever ou renomear qualquer arquivo existente, mostre o que vai mudar e espere confirmação.
- Não modifique nada fora desta pasta do projeto.
- Responda em português do Brasil. Código e nomes de variáveis podem ser em português.

## Contexto do Exame (o que a banca vai cobrar)

- Duas partes do mesmo projeto: **apresentação oral** (10 min de exposição + 5 min de perguntas, cronômetro vale,
  pergunta pode ir a qualquer integrante) e **artigo final no modelo SIGE**.
- A técnica tem de ser uma das ensinadas na disciplina, usada **de forma visível**, e o grupo tem de **mostrar que rodou**.
- A apresentação precisa mostrar:
  1. o problema em poucas frases e por que um modelo entra nele;
  2. a técnica da disciplina no ponto em que ela aparece no sistema;
  3. uma execução com sucesso **e** um caso que não fecha (falha tratada, recusa ou limite);
  4. **o que o modelo decide e o que o sistema força**;
  5. o limite que o artigo vai escrever na seção de **AI Assurance**.
- Demo ao vivo é bem-vinda; se a rede falhar, o grupo segue com captura/vídeo curto já no slide. Não improvisar outro sistema.
- Slides em PDF ou PPTX, nome: `TE251_2026-2_Exame_AgenteVFR_slides.pdf` (ou `.pptx`).
- Data da apresentação: **13/11/2026** (confirmada em 10/11/2026).

### Técnicas da disciplina usadas neste projeto

| Técnica | Onde aparece |
|---|---|
| Prompt Engineering | prompt de sistema do agente (vai num slide) |
| Context Engineering | o que entra na janela a cada passo: só dados compactos e o veredito, nunca o JSON bruto da API |
| Agente com ferramenta | `buscar_metar` (já devolve o veredito do harness) e `avaliar_janela` (TAF, módulo 05) via tool calling do Ollama; `buscar_taf` só é chamada por dentro de `avaliar_janela` |
| Harness | regra VMC/IMC em código, checagem de idade do dado, escopo, lista de ferramentas permitidas, limite de 5 chamadas, ramo de erro, verificador de contradição |
| AGENTS.md | `AGENTS.md` na raiz: padrões e invariantes de segurança para agentes de código que trabalham no repositório |
| Análise de perigos assistida por LLM (STPA) | pasta `stpa/` (módulo 07) |
| Evals: gabarito do grupo, grader de código e juiz LLM | `avaliacao/` (módulo 06): harness × 40 METARs rotulados, acerto de ICAO, recusas, juiz avaliando a fidelidade das explicações |

O projeto **não usa RAG** (não há corpus, recuperação nem citação de trecho); não apresentar como RAG
(`specs/08-conformidade-disciplina/requisitos.md`, D4).

## O sistema

O usuário pergunta em linguagem natural (ex.: "dá pra ir VFR de Guarulhos pra Congonhas agora?").
O agente identifica os aeródromos, busca METAR/TAF, um **módulo em código** decide VMC/IMC,
e o modelo **só explica** a decisão.

Também responde "qual a melhor janela para voar VFR em <aeródromo> nas próximas horas?", limitado à
validade do TAF (24–30 h). O harness decodifica o TAF e calcula VMC/IMC por período; o modelo só explica.

### O que o modelo decide
- interpretar a pergunta e mapear nomes de aeródromos para códigos ICAO;
- quais ferramentas chamar e em que ordem;
- redigir a explicação para o piloto.

### O que o sistema força (harness) — o modelo NÃO consegue alterar
1. **Veredito VMC/IMC calculado em código** a partir do METAR bruto (decodificado por nós, não pelo modelo).
2. **Dado desatualizado → recusa**: METAR com mais de 60 min.
3. **Dado ausente/inválido → recusa**: ICAO inexistente, METAR NIL, campos `////`.
4. **Escopo**: só aeródromos brasileiros (prefixos ICAO SB, SD, SI, SJ, SN, SS, SW). Fora disso → recusa.
5. **Pedidos fora de escopo → recusa** com aviso: planejamento IFR, "posso decolar mesmo assim?",
   pedidos para ignorar a regra, previsão além do TAF. O sistema não substitui o briefing oficial (REDEMET/AIS).
6. **Verificador de contradição**: se a explicação do modelo contradiz o veredito (ex.: veredito IMC e o texto diz
   que dá para voar visual), a explicação é bloqueada e substituída por um texto-modelo gerado em código;
   o bloqueio é registrado no traço. Começar com regras (palavras/expressões) e, se der tempo, um segundo
   passe com o LLM como checador.
7. **Janela pelo TAF**: VMC/IMC de cada período do TAF calculado em código com a mesma regra de mínimos.
   `TEMPO` e `PROB30/40` contam como pior caso (se o trecho temporário é IMC, o período é IMC).
   Pedido além da validade do TAF → recusa, com a oferta da janela disponível.

O veredito exibido na interface vem **sempre** do código, nunca do texto do modelo.

### Regra de mínimos (harness.py)

Base: ICA 100-1 ("Requisitos para Operação VFR ou IFR em Aeródromos"), item 3.1.1 — operação VFR condicionada
aos mínimos de teto e visibilidade. Critério usado:

- **VMC** se teto **≥ 1500 ft** **e** visibilidade **≥ 5000 m**;
- caso contrário **IMC**.

**Pendência:** conferir o texto vigente da ICA 100-1 e da ICA 100-12 e citar o item exato no artigo.

Decodificação (o mínimo necessário):
- **Teto** = base da camada mais baixa BKN ou OVC; VV (visibilidade vertical) também conta como teto.
  FEW/SCT não são teto. Altura em centenas de pés (`BKN015` = 1500 ft).
- **Visibilidade**: METAR brasileiro em metros, 4 dígitos (`9999` = 10 km ou mais). Tratar `CAVOK`
  (visibilidade ≥ 10 km e sem teto abaixo de 5000 ft → VMC).
- `NSC`, `NCD`, `SKC`, `CLR` = sem teto.
- Horário `DDHHMMZ` → calcular idade em minutos em relação ao relógio UTC atual.
- Aceitar `METAR` e `SPECI`; tratar `AUTO`, `COR`, `NIL` e `////`.

Casos de teste obrigatórios (pytest, `tests/test_harness.py`); use horário relativo ao "agora" do teste:

| METAR | Esperado | Por quê |
|---|---|---|
| `METAR SBGR 101200Z 12008KT 9999 FEW030 SCT100 25/16 Q1018=` | VMC | sem teto, vis 10 km |
| `METAR SBKP 101200Z 32005KT CAVOK 28/12 Q1015=` | VMC | CAVOK |
| `METAR SBRJ 101200Z 20006KT 9999 BKN015 24/19 Q1016=` | VMC | teto exatamente 1500 (limite inclusivo) |
| `SPECI SBSJ 101215Z 10003KT 5000 -RA SCT010 BKN020 19/18 Q1019=` | VMC | vis exatamente 5000; SCT010 não é teto |
| `METAR SBSP 101200Z 15010KT 4000 BR BKN008 18/17 Q1020=` | IMC | vis e teto abaixo |
| `METAR SBCT 101200Z 09004KT 6000 OVC012 15/14 Q1021=` | IMC | só o teto abaixo |
| `METAR SBPA 101200Z 00000KT 0800 FG VV002 12/12 Q1022=` | IMC | VV conta como teto |
| METAR com mais de 60 min | RECUSA | dado desatualizado |
| `METAR SBXX 101200Z NIL=` | RECUSA | sem dado |
| `METAR KJFK ...` | RECUSA | fora do escopo (não brasileiro) |

## Stack

- **Mac Apple Silicon** com OrbStack (Docker).
- **Tudo em Docker Compose** (OrbStack), dois serviços:
  - `ollama`: imagem oficial `ollama/ollama` (versão fixada), volume nomeado `ollama_data` para os modelos,
    porta 11434 publicada no host (para testes locais). Um serviço `ollama-pull` baixa o modelo uma vez.
  - `app`: Python 3.11+, FastAPI, httpx, pydantic. Acessa o Ollama em `http://ollama:11434`
    (variável de ambiente `OLLAMA_URL`).
- **Limitação aceita**: no Mac, o contêiner não acessa a GPU (Metal); o modelo roda só na CPU.
  Respostas mais lentas; medir o tempo por pergunta e registrar no artigo e no roteiro da demo.
- **Modelo: `llama3.1:8b`** (`ollama pull llama3.1:8b`). Atenção: o `llama3` original **não suporta tool calling**
  no Ollama; o `llama3.1` suporta. Alternativa leve: `llama3.2:3b`.
- **Fonte de dados**: API pública aviationweather.gov, sem chave, cobertura mundial, limite de 100 req/min.
  - METAR: `https://aviationweather.gov/api/data/metar?ids=SBGR&format=json`
  - TAF: provavelmente `https://aviationweather.gov/api/data/taf?ids=SBGR&format=json` — **confirmar no schema
    OpenAPI** em https://aviationweather.gov/data/api/ antes de implementar.
  - Pegar o campo do METAR bruto e decodificar no `harness.py`. Os campos decodificados da API podem ser usados
    só para conferência nos testes.
  - Cache de 5 min por ICAO para não estourar o limite durante a demo.
- **Interface**: um único `static/index.html` (HTML + CSS + JS puro), servido pelo FastAPI.

## Estrutura de pastas

```
AgenteVFR/
├── CLAUDE.md
├── docker-compose.yml        # serviços app + ollama (+ ollama-pull)
├── Dockerfile
├── requirements.txt
├── app/
│   ├── main.py               # FastAPI: GET / (index.html), POST /api/perguntar, GET /api/traco/{id}
│   ├── agente.py             # loop do agente com tool calling (Ollama /api/chat com tools)
│   ├── ferramentas.py        # buscar_metar, buscar_taf (httpx + cache)
│   ├── harness.py            # decodificação, regra VMC/IMC, idade, escopo, verificador de contradição
│   ├── prompts.py            # prompt de sistema (versionado; vai num slide)
│   ├── traco.py              # log JSON de cada execução em traces/
│   └── static/index.html
├── tests/
│   └── test_harness.py
├── avaliacao/
│   ├── coletar_metars.py     # coleta METARs reais de ~20 aeródromos brasileiros, salva em dados/
│   ├── casos.json            # casos com gabarito (rotulados à mão pelo grupo) + casos de recusa
│   ├── avaliar.py            # roda tudo e gera métricas + tabelas/figuras para o artigo
│   └── resultados/
├── stpa/
│   ├── prompts_stpa.md
│   └── stpa.md               # tabela final revisada pelo grupo
├── traces/
└── docs/
    ├── roteiro_apresentacao.md
    └── artigo_estrutura.md
```

## Loop do agente (agente.py)

1. Monta a janela: prompt de sistema + pergunta do usuário.
2. Pré-filtro de escopo em código (palavras como IFR, "mesmo assim", "ignore"); se pegar → recusa direta, registrada no traço.
3. Chama o Ollama com as tools. Para cada `tool_call`:
   - executa a ferramenta;
   - passa o resultado pelo harness;
   - devolve ao modelo **só o resumo compacto** (Context Engineering):
     `{icao, tipo, horario_utc, idade_min, vis_m, teto_ft, camadas, veredito, motivo, metar_bruto}`.
4. Limite de 5 iterações de ferramenta; depois disso → erro tratado.
5. Resposta final = veredito (código) + explicação (modelo, após o verificador de contradição).
6. Se o harness recusar em qualquer ponto, a resposta é a recusa com o motivo; o modelo não "conserta" a recusa.

`temperature` baixa (0–0.2) para reprodutibilidade.

## Traço (traco.py) — prova de que rodou

Cada execução gera `traces/<timestamp>_<id>.json` com:
- pergunta; mensagens enviadas ao modelo em cada passo (o que entrou na janela) e estimativa de tokens;
- tool calls com argumentos e resultados (o bruto da API fica no traço, mas NÃO na janela do modelo);
- cada checagem do harness (passou/bloqueou e motivo);
- resposta final e tempo total.

## Interface (static/index.html)

- Campo de pergunta + botão; exemplos clicáveis (um VMC, um IMC, uma recusa).
- Veredito em destaque: **VMC** (verde), **IMC** (vermelho), **RECUSA** (cinza) com o motivo.
- Explicação do modelo abaixo; METAR bruto citado.
- Painel recolhível "Traço da execução": passos, janela de contexto, tool calls, checagens do harness
  (bloqueios em destaque).
- Aviso fixo: "Ferramenta acadêmica. Não substitui o briefing meteorológico oficial."

## Avaliação (avaliacao/)

1. `coletar_metars.py`: coleta METARs reais de ~20 aeródromos brasileiros, várias vezes ao longo de alguns dias,
   para pegar condições IMC também (madrugada/manhã costuma ter nevoeiro em SBSP, SBCT, SBPA, SBSJ).
2. `casos.json`: pelo menos 30 METARs com o veredito **rotulado à mão pelo grupo** (o gabarito não pode vir do próprio
   harness) + ~10 perguntas que devem ser recusadas + ~10 perguntas normais em linguagem natural.
3. `avaliar.py` mede:
   - acurácia do veredito do harness contra o gabarito;
   - acerto de ICAO a partir do nome do aeródromo (o que o modelo decide);
   - taxa de recusa correta e de falsa recusa;
   - fidelidade da explicação: modelo juiz com rubrica (1–5: consistente com o veredito, cita teto/visibilidade
     corretos, não inventa dado);
   - quantas contradições o verificador bloqueou;
   - tokens médios por execução (Context Engineering).
   Saídas: CSV + figuras em `avaliacao/resultados/`.
4. Limitação a registrar: o juiz é o próprio Llama (viés de autoavaliação). Se der tempo, comparar com rótulo humano
   em uma amostra.

## STPA (stpa/)

Análise de perigos assistida pelo Llama, **revisada pelo grupo**:
1. Perdas (ex.: L1 piloto decide voar VFR em condição IMC; L2 perda de confiança no sistema).
2. Perigos (ex.: H1 sistema apresenta VMC quando a condição real é IMC; H2 sistema usa dado desatualizado;
   H3 explicação contradiz o veredito; H4 sistema responde fora do escopo).
3. Estrutura de controle: usuário ↔ interface ↔ agente (LLM) ↔ harness ↔ API.
4. Ações de controle inseguras (UCAs) nas 4 categorias do STPA.
5. Cenários causais e qual mecanismo do harness mitiga cada um. Os não mitigados vão para a seção de AI Assurance.
Guardar os prompts usados em `prompts_stpa.md` e marcar o que o grupo alterou na saída do LLM.

## Demo da apresentação

- **Sucesso**: aeródromo em VMC, veredito verde e explicação coerente, mostrando o traço.
- **Caso que não fecha**: METAR desatualizado, aeródromo estrangeiro ou "posso decolar mesmo assim?" → recusa;
  e/ou um IMC em que o verificador bloqueia uma explicação contraditória.
- "Qual o melhor dia pra ir pra Miami nos próximos 5 dias?" → recusa dupla (fora do Brasil + além do TAF).
- Gravar vídeo curto de backup da demo e colocar no slide.

## AI Assurance (limites para o artigo)

- Não substitui o briefing oficial nem a decisão do piloto em comando.
- Só aeródromo e só METAR/TAF: não avalia rota, terreno, NOTAM, condições em voo.
- Mínimos simplificados (teto/visibilidade de aeródromo); não cobre VFR especial, operação noturna, mínimos de
  espaço aéreo por classe.
- Dependência da disponibilidade e da atualização da API.
- Verificador de contradição baseado em regras pode deixar passar paráfrases.
- Juiz é o mesmo modelo; conjunto de avaliação pequeno.
- O modelo pode mapear o nome para o aeródromo errado (H7: "Guarulhos" → SBKP/Campinas, reprodutível com o
  llama3.1:8b) e omitir aeródromos da pergunta (H8). O sistema só torna isso visível (nome da estação na
  resposta); não bloqueia.
- Janela pelo TAF é previsão, não observação; a regra de pior caso pode ser conservadora demais
  (marca IMC um período em que o TEMPO tem 30% de chance).

## Ordem de trabalho

1. Esqueleto do projeto + `harness.py` + `tests/test_harness.py` passando.
2. `ferramentas.py` (confirmar o schema da API) + cache.
3. `agente.py` + `prompts.py` + `traco.py`, testados com o Ollama do Compose.
4. `main.py` + `static/index.html` + Docker Compose; `docker compose up` e demo funcionando; medir tempo médio por pergunta.
4b. Janela VFR pelo TAF (`specs/05-janela-taf/`): decodificação do TAF, veredito por período, ferramenta
    `avaliar_janela` para o agente, exemplo na interface.
5. Avaliação: coletar, rotular (grupo), rodar métricas.
6. STPA.
7. `docs/roteiro_apresentacao.md` (10 min) e slides.
8. `docs/artigo_estrutura.md` no modelo SIGE.

## Pendências

- Confirmar o item exato da ICA 100-1/ICA 100-12 para citar.
- Confirmar o endpoint do TAF e os campos do JSON no schema da API.
- Lista de integrantes (autores no artigo e na apresentação).
