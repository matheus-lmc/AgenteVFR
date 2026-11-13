# 09 — Interface em chat (design curto)

Status: **aprovada em 12/11/2026; implementada no branch chat-ui**. Muda só a apresentação da página; regra, harness, agente e API ficam
como estão.

## Por quê

O MVP funciona, mas a página é um formulário com cartões empilhados. O grupo quer uma página **usável como um chat**:
o campo embaixo, a conversa em cima, o AgenteVFR respondendo em balões com avatar e mostrando os passos que executou
("Buscou o METAR de SBSP", "Verificando VMC"). O estilo escolhido foi o **C: limpo, no estilo iMessage**.

## Abordagens consideradas

| | Como | Escolha |
|---|---|---|
| 1 | Status **reais, mostrados quando a resposta chega**: durante a espera só "digitando…" com segundos; depois as linhas de status saem do traço (`/api/traco/{id}`), uma a uma, e então o balão da resposta | **escolhida** |
| 2 | Status ao vivo com streaming (SSE): endpoint novo no `main.py`, callback de progresso no `agente.py` | depois de 13/11 (mexe no núcleo na véspera) |
| 3 | Status por cronômetro no navegador | descartada: pode citar passo que não aconteceu |

## O que muda (só `app/static/index.html`, mais a reserva abaixo)

- **Layout de chat:** cabeçalho fino (avatar, "AgenteVFR", saúde do modelo, botão de tema), conversa rolável no meio,
  barra fixa embaixo com campo + botão de enviar (ícone de seta). Enter envia. Rola sozinho para a última mensagem.
- **Balão do usuário** à direita (azul, cantos de 16 px). **Balão do agente** à esquerda, cinza claro, com avatar
  (imagem do piloto, JPEG embutido, a pedido do grupo; não o ícone de avião) — no tema escuro, as mesmas cores atuais do tema escuro.
- **Espera:** balão do agente com três pontinhos animados + "N s" (respeita `prefers-reduced-motion`).
- **Status (abordagem 1):** ao chegar a resposta, linhas discretas centralizadas, tiradas dos `passos` do traço, nesta
  ordem e com intervalo curto (~250 ms; sem animação se `prefers-reduced-motion`):
  - `prefiltro` bloqueou → "Pré-filtro recusou: <regra>"
  - `modelo` com `tool_calls` → "Modelo pediu buscar_metar(SBSP)"
  - `ferramenta` → "Buscou o METAR de SBSP (idade N min)" / "sem dado"
  - `harness` → "Harness: SBSP VMC" / "recusou (<código>)"
  - `verificador` → "Verificador: sem contradição com o veredito (não confere valores)" / "**bloqueou** a explicação" (em destaque)
  Se o traço não abrir, as linhas saem de `resp.avaliacoes` (menos detalhe, mas nada inventado).
- **Balão da resposta:** dentro dele, nesta ordem, o conteúdo que já existe hoje, compactado:
  1. cartão do veredito VMC/IMC/RECUSA (cor + ícone + motivo; teto e visibilidade com os mínimos);
  2. aeródromos consultados (nome da estação + ICAO + METAR bruto) — continua visível sem clique (defesa H7/H8);
  3. previsão pelo TAF quando houver (faixa por hora);
  4. explicação, com "Explicação do modelo" / "Texto gerado pelo sistema" e o antes × depois do bloqueio;
  5. "Ver traço da execução" recolhido (a tabela atual).
- **Erros** (rede, 422, tempo esgotado) viram um balão do agente com estilo de erro, sem cara de veredito (REQ-I-14).
- **Sugestões:** os 4 exemplos viram chips acima do campo, visíveis enquanto a conversa está vazia e num botão
  "Sugestões" depois.
- **Execuções gravadas:** botão "Gravadas" no cabeçalho abre a lista; abrir uma insere na conversa o par
  pergunta/resposta com a etiqueta "Execução gravada em …".
- **Aviso fixo** "Ferramenta acadêmica. Não substitui o briefing meteorológico oficial." fica numa linha pequena
  logo abaixo da barra de envio.
- **Sem memória entre perguntas** (o agente não guarda contexto): o campo diz "Pergunte sobre um aeródromo — cada
  pergunta é independente". *Escolha do Claude.*

## Invariantes que continuam valendo

REQ-I-08 a 16: veredito só do código; texto do modelo sempre como texto (`textContent`, nunca `innerHTML`); sem
recursos externos; pt-BR; contraste AA; `aria-live` na conversa. Os testes de `tests/test_main.py` que leem o HTML
continuam passando.

Exceção: a página de chat abandona o contador visível de caracteres do REQ-I-07
(`specs/04-interface/requisitos.md`). O `maxlength=500` continua; o contador segue em `/classico`.
Também saem da página de chat o **logo do grupo** (DD17 da spec 04) e o **fundo decorativo** (DD16): o cabeçalho
passa a ter o avatar do piloto. Os dois continuam em `/classico`. **Pendente:** o grupo confirmar que quer o logo
fora da tela principal (o logo foi pedido em 10/11; o avatar, em 12/11).

## Reserva para a demo (escolha do Claude)

A página atual é copiada, sem mudança, para `app/static/classico.html` e servida em `GET /classico` (uma rota no
`main.py` + um teste). Se o chat der problema na apresentação, abre-se `/classico`. Tudo num branch `chat-ui`;
merge só depois de testado no navegador com o Compose.

## Fica para depois

Streaming real (abordagem 2), memória de conversa ("e Guarulhos?"), confirmação do aeródromo (D1 da spec 08).
