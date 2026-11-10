# 05 — Janela VFR pelo TAF: requisitos

**Estado:** aprovado em 10/11/2026 · **Módulos:** `app/harness.py` (decodificação do TAF), `app/agente.py` + `app/prompts.py`
(ferramenta `avaliar_janela`), `app/static/index.html` (linha do tempo) · **Testes:** `tests/test_taf.py`,
`tests/test_agente.py`, `tests/test_main.py`

## 1. Objetivo e escopo

Responder "qual a melhor janela para voar VFR em <aeródromo> nas próximas horas?" (CLAUDE.md, item 7 do harness).
O **código** decodifica o TAF, calcula VMC/IMC **por hora** com a mesma regra de mínimos e escolhe a melhor
janela; o modelo só explica.

**O veredito exibido continua sendo o de agora, pelo METAR** (observação). A janela é informação complementar,
de **previsão**, mostrada à parte. *[Decisão D4]*

**Fora do escopo:** previsão além da validade do TAF (recusada, REQ-H-13); grupos `FM` (não apareceram em nenhum
TAF brasileiro observado); vento, tempo presente e temperatura (`TX`/`TN`) — não entram na regra de mínimos.

## 2. Base: TAFs reais observados (10/11/2026, 14 aeródromos)

Gravados em `tests/fixtures/awc/taf_14_aerodromos_20261110.json`. Grupos encontrados: `BECMG`, `TEMPO`, `PROB30`,
`PROB40`, `PROB40 TEMPO`, `CAVOK`, `NSC`, `NSW`. Exemplo (SBGR):

```
TAF SBGR 102222Z 1100/1206 09005KT 9999 BKN013 TN15/1109Z TX26/1118Z BECMG 1103/1105 8000 NSC
BECMG 1108/1110 4000 BR BKN007 BECMG 1112/1114 CAVOK BECMG 1115/1117 29005KT SCT040 PROB30 1118/1121 16010KT SHRA
SCT035 FEW045TCU BECMG 1121/1123 14007KT BKN020 BECMG 1201/1203 08005KT CAVOK RMK PGG
```

## 3. Perigos

| ID | Perigo | Novo? |
|---|---|---|
| H1 | apresentar VMC quando é IMC (aqui: período previsto como VMC quando o TAF prevê IMC em algum trecho) | — |
| H3 | explicação contradiz o código (aqui: texto diz "às 15Z dá para voar visual" e o código calculou IMC às 15Z) | — |
| H10 | **previsão tratada como observação**: o piloto lê a janela como se fosse o tempo de agora | sim |

## 4. Requisitos — harness (decodificação e regra)

**REQ-J-01 — Formato** (H1)
- O harness DEVE aceitar `TAF [AMD|COR] ICAO DDHHMMZ DDHH/DDHH <condições> [grupos de mudança] [RMK …]`, com ou sem
  `=`, espaços repetidos e quebras de linha.
- SE emissão ou validade não forem identificáveis, ENTÃO DEVE recusar com `formato_invalido`.
- As checagens de escopo (`fora_do_escopo`) e ICAO divergente (`icao_divergente`) DEVEM ser as mesmas do METAR
  (REQ-H-03, REQ-H-04), na mesma ordem.

**REQ-J-02 — TAF sem uso**
- `NIL` → `sem_dado`; `CNL` (cancelado) → `taf_cancelado`.
- SE "agora" for depois do fim da validade, ENTÃO DEVE recusar com `taf_vencido`.
- Dias `DD` resolvidos como no METAR (mês anterior/seguinte conforme "agora"; virada de mês e de ano).
  *(Validade pode começar no dia seguinte à emissão: `102222Z 1100/1206`.)*

**REQ-J-03 — Condições**
- Visibilidade, nuvens, `VV`, `CAVOK`, `NSC` decodificados com as mesmas regras do METAR (REQ-H-08, REQ-H-09).
- O harness DEVE ignorar vento, tempo presente, `NSW`, `TX`/`TN` e tudo depois de `RMK`.
- SE a condição-base não tiver visibilidade ou nuvens (nem `CAVOK`/`NSC`), ENTÃO DEVE recusar o TAF inteiro com
  `taf_incompleto`. *[Decisão D6]*

**REQ-J-04 — Grupos de mudança** (H1)
- `BECMG DDHH/DDHH`: depois do fim do período, valem as novas condições — **só os elementos informados mudam**
  (ex.: `BECMG 1106/1108 09007KT` não muda visibilidade nem nuvens; `CAVOK` define visibilidade 10000 m e sem teto;
  `NSC` tira o teto; um grupo de nuvens substitui todas as camadas).
- **Durante** a transição do `BECMG`, a hora DEVE ser avaliada pelo **pior caso** entre a condição anterior e a
  nova. *[Decisão D1]*
- `TEMPO`, `PROB30`, `PROB40` e `PROB30/40 TEMPO`: durante o período, a hora DEVE ser avaliada pelo **pior caso**
  entre a condição vigente e a temporária (CLAUDE.md, item 7).

**REQ-J-05 — Veredito por hora** (H1)
- O harness DEVE avaliar cada hora cheia `[h, h+1)` desde a hora atual (arredondada para baixo) até o fim da
  validade, com a regra do REQ-H-10 (`TETO_MIN_FT`, `VIS_MIN_M` — as mesmas constantes).
- Cada hora DEVE trazer o motivo e **qual grupo** determinou o resultado (`base`, `BECMG 1108/1110`,
  `PROB30 1118/1121` …).

**REQ-J-06 — Períodos e melhor janela**
- Horas consecutivas com o mesmo veredito DEVEM ser agrupadas em períodos `{inicio, fim, veredito, motivo, grupo}`.
- A **melhor janela** DEVE ser o período VMC contínuo mais longo; empate → o mais cedo; nenhum VMC → `null`.
  *[Decisão D3]*

**REQ-J-07 — Resumo compacto** (Context Engineering)
- Para a janela do modelo, o harness DEVE produzir exatamente:
  `icao, emitido_utc, validade_inicio, validade_fim, periodos, melhor_janela, veredito, motivo, taf_bruto`,
  com `veredito` ∈ {`JANELA`, `RECUSA`}. Horários em ISO 8601 UTC.

**REQ-J-08 — Independência do modelo**
- Mesmas garantias do REQ-H-11: só biblioteca padrão, "agora" por parâmetro, sem rede, sem LLM, sem campos
  decodificados da API (`fcsts` do JSON é ignorado).

## 5. Requisitos — agente e prompt

**REQ-J-09 — Ferramenta `avaliar_janela(icao)`**
- O agente DEVE expor a terceira ferramenta `avaliar_janela(icao)`: busca o TAF (módulo 02), passa por
  `harness.avaliar_taf` e devolve **só o resumo compacto** (REQ-J-07). O JSON bruto vai só para o traço.
- `buscar_taf` (informativo, REQ-A-02) **sai** do conjunto de ferramentas: `avaliar_janela` o substitui. *[Decisão D8]*
- A resposta do agente DEVE ganhar o campo `janelas` (lista de resumos de janela, um por aeródromo).
- `avaliar_janela` NÃO DEVE mudar o veredito geral (que continua vindo de `buscar_metar`, REQ-A-07). *[D4]*

**REQ-J-10 — Prompt v3**
- `PROMPT_SISTEMA_V3` (`VERSAO_PROMPT = "v3"`): para perguntas sobre "quando", "melhor horário", "próximas horas",
  chamar `buscar_metar` **e** `avaliar_janela`; usar períodos e melhor janela exatamente como vieram; dizer os
  horários em UTC; deixar claro que a janela é previsão. v1 e v2 continuam no código.

**REQ-J-11 — Verificação com horário** (H3) *[Decisão D5]*
- Frase da explicação que cita um horário explícito (ex.: `15Z`, `15 UTC`, `15h`, `às 15`) DEVE ser verificada
  contra o veredito **do período que contém esse horário**; frases sem horário continuam verificadas contra o
  veredito de agora (REQ-A-09).
- SE a frase citar horário fora da validade do TAF, ENTÃO a explicação DEVE ser bloqueada (`horario_fora_da_validade`).
- Explicação bloqueada → texto-modelo gerado em código, agora incluindo a lista de períodos.

**REQ-J-12 — Recusa além do TAF oferece a janela**
- O motivo da categoria `previsao_alem_taf` do pré-filtro (REQ-H-13) DEVE passar a oferecer a alternativa:
  "… Posso mostrar a melhor janela VFR dentro da validade do TAF (até ~30 h)."

## 6. Requisitos — interface

**REQ-J-13 — Linha do tempo**
- QUANDO houver `janelas`, a página DEVE mostrar, para cada aeródromo, uma linha do tempo horária (uma célula por
  hora, cor + texto VMC/IMC), a melhor janela em destaque e o TAF bruto.
- A seção DEVE ter o título "**Previsão (TAF)** — não é o tempo de agora" e ficar visualmente separada do veredito
  (H10).
- Horários em UTC com a hora local entre parênteses (Brasília, UTC−3). *[Decisão D7]*
- Novo exemplo clicável: "Qual a melhor janela pra voar VFR em Congonhas nas próximas horas?".

## 7. Decisões (confirmadas em 10/11/2026, opção proposta)

| ID | Decisão proposta | Alternativa | Efeito |
|---|---|---|---|
| D1 | Transição do `BECMG` = pior caso entre antes e depois | Mudar no início (ou no meio) do período | Conservador; pode marcar IMC horas que já seriam VMC |
| D2 | Granularidade de 1 hora | Meia hora / minutos | TAF brasileiro só usa horas cheias |
| D3 | Melhor janela = VMC contínuo mais longo (empate → mais cedo) | Primeira janela VMC | "Melhor" é decidido em código, não pelo modelo |
| D4 | Veredito exibido continua sendo o de agora (METAR); janela é previsão à parte | Veredito da janela | Não mistura observação com previsão (H10) |
| D5 | Verificador por horário: frase com hora é checada contra o período daquela hora | (a) aceitar bloqueio frequente checando tudo contra agora; (b) explicação da janela só em texto-modelo | (a) bloquearia quase toda resposta útil ("agora IMC, abre às 13Z"); (b) tira o modelo da explicação. A proposta mantém o modelo e a verificação |
| D6 | Condição-base incompleta → recusa do TAF inteiro | Marcar só as horas afetadas | Simples e conservador; caso raro |
| D7 | UTC com hora local (UTC−3) entre parênteses | Só UTC | Piloto usa UTC; a banca entende melhor com a local |
| D8 | `avaliar_janela` substitui `buscar_taf` | Manter as três ferramentas | Menos ferramentas para o 8b confundir |

## 8. Tamanho

É o maior módulo depois do harness: decodificador de TAF com a semântica de mudanças, ferramenta nova, prompt v3,
verificador por horário e linha do tempo. Estimativa: ~1,5 dia de trabalho com os portões. **Se a apresentação for
em 12/11, não cabe** junto com avaliação, STPA e slides; em 26/11, cabe.
