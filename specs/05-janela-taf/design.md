# 05 — Janela VFR pelo TAF: design

**Estado:** aprovado em 10/11/2026 · **Requisitos:** [requisitos.md](requisitos.md) (aprovado)

## 1. Decisões de design para validar

| ID | Decisão | Por quê |
|---|---|---|
| DJ1 | Decodificador do TAF em arquivo próprio, **`app/harness_taf.py`**, dentro da camada do harness (mesmas regras: só biblioteca padrão, sem rede/LLM/relógio) | `harness.py` já tem ~360 linhas; o TAF tem semântica própria (mudanças no tempo). O teste de imports do REQ-H-11 passa a cobrir os dois arquivos |
| DJ2 | Reaproveitar a leitura de visibilidade/nuvens do METAR extraindo uma função `ler_condicoes(tokens)` de `avaliar_metar` (refatoração coberta pelos 155 testes do harness) | Uma regra só de visibilidade/teto para METAR e TAF (REQ-J-03) |
| DJ3 | Condição como "o que foi informado": `vis_m` e `camadas` podem ser `None` (= não mudou) nos grupos de mudança | Implementa "só os elementos informados mudam" (REQ-J-04) |
| DJ4 | Períodos **IMC** agrupados por veredito + grupo responsável; períodos **VMC** só pelo veredito; a melhor janela olha só o veredito hora a hora | O motivo do IMC fica fiel ao grupo que o causou; o VMC não se quebra em pedaços a cada `BECMG` que não muda o resultado *(ajuste feito ao escrever os testes: com veredito + grupo também no VMC, o SBGR real virava 4 períodos VMC seguidos)* |
| DJ5 | Verificador por horário mora no **agente** (que conhece as janelas), usando uma função nova do harness `contradicao(texto, veredito)` extraída de `verificar_explicacao` | Uma só lista de expressões favoráveis/desfavoráveis (REQ-H-14) |
| DJ6 | Horário citado numa frase = primeira ocorrência daquela hora UTC a partir de agora, dentro da validade; vários aeródromos com janela → vale o **pior** veredito daquela hora entre eles | Conservador e determinístico |
| DJ7 | `RespostaAgente` ganha `janelas: list[dict]` com valor padrão `[]` | Não quebra o módulo 04 nem as execuções gravadas antigas |
| DJ8 | Linha do tempo na página: uma faixa de células por hora (rótulo `12Z`, cor + texto `VMC`/`IMC`), a melhor janela com contorno grosso e, logo abaixo, a **lista textual dos períodos** (acessível sem cor) | Segue o estilo já aprovado (Swiss, 1C/2B) |

## 2. API do harness do TAF (`app/harness_taf.py`)

```python
@dataclass(frozen=True)
class ResumoJanela:                      # REQ-J-07 — os campos SÃO as chaves
    icao: str | None
    emitido_utc: str | None
    validade_inicio: str | None
    validade_fim: str | None
    periodos: list[dict]                 # [{inicio, fim, veredito, motivo, grupo}]
    melhor_janela: dict | None           # {inicio, fim, horas}
    veredito: str                        # "JANELA" | "RECUSA"
    motivo: str
    taf_bruto: str
    def para_dict(self) -> dict

@dataclass(frozen=True)
class ResultadoJanela:
    veredito: str                        # "JANELA" | "RECUSA"
    codigo_recusa: str | None
    resumo: ResumoJanela
    horas: list[dict]                    # [{hora, veredito, motivo, grupo}] — para o traço e os testes

def avaliar_taf(taf_bruto: str, icao_solicitado: str, agora: datetime) -> ResultadoJanela
def veredito_na_hora(resumo: ResumoJanela, momento: datetime) -> str | None   # usado pelo verificador
def texto_modelo_janela(resumo: ResumoJanela) -> str
```

### 2.1 Algoritmo de `avaliar_taf`

1. **Cabeçalho**, na ordem: `TAF` · `AMD`/`COR` opcionais · ICAO (`formato_invalido`) · escopo (`fora_do_escopo`)
   · ICAO divergente (`icao_divergente`) · emissão `DDHHMMZ` (`formato_invalido`; no futuro > 5 min →
   `horario_futuro`) · `NIL` → `sem_dado` · validade `DDHH/DDHH` (`formato_invalido`) · `CNL` → `taf_cancelado`.
2. **Datas da validade** resolvidas a partir da **emissão**: o dia é o do mês da emissão ou do mês seguinte (o
   primeiro que não fica antes da emissão menos 1 h); `HH=24` → 00 h do dia seguinte.
3. `agora ≥ fim da validade` → `taf_vencido`.
4. **Corte** em `RMK`. **Segmentos**: base (até o primeiro grupo de mudança) e grupos iniciados por `BECMG`,
   `TEMPO`, `PROB30`/`PROB40` (com ou sem `TEMPO` em seguida), cada um com seu período `DDHH/DDHH`.
5. **Condições** de cada segmento com `harness.ler_condicoes` → `Condicao(vis_m | None, camadas | None)`.
   `CAVOK` → `vis 10000, camadas []`; `NSC` → `camadas []`. Base sem visibilidade ou sem nuvens → `taf_incompleto`;
   camada `///` → `taf_incompleto`.
6. **Hora a hora**, de `max(agora arredondado, início)` até o fim:
   - *vigente* = base + todos os `BECMG` já terminados, em ordem;
   - candidatos = `[vigente]`; + `vigente ⊕ BECMG` se a hora está dentro de uma transição;
     + `vigente ⊕ temporário` para cada `TEMPO`/`PROB` ativo;
   - veredito da hora = **IMC se algum candidato for IMC** (pior caso); `grupo` = o grupo do candidato que deu IMC
     (ou `base`/último `BECMG` se VMC); `motivo` = `harness._motivo` do candidato escolhido.
7. **Períodos** (DJ4) e **melhor janela** (REQ-J-06).

### 2.2 Texto-modelo da janela

```
Previsão (TAF) para SBGR, válida até 12/11 06Z: 00–03Z IMC (teto 1300 ft abaixo de 1500 ft, base);
03–08Z VMC; 08–12Z IMC (visibilidade 4000 m ..., BECMG 1108/1110); ...
Melhor janela VMC: 12Z–18Z (6 h). Previsão, não observação.
```

## 3. Agente (`app/agente.py`, `app/prompts.py`)

- `FERRAMENTAS` = `buscar_metar`, `avaliar_janela` (DJ8 dos requisitos: `buscar_taf` sai).
- `_executar("avaliar_janela", {"icao"})`: `buscar_taf` (módulo 02) → `ok` → `harness_taf.avaliar_taf` → janela =
  `resumo.para_dict()`; busca que falhou → `{icao, status, veredito: "RECUSA", motivo}`. Guarda em `janelas`.
  Passo `harness` do traço com `tipo_dado: "taf"` e as horas.
- Veredito geral: **sem mudança** (só `buscar_metar`, REQ-A-07).
- Verificação (REQ-J-11):
  1. divide a explicação em frases (`.`, `!`, `?`, quebra de linha);
  2. frase com horário (`\b(\d{1,2})(?:[:h](\d{2}))?\s*(?:z|utc)\b`, `\bàs\s+(\d{1,2})(?:h|:\d{2})?\b`,
     `\b(\d{1,2})h\b`) → momento (DJ6) → veredito daquela hora; sem janela que cubra → bloqueio
     `horario_fora_da_validade`; senão `harness.contradicao(frase, veredito_da_hora)`;
  3. frases sem horário → verificação atual contra o veredito de agora (REQ-A-09);
  4. ICAOs citados podem estar em `avaliacoes` **ou** `janelas` (REQ-A-09, ICAO não avaliado).
  Bloqueio → texto-modelo dos aeródromos + `texto_modelo_janela` de cada janela.
- `PROMPT_SISTEMA_V3`: v2 + passo "Para perguntas sobre quando voar, melhor horário ou próximas horas, chame
  `buscar_metar` **e** `avaliar_janela`. Use os períodos e a melhor janela exatamente como vieram, com horários em
  UTC (ex.: 15Z), e diga que é previsão." `VERSAO_PROMPT = "v3"`.
- Pré-filtro (REQ-J-12): novo texto do motivo `previsao_alem_taf`.

## 4. Interface (`app/static/index.html`)

- Seção **"Previsão (TAF) — não é o tempo de agora"** depois de "Aeródromos consultados", uma por janela:
  - faixa horizontal de células (rolagem horizontal **dentro** da faixa em telas estreitas), cada célula com hora
    (`12Z`), cor e texto curto (`VMC`/`IMC`), `title`/`aria-label` com o motivo;
  - melhor janela: células com contorno grosso + frase "Melhor janela VMC: 12Z–18Z (09h–15h em Brasília), 6 h";
  - lista textual dos períodos (hora UTC, hora local, veredito, motivo, grupo);
  - TAF bruto em fonte monoespaçada; janela recusada → motivo.
- Novo exemplo: "Qual a melhor janela pra voar VFR em Congonhas nas próximas horas?".

## 5. Plano de testes

`tests/test_taf.py` com os 14 TAFs reais da fixture + TAFs sintéticos para cada regra; "agora" fixo.

| Requisito | Testes previstos |
|---|---|
| J-01 | cabeçalho com/sem `AMD`/`COR`, com/sem `=`; ICAO ausente/emissão/validade malformadas → `formato_invalido`; estrangeiro → `fora_do_escopo`; divergente → `icao_divergente` |
| J-02 | `NIL`, `CNL`; vencido; validade começando no dia seguinte; virada de mês/ano; `HH=24` |
| J-03 | `CAVOK`, `NSC`, `VV`, `NSW` ignorado, `TX`/`TN` ignorados, `RMK` cortado; base incompleta → `taf_incompleto` |
| J-04 | `BECMG` só com vento não muda nada; `BECMG` só com visibilidade mantém nuvens; transição = pior caso; `TEMPO`, `PROB30`, `PROB40`, `PROB40 TEMPO` = pior caso só no período |
| J-05 | horas desde agora até o fim; limites 1500 ft/5000 m; grupo responsável correto |
| J-06 | agrupamento; melhor janela mais longa; empate → mais cedo; sem VMC → `null` |
| J-07 | chaves exatas do resumo em `JANELA` e `RECUSA` |
| J-08 | imports só da biblioteca padrão (teste do REQ-H-11 estendido) |
| reais | os 14 TAFs reais decodificam sem erro; SBGR (agora 11/00:30Z): IMC 00–05Z (base `BKN013`, inclui a transição 03–05Z), VMC 05–08Z, IMC 08–14Z (`BECMG 1108/1110`, inclui as transições), **melhor janela 14Z–06Z (16 h)** — começa em 14Z e não em 12Z porque a transição do `BECMG 1112/1114 CAVOK` é pior caso (D1); SBCT: IMC 00–14Z, VMC 14–24Z |
| J-09 | ferramenta exposta; janela na mensagem `tool` = resumo; `janelas` na resposta; veredito geral não muda |
| J-10 | `VERSAO_PROMPT == "v3"`; v1/v2 preservados; v3 cita `avaliar_janela` |
| J-11 | "às 15Z dá para voar visual" com 15Z IMC → bloqueia; com 15Z VMC → passa; horário fora da validade → bloqueia; frase sem horário continua contra agora |
| J-12 | motivo do pré-filtro oferece a janela |
| J-13 | página contém o título da previsão e o exemplo novo; conferência no navegador |
| Ollama real | "melhor janela em Congonhas nas próximas horas" → `avaliar_janela` chamado (marcado `ollama`) |
