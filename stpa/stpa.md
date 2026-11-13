# STPA do AgenteVFR

**Estado:** rascunho da revisão escrito pelo Claude Code em 11/11/2026 a partir da saída do Llama. **Falta a
revisão do grupo** (marcar ✔ ou corrigir cada linha). · **Plano:** `specs/07-stpa/plano.md` · **Prompts:**
`prompts_stpa.md` · **Saída bruta do Llama (sem edição):** `saidas_llm/passo1.md` … `passo4.md`

**Origem de cada linha:** **LLM** = mantida como o Llama escreveu · **LLM alt.** = aproveitada da saída do Llama
com alteração (o que mudou está na linha) · **grupo** = acrescentada na revisão. O que foi descartado da saída do
Llama está na seção 6, com o motivo.

## Revisão do grupo (REQ-S-01, spec 08)

A Aula 10 cobra que uma pessoa aceite o rascunho do LLM. Preencher antes de apresentar o STPA como revisado;
enquanto não estiver completo, a apresentação diz "revisão do grupo em andamento".

| Seção | Revisada por (iniciais) | Data | Correções feitas |
|---|---|---|---|
| 1. Perdas | | | |
| 2. Perigos | | | |
| 3. Estrutura de controle | | | |
| 4. UCAs | | | |
| 5. Cenários e mitigação | | | |
| 7. Não mitigados | | | |

## 0. Resumo: o que o Llama fez bem e mal

| Passo | O Llama escreveu | Aproveitado | Problema principal |
|---|---|---|---|
| 1 Perdas e perigos | 4 perdas, 8 perigos | 3 perdas; 5 perigos (1 sem mudança, 4 reescritos) | 4 dos 8 "perigos" são **causas** ("falha no pré-filtro"), não estados do sistema; não achou dado inventado, resposta sem consulta, aeródromo omitido, HTML do modelo, previsão lida como observação |
| 2 Estrutura de controle | 5 componentes, 7 ligações | a lista de componentes | **pôs o cálculo do veredito no agente (LLM)**, ao contrário da descrição que recebeu; não modelou pré-filtro nem verificador como ações de controle |
| 3 UCAs | 16 | 4 (reescritas) | ações de controle CA1–CA16 que não existem no passo 2; 3 UCAs repetidas; UCAs de tempo impossíveis num fluxo síncrono |
| 4 Cenários causais | 16 | nenhum | **todos "não mitigado"**, ignorando os mecanismos do harness descritos no prompt; tabela com coluna faltando |

**Achado para o artigo:** o `llama3.1:8b`, ao fazer o STPA do próprio sistema, repetiu o erro que o harness existe
para evitar: atribuiu ao modelo de linguagem a decisão do veredito. A análise assistida por LLM serviu como
esqueleto e lista de verificação; a substância veio da revisão.

## 1. Perdas

| Id | Perda | Origem |
|---|---|---|
| L1 | Morte ou lesão de pessoas (piloto, passageiros, terceiros no solo) | LLM alt. (L1; incluídos terceiros) |
| L2 | Dano à aeronave ou a propriedade | LLM alt. (L2; "infraestrutura de aeródromo" generalizada) |
| L3 | Perda de confiança no sistema ou uso dele no lugar do briefing oficial | LLM alt. (L4 "reputação" reescrita como perda de confiança, como no CLAUDE.md) |

## 2. Perigos (estados do sistema)

Os ids seguem os que já usamos nas specs (H1–H10).

| Id | Perigo | Perdas | Origem |
|---|---|---|---|
| H1 | Sistema apresenta VMC quando a condição real no aeródromo pedido é IMC | L1, L2 | LLM alt. (H3 "dados incorretos ou ausentes" é causa; reescrito como estado) |
| H2 | Sistema usa dado desatualizado como se fosse atual | L1, L2 | LLM alt. (H7 "fora da validade") |
| H3 | Explicação contradiz o veredito | L1, L2, L3 | LLM (H6) |
| H4 | Sistema responde a pedido fora do escopo (IFR, fora do Brasil, além do TAF, "ignore a regra", "mesmo assim") | L1, L3 | LLM alt. (H5 "falha no pré-filtro" é causa; reescrito como estado) |
| H5 | Explicação cita dado que não está nos dados consultados | L1, L3 | grupo |
| H6 | Sistema responde sem ter consultado dado | L1, L3 | grupo |
| H7 | Sistema avalia aeródromo diferente do pedido | L1, L2 | LLM alt. (H1 "erro de interpretação da pergunta" é causa; reescrito como estado) |
| H8 | Sistema omite aeródromo pedido | L1, L2 | grupo |
| H9 | Texto do modelo executado como código na página | L3 | grupo |
| H10 | Previsão (TAF) apresentada ou lida como observação | L1, L2 | grupo |

## 3. Estrutura de controle

Reescrita pelo grupo. A do Llama (passo 2) punha o veredito no agente; aqui ele está no harness, como no sistema.

```
 Piloto em comando ──────────────── CA7 decide voar VFR ───────────────▶ voo (processo físico)
   │ CA1 pergunta                                ▲ R3 veredito, aeródromos consultados (nome da
   ▼                                             │    estação), METAR bruto, explicação, traço, aviso
 Interface web ◀──────────────────────────────────┘
   │                       ▲ CA4 veredito/recusa   ▲ CA6 explicação (texto)
   ▼                       │ CA5 libera/bloqueia   │
 Harness: pré-filtro ── CA2 libera ou recusa ──▶ Agente (llama3.1:8b)
 Harness: regra, escopo,     ◀── CA3 buscar_metar / avaliar_janela (ICAO) ──┘
 idade, verificador          ── R2 resumo compacto (veredito, motivo, nome da estação) ──▶ Agente
   ▲ R1 METAR/TAF bruto
 API aviationweather.gov (cache 5 min)
```

| Id | De → para | Tipo | Descrição | Origem |
|---|---|---|---|---|
| CA1 | Piloto → agente (pela interface) | ação de controle | pergunta em linguagem natural | LLM |
| CA2 | Harness (pré-filtro) → agente | ação de controle | libera a pergunta para o modelo ou recusa antes dele | grupo |
| CA3 | Agente → harness/ferramentas | ação de controle | pede `buscar_metar` ou `avaliar_janela` com um ICAO | LLM alt. ("obter dados"; agora com o ICAO, que é decisão do modelo) |
| CA4 | Harness → interface | ação de controle | emite o veredito VMC/IMC ou a recusa, calculados em código | grupo (o Llama atribuiu ao agente) |
| CA5 | Harness (verificador) → interface | ação de controle | libera a explicação do modelo ou a bloqueia e troca pelo texto em código | grupo |
| CA6 | Agente → interface | ação de controle | explicação em texto | LLM alt. (o Llama mandava "veredito e explicação") |
| CA7 | Piloto → voo | ação de controle | decide voar VFR | grupo |
| R1 | API → harness | realimentação | METAR/TAF bruto | LLM |
| R2 | Harness → agente | realimentação | só o resumo compacto (Context Engineering); o bruto fica no traço | LLM alt. (acrescentado o que entra na janela) |
| R3 | Interface → piloto | realimentação | veredito, aeródromos consultados com nome da estação, METAR, explicação, traço, aviso fixo | LLM alt. (acrescentados aeródromos consultados e aviso) |

**Modelos de processo (o que cada controlador precisa saber):**

| Controlador | Precisa saber | Onde pode errar | Origem |
|---|---|---|---|
| Piloto | que o veredito é do aeródromo que ele pediu, de agora, e não substitui o briefing oficial | lê o veredito sem conferir os aeródromos consultados | grupo |
| Agente (LLM) | qual ICAO corresponde a cada nome; quantos aeródromos a pergunta tem | mapeia por memória, sem base de dados (H7, H8) | grupo |
| Harness | regra de mínimos, relógio UTC, escopo, formato do METAR/TAF | formato não previsto; relógio errado | grupo |

## 4. Ações de controle inseguras (UCAs)

Categorias: (a) não fornecida causa perigo · (b) fornecida causa perigo · (c) cedo, tarde ou fora de ordem ·
(d) parada cedo demais ou aplicada por tempo demais.

| Id | CA | Cat. | UCA (contexto em que é insegura) | Perigos | Origem |
|---|---|---|---|---|---|
| UCA1 | CA3 | a | Agente não consulta um dos aeródromos pedidos (pergunta com origem e destino) | H8, H1 | LLM alt. (UCA4 "parar de chamar ferramentas antes de obter dados") |
| UCA2 | CA3 | b | Agente consulta o ICAO de outro aeródromo | H7, H1 | grupo |
| UCA3 | CA3 | b | Agente consulta um aeródromo que a pergunta não cita | H6, H7 | grupo (achado da avaliação, R09) |
| UCA4 | CA2 | a | Pré-filtro não recusa pedido fora do escopo escrito com outras palavras | H4 | LLM alt. (UCA2) |
| UCA5 | CA2 | b | Pré-filtro recusa pergunta legítima | L3 | grupo |
| UCA6 | CA4 | b | Harness emite VMC a partir de METAR de outra estação ou mal decodificado | H1 | LLM alt. (UCA6/UCA12 "dados que causam perigo") |
| UCA7 | CA4 | b | Harness emite veredito com METAR desatualizado | H2 | LLM alt. (UCA6/UCA12, exemplo "mais de 60 min") |
| UCA8 | CA4 | a | Harness não recusa quando o dado está ausente ou ilegível | H1, H6 | LLM alt. (UCA5/UCA11) |
| UCA9 | CA5 | a | Verificador não bloqueia explicação que contradiz o veredito | H3 | LLM alt. (UCA10, exemplo do próprio Llama) |
| UCA10 | CA5 | b | Verificador bloqueia explicação correta | L3 | grupo |
| UCA11 | CA6 | b | Explicação com dado inventado, ou previsão do TAF apresentada como condição atual | H5, H10 | grupo |
| UCA12 | CA4 | d | Veredito de uma consulta guardada em cache continua sendo exibido depois que a condição mudou | H2 | grupo |
| UCA13 | CA7 | b | Piloto decide voar VFR com base no sistema, sem o briefing oficial | H1–H10 → L1 | grupo |

## 5. Cenários causais e mitigação

| Id | UCA | Cenário causal | Mecanismo que mitiga | Mitigado? | Origem |
|---|---|---|---|---|---|
| CS1 | UCA2 | O modelo 8B mapeia nome → ICAO por memória: "Guarulhos" → SBKP, "Santos Dumont" → SBSP, "Brasília" → SBTL (avaliação: ICAO exato 6–8 de 14) | nome da estação na janela do modelo e na interface (só transparência) | **não** | grupo |
| CS2 | UCA1 | Pergunta com dois aeródromos; o modelo consulta só um e responde pelos dois ("Sim, dá pra ir de Guarulhos pra Congonhas" com Campinas CAVOK e Congonhas IMC, avaliação v3 P13) | lista "aeródromos consultados" na interface | **não** | grupo |
| CS3 | UCA3 | Pergunta sem aeródromo; o modelo escolhe um sozinho (SBSP ou SBGR, avaliação R09) | nenhum | **não** | grupo |
| CS4 | UCA4 | Pedido de pressão com palavras fora da lista ("vou de qualquer jeito") | o veredito continua sendo do código; o pedido não muda VMC/IMC | parcial | LLM alt. (CS2 "modelo de processo não configurado") |
| CS5 | UCA6 | A API devolve METAR de outra estação | recusa por ICAO divergente (REQ-H-04) | sim | grupo |
| CS6 | UCA6 | Formato de METAR não previsto (grupo novo, RMK, erro de digitação) | grupo desconhecido é ignorado; visibilidade ou nuvens ilegíveis → recusa por dado indisponível; 443 testes; 40/40 contra o gabarito | parcial (40 casos; um grupo de nuvens com erro de digitação que pareça válido não seria pego) | grupo |
| CS7 | UCA7 | A estação para de emitir e a API entrega o último METAR | recusa acima de 60 min; Galeão recusado na avaliação | sim | LLM alt. (CS12 "dados perigosos") |
| CS8 | UCA8 | METAR NIL ou com `////` | recusa por dado ausente/ilegível | sim | grupo |
| CS9 | UCA9 | O modelo contradiz o veredito com uma paráfrase que as regras de palavras não conhecem | verificador por regras com polaridade e negação; o veredito exibido continua do código | parcial | LLM alt. (CS10) |
| CS10 | UCA10 | Negação ou frase condicional confunde as regras ("não está bom, mas...") | o texto-modelo em código substitui a explicação; falha segura | sim | grupo |
| CS11 | UCA11 | O modelo acrescenta vento, tendência ou outro aeródromo que não consultou | bloqueio de ICAO não avaliado (só para códigos, não para nomes); juiz na avaliação | parcial | grupo |
| CS12 | UCA11 | O piloto lê a melhor janela do TAF como tempo de agora | janela separada e rotulada "previsão"; veredito de agora vem do METAR; verificador por horário | parcial | grupo |
| CS13 | UCA12 | Cache de 5 min durante a demo | cache não serve METAR com mais de 55 min; a idade é recalculada a cada resposta | sim | grupo |
| CS14 | UCA5 | Palavra da lista numa pergunta legítima ("instrumentos" numa pergunta VFR) | falha segura (recusa com motivo) | sim (aceito) | grupo |
| CS15 | UCA13 | Viés de automação: o piloto confia no verde | aviso fixo; recusa de "mesmo assim"; motivo e METAR sempre visíveis | parcial (fora do sistema) | grupo |
| CS16 | — (H9) | Texto do modelo com HTML ou script | a interface só usa `textContent` | sim | grupo |

## 6. Descartado da saída do Llama

| Item do Llama | Motivo |
|---|---|
| L3 prejuízo econômico | consequência de L2; fora do foco do protótipo |
| H2 falha de comunicação agente–interface | é causa, não estado do sistema; e a falha é segura (sem resposta, sem veredito) |
| H4 limite de chamadas de ferramenta | é uma mitigação (evita laço infinito), não um perigo |
| H8 falha no verificador | é causa de H3, coberta em CS9 |
| UCA1 piloto não faz pergunta | não leva a perigo |
| UCA3, UCA7, UCA15 "enviar antes de calcular" | repetidas entre si e impossíveis no fluxo síncrono |
| UCA8, UCA13, UCA14, UCA16 | parada/tempo sem sentido para chamadas síncronas; texto repetido |
| UCA9 interface não exibe veredito | falha segura (sem veredito, sem decisão apoiada no sistema) |
| CS1–CS16 | todos "não mitigado" ignorando os mecanismos descritos; cenários genéricos ("modelo de processo não configurado") |

## 7. Não mitigados → seção de AI Assurance

1. **H7 / CS1:** o modelo troca o aeródromo (ICAO exato 6–8 de 14). Só há transparência (nome da estação).
2. **H8 / CS2:** o modelo omite um dos aeródromos e responde pelos dois. Caso medido: "sim" com o destino IMC.
3. **H6 / CS3:** pergunta sem aeródromo é respondida com um aeródromo escolhido pelo modelo.
4. **H3 / CS9 (parcial):** paráfrase de contradição escapa do verificador por regras.
5. **H5 / CS11 (parcial):** dado inventado em linguagem natural só é pego se for código ICAO; o juiz é o mesmo
   modelo e erra nos dois sentidos.
6. **H10 / CS12 (parcial):** a regra de pior caso do TAF pode ser conservadora demais, e a previsão pode ser lida
   como observação.
7. **CS6 (parcial):** a decodificação foi conferida em 40 METARs reais e nos testes; formatos raros não foram
   vistos.
8. **CS15:** viés de automação do piloto está fora do sistema; o aviso fixo é a única barreira.

**Mitigações possíveis, não implementadas (trabalho futuro):** tabela nome → ICAO em código, conferida contra a
pergunta (H7/H6); exigir que cada aeródromo citado na pergunta tenha sido consultado (H8); segundo passe de
verificação com LLM (H3).
