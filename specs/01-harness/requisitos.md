# 01 — Harness: requisitos

**Estado:** aprovado em 10/11/2026 · **Módulo:** `app/harness.py` · **Testes:** `tests/test_harness.py`

## 1. Objetivo e escopo

O harness é a parte do sistema que **o modelo não consegue alterar**. Ele recebe dados brutos e devolve
decisões calculadas em código:

| Função | Entrada | Saída |
|---|---|---|
| Avaliar METAR | METAR bruto (texto), ICAO solicitado, instante "agora" (UTC) | veredito `VMC` / `IMC` / `RECUSA` + motivo + resumo compacto |
| Pré-filtrar pergunta | pergunta do usuário (texto) | segue / `RECUSA` + categoria |
| Verificar explicação | explicação do modelo + resumo compacto | aceita / bloqueada + texto substituto |

**Fora do escopo deste módulo:** buscar dados na API e verificar se um ICAO existe (módulo 02); decodificar o
TAF (o TAF é repassado como texto e **não** entra no veredito); o loop do agente (módulo 03).

## 2. Perigos preliminares mitigados

| ID | Perigo |
|---|---|
| H1 | Sistema apresenta VMC quando a condição real é IMC |
| H2 | Sistema usa dado desatualizado |
| H3 | Explicação contradiz o veredito |
| H4 | Sistema responde fora do escopo |

## 3. Glossário

- **Teto**: altura da base da camada mais baixa reportada como BKN ou OVC, ou a visibilidade vertical (VV).
- **Visibilidade**: visibilidade predominante do METAR, em metros.
- **Idade**: minutos entre o horário de observação do METAR e o instante "agora".
- **Recusa**: resposta em que o sistema não emite VMC/IMC e informa o motivo. Toda recusa tem um código.

## 4. Requisitos

### Identificação e ordem das checagens

**REQ-H-01 — Formato do boletim** (H1)
- O harness DEVE aceitar boletins na forma `[METAR|SPECI] [COR] ICAO DDHHMMZ [AUTO] …`, com ou sem `=` no
  final, com espaços repetidos ou quebras de linha.
- QUANDO o tipo estiver ausente (boletim começa pelo ICAO), o harness DEVE assumir `METAR`.
- SE o ICAO (4 letras) ou o horário `DDHHMMZ` não puderem ser identificados, ENTÃO o harness DEVE recusar com
  `formato_invalido`.

**REQ-H-02 — Ordem das checagens** (H1, H2, H4)
- O harness DEVE aplicar as checagens nesta ordem e devolver a **primeira** recusa encontrada:
  1. ICAO identificável → `formato_invalido`
  2. escopo geográfico → `fora_do_escopo`
  3. ICAO do boletim igual ao solicitado → `icao_divergente`
  4. horário `DDHHMMZ` identificável e válido → `formato_invalido`
  5. boletim NIL → `sem_dado`
  6. horário no futuro → `horario_futuro`
  7. idade → `dado_desatualizado`
  8. campos meteorológicos → `visibilidade_indisponivel`, `teto_indisponivel`, `nuvens_indisponiveis`
- *Revisão 10/11/2026:* ICAO e horário separados (antes eram um passo só, o que impedia o caso KJFK);
  NIL passou para depois do horário.
- A recusa por escopo DEVE ocorrer mesmo que o restante do boletim seja inválido (ex.: `METAR KJFK ...`).

**REQ-H-03 — Escopo geográfico** (H4)
- SE o ICAO não começar com `SB`, `SD`, `SI`, `SJ`, `SN`, `SS` ou `SW`, ENTÃO o harness DEVE recusar com
  `fora_do_escopo`.

**REQ-H-04 — ICAO divergente** (H1)
- SE o ICAO do boletim for diferente do ICAO solicitado, ENTÃO o harness DEVE recusar com `icao_divergente`.
- O ICAO usado no veredito DEVE ser o do boletim, nunca um valor vindo do modelo.

### Disponibilidade e atualidade do dado

**REQ-H-05 — Boletim NIL** (H1)
- SE o boletim contiver `NIL` logo após o horário, ENTÃO o harness DEVE recusar com `sem_dado`.

**REQ-H-06 — Idade do dado** (H2)
- O harness DEVE calcular a idade em minutos a partir de um instante "agora" **recebido como parâmetro**
  (a função de decisão não lê o relógio).
- QUANDO o dia `DD` do boletim for maior que o dia de "agora", o harness DEVE considerar o mês anterior
  (inclusive virada de ano).
- SE a idade for **maior que 60 min**, ENTÃO o harness DEVE recusar com `dado_desatualizado`. Idade de
  exatamente 60 min é aceita.
- SE o horário do boletim estiver mais de 5 min no futuro em relação a "agora", ENTÃO o harness DEVE recusar com
  `horario_futuro`.
- SE o dia `DD` não existir no mês deduzido, ENTÃO o harness DEVE recusar com `formato_invalido`.

### Decodificação

**REQ-H-07 — Parte decodificada** (H1)
- O harness DEVE decodificar só a observação atual, parando no primeiro `RMK`, `BECMG`, `TEMPO` ou `NOSIG`.
  Grupos depois disso (tendência e observações) não entram no veredito.
- O harness DEVE aceitar `AUTO` e `COR` sem que eles alterem a decisão.
- O harness DEVE ignorar grupos que não usa (vento, RVR `R..`, tempo presente, temperatura, pressão, `RE..`,
  `WS..`).

**REQ-H-08 — Visibilidade** (H1)
- O harness DEVE ler a visibilidade predominante como 4 dígitos em metros; `9999` vale 10000 m.
- O harness DEVE aceitar o sufixo `NDV` (`9999NDV`) e ignorar a visibilidade mínima direcional
  (ex.: o `1500NE` em `4000 1500NE`). *[Decisão D1]*
- QUANDO o boletim contiver `CAVOK`, o harness DEVE considerar visibilidade 10000 m e ausência de teto.
- SE a visibilidade for `////` ou estiver ausente (sem `CAVOK`), ENTÃO o harness DEVE recusar com
  `visibilidade_indisponivel`.

**REQ-H-09 — Teto** (H1)
- O harness DEVE considerar como teto a menor base entre as camadas `BKN`, `OVC` e `VV`, em pés
  (altura × 100: `BKN015` = 1500 ft, `VV002` = 200 ft).
- O harness DEVE ignorar `FEW` e `SCT` no cálculo do teto e aceitar os sufixos `CB` e `TCU`.
- QUANDO o boletim trouxer `NSC`, `NCD`, `SKC`, `CLR` ou `CAVOK`, o harness DEVE considerar ausência de teto.
- SE uma camada `BKN`, `OVC` ou `VV` tiver altura `///`, ou houver grupo de nuvem com cobertura desconhecida
  (`//////`), ENTÃO o harness DEVE recusar com `teto_indisponivel`. *[Decisão D2]*
- SE o boletim não tiver nenhum grupo de nuvem nem `CAVOK`/`NSC`/`NCD`/`SKC`/`CLR`, ENTÃO o harness DEVE recusar
  com `nuvens_indisponiveis`. *[Decisão D3]*

### Decisão

**REQ-H-10 — Regra VMC/IMC** (H1)
- O harness DEVE emitir `VMC` se, e somente se, (não houver teto **ou** teto ≥ 1500 ft) **e**
  visibilidade ≥ 5000 m. Caso contrário, DEVE emitir `IMC`. Os limites são inclusivos.
- O motivo DEVE dizer qual condição falhou (teto, visibilidade ou ambos) com os valores medidos e os mínimos.
- A regra DEVE estar parametrizada por constantes (`TETO_MIN_FT = 1500`, `VIS_MIN_M = 5000`,
  `IDADE_MAX_MIN = 60`) com a referência normativa (ICA 100-1, item 3.1.1) comentada no código.

**REQ-H-11 — Independência do modelo** (H1, H3)
- A função de decisão DEVE depender só do METAR bruto, do ICAO solicitado e de "agora": sem rede, sem LLM, sem
  relógio interno. A mesma entrada DEVE produzir sempre a mesma saída.
- O harness NÃO DEVE usar campos já decodificados pela API (ex.: `fltCat`, `visib`, `clouds`) na decisão.

### Contexto para o modelo

**REQ-H-12 — Resumo compacto** (Context Engineering)
- O harness DEVE produzir, para todo resultado (inclusive recusa), um resumo com exatamente as chaves
  `icao, tipo, horario_utc, idade_min, vis_m, teto_ft, camadas, veredito, motivo, metar_bruto`.
- `horario_utc` em ISO 8601; `teto_ft` = `null` sem teto; `camadas` = lista de grupos como no boletim
  (ex.: `["FEW030", "SCT100"]`); campos não decodificados = `null`.
- O resumo NÃO DEVE conter nenhum outro campo (em particular, nada do JSON bruto da API além de `metar_bruto`).

### Pré-filtro de pergunta

**REQ-H-13 — Pedidos fora de escopo** (H4)
- QUANDO a pergunta contiver um termo de fora de escopo, o harness DEVE recusar, antes de qualquer chamada ao
  modelo, com uma destas categorias:

  | Categoria | Exemplos de termos |
  |---|---|
  | `pedido_ifr` | IFR, plano IFR, aproximação por instrumentos |
  | `pressao_operacional` | mesmo assim, assim mesmo, mesmo com, dá um jeito |
  | `manipulacao_regra` | ignore, desconsidere, esqueça a regra, finja, sem o harness |
  | `previsao_alem_taf` | semana que vem, próxima semana, depois de amanhã, daqui a N dias, mês que vem |
  | `fora_do_tema` *(13/11)* | integral, derivada, equação, Python/SQL, receita, poema, piada, traduza, redação — **só se a pergunta não tiver termo do tema** (REQ-H-16): "Traduza este METAR" passa (revisão do PR #5) |

- A comparação DEVE ignorar maiúsculas/minúsculas e acentos.
- A lista de termos DEVE ficar num único lugar do código (vai para slide e artigo).

### Verificador de contradição

**REQ-H-14 — Detecção de contradição** (H3)
- QUANDO o veredito for `IMC` e a explicação afirmar condição visual favorável (ex.: "dá para voar visual",
  "condições VMC", "VFR liberado", "pode voar VFR", "favorável ao voo visual"), o harness DEVE bloquear a
  explicação.
- QUANDO o veredito for `VMC` e a explicação afirmar condição desfavorável (ex.: "condições IMC",
  "abaixo dos mínimos", "não é possível voar VFR", "voo visual não recomendado"), o harness DEVE bloquear a
  explicação.
- Uma expressão precedida de negação (`não`, `nem`, `nunca`) em até 3 palavras DEVE ser lida com o sentido
  invertido (ex.: "não dá para voar visual" com veredito IMC **não** é contradição).
- SE a explicação estiver vazia, ENTÃO o harness DEVE tratá-la como bloqueada.

**REQ-H-15 — Substituição e registro** (H3)
- QUANDO a explicação for bloqueada, o harness DEVE devolver um texto-modelo gerado em código a partir do
  resumo compacto (veredito, teto, visibilidade, mínimos e METAR bruto).
- O harness DEVE devolver também o registro do bloqueio: regra disparada e trecho da explicação, para o traço.
- QUANDO o veredito for `RECUSA`, nenhuma explicação do modelo DEVE ser usada; o texto é sempre o texto-modelo
  de recusa com o motivo.

**REQ-H-16 — Trava de conversa sem consulta** (H1) *[revisão de 13/11/2026; ver REQ-A-16]*
- `verificar_conversa(texto)` DEVE devolver `(regra, trecho)` quando o texto, escrito sem nenhuma ferramenta
  consultada, trouxer: texto vazio (`conversa_vazia`); código de 4 letras maiúsculas, como `SBGR` ou `KJFK`
  (`conversa_cita_aerodromo`); grupo de METAR, como `BKN015`, `CAVOK` ou `101200Z` (`conversa_cita_dado`);
  afirmação favorável ou desfavorável do REQ-H-14, ou frase de ir/não ir, como "pode ir", "não dá pra voar" ou
  "o tempo está bom" (`conversa_com_veredito`).
- Também DEVE barrar texto com mais de 500 caracteres (`conversa_longa`) e texto com cara de conta, como `∫`, `√`,
  `dx` ou "2 + 2 = 4" (`conversa_fora_do_tema`). Barra não conta: "1500/5000" e "13/11" passam.
- Siglas de 4 letras que não são aeródromo (ICAO, IATA, ANAC, ATIS, AFIS, ZULU) não contam como código.
- Frases de liberação também são afirmação de condição: "liberado", "autorizado", "seguro para voar",
  "sem restrições" (revisão do PR #5: antes a trava deixava passar).
- Caso contrário, DEVE devolver `None`. Definições e mínimos ("VMC significa…", "teto de 1500 ft") passam.
- `pergunta_no_tema(pergunta)` DEVE devolver `True` só se a pergunta tiver um termo de `TERMOS_DO_TEMA`
  (aviação/meteorologia, cumprimento ou dúvida sobre o sistema). A lista fica num único lugar do código.
  "Como está <lugar>" é do tema.
- `pergunta_pede_consulta(pergunta)` DEVE devolver `True` quando a pergunta tiver um código de 4 letras (fora as
  siglas acima) ou pedir decisão de voo ("posso ir", "dá pra decolar", "está VMC", "está aberto").
  Motivo: o llama3.1:8b não classificou o tema de forma estável (13/11/2026: marcou "Oi, tudo bem?" e
  "O que é um METAR?" como fora do tema numa rodada e acertou na outra).

## 5. Critérios de aceite obrigatórios (CLAUDE.md)

Horários relativos ao "agora" do teste.

| METAR | Esperado | Requisitos |
|---|---|---|
| `METAR SBGR 101200Z 12008KT 9999 FEW030 SCT100 25/16 Q1018=` | VMC | H-08, H-09, H-10 |
| `METAR SBKP 101200Z 32005KT CAVOK 28/12 Q1015=` | VMC | H-08, H-09 |
| `METAR SBRJ 101200Z 20006KT 9999 BKN015 24/19 Q1016=` | VMC (limite inclusivo) | H-09, H-10 |
| `SPECI SBSJ 101215Z 10003KT 5000 -RA SCT010 BKN020 19/18 Q1019=` | VMC (vis no limite; SCT não é teto) | H-08, H-09, H-10 |
| `METAR SBSP 101200Z 15010KT 4000 BR BKN008 18/17 Q1020=` | IMC | H-10 |
| `METAR SBCT 101200Z 09004KT 6000 OVC012 15/14 Q1021=` | IMC (só teto) | H-10 |
| `METAR SBPA 101200Z 00000KT 0800 FG VV002 12/12 Q1022=` | IMC (VV é teto) | H-09, H-10 |
| METAR com mais de 60 min | RECUSA `dado_desatualizado` | H-06 |
| `METAR SBXX 101200Z NIL=` | RECUSA `sem_dado` | H-05 |
| `METAR KJFK ...` | RECUSA `fora_do_escopo` | H-02, H-03 |

Além desses, cada requisito terá ao menos um teste próprio (limites, casos de borda e caminho de recusa).

## 6. Decisões (confirmadas em 10/11/2026, opção proposta)

| ID | Decisão proposta | Alternativa | Efeito |
|---|---|---|---|
| D1 | Usar só a visibilidade predominante; ignorar a mínima direcional | Usar a menor das duas (mais conservador) | Limite para o AI Assurance |
| D2 | Altura `///` em BKN/OVC/VV ou cobertura `//////` → recusa | Ignorar a camada | Mais recusas em estações AUTO |
| D3 | Sem nenhum grupo de nuvem → recusa | Tratar como sem teto | Conservador; caso raro |
| D4 | Horário mais de 5 min no futuro → recusa | Aceitar como idade 0 | Protege contra relógio errado |
| D5 | Pré-filtro só por lista de termos; erro de digitação ou paráfrase passa | Segundo passe com o LLM | Limite para o AI Assurance |
| D6 | Negação em até 3 palavras antes da expressão | Janela maior / LLM checador | Paráfrases passam; limite para o AI Assurance |
