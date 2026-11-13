# Interface em chat — plano de implementação

> **Para agentes:** use superpowers:executing-plans (ou subagent-driven-development) tarefa por tarefa. Passos em
> checkbox (`- [ ]`).

**Objetivo:** trocar a página de formulário por um chat no estilo iMessage. Os status reais saem do traço depois
da resposta. A página antiga fica preservada em `/classico`.

**Arquitetura:** só o front-end muda (`app/static/index.html`, HTML + CSS + JS puro). O backend ganha uma rota que
serve a cópia intacta da página atual. O JS continua montando tudo com `el()`/`textContent`.

**Stack:** FastAPI (rota), HTML/CSS/JS sem dependências, pytest.

**Spec:** `specs/09-chat/design.md` (aprovada em 12/11/2026).

## Restrições globais

- Branch `chat-ui`; merge na `main` só depois da Tarefa 3.
- REQ-I-11: nada de `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write` ou `eval(` no HTML.
- REQ-I-16: nada de `http://`/`https://` nem `@import` (sem recurso externo, fontes do sistema).
- O texto do aviso continua sendo `prompts.AVISO`, exatamente como hoje. A página continua com `lang="pt-BR"`.
- O veredito exibido vem de `resp.veredito`, nunca do texto do modelo.
- Reaproveitar sem mudar a lógica: `el`, `icone`, `fmt*`, `seloPequeno`, `verificarSaude`, `cartaoPrevisao`,
  `cartaoExplicacao`, `preencherTextoBloqueado`, `carregarTraco`, `resumoPasso`, a tabela do traço, `abrirGravada`
  e o tema (`data-tema="escuro"` + `localStorage`).
- Contraste AA nos dois temas. `prefers-reduced-motion` desliga os pontinhos e o atraso entre as linhas de status.

## Pontos de atenção na revisão

1. **Duas perguntas seguidas:** o traço e o "ver traço" de cada balão precisam apontar para o próprio `id_traco`,
   não para uma variável global. Hoje `tracoAtual` é global e `#texto-bloqueado` é um id único.
2. **Traço que não abre** (404/rede): as linhas de status saem de `resp.avaliacoes` e a resposta aparece mesmo assim.
3. **Pergunta longa ou METAR comprido** num celular (375 px): sem rolagem horizontal da página. Só o METAR quebra
   ou rola dentro do próprio bloco.
4. **Enviar durante a espera:** o campo e o botão ficam travados até a resposta. O Enter não dispara duas vezes.
5. **Recusa do pré-filtro** (sem tool call): uma linha de status ("Pré-filtro recusou: pedido_ifr") e um balão
   RECUSA cinza, sem aeródromos com cara de erro.

---

### Task 1: reserva `/classico`

**Arquivos:**
- Criar: `app/static/classico.html` (cópia byte a byte do `index.html` atual da `main`)
- Modificar: `app/main.py` (constante `CLASSICO` ao lado de `INDEX`, mais a rota)
- Teste: `tests/test_main.py`

- [ ] `git switch -c chat-ui` e `cp app/static/index.html app/static/classico.html`
- [ ] Teste `test_classico_serve_a_pagina_antiga(tmp_path)`: `c.get("/classico")` dá 200, `text/html` e contém
      `prompts.AVISO` e `id="lista-demo"`. Estender os dois testes REQ-I-11/16 para os dois arquivos
      (`for arq in (INDEX, CLASSICO)`).
- [ ] Rodar `pytest tests/test_main.py -q`: o teste novo falha com 404.
- [ ] Rota `@app.get("/classico", include_in_schema=False)` → `FileResponse(CLASSICO, media_type="text/html")`.
- [ ] Rodar `pytest -q`: tudo passa.
- [ ] Commit "Reserva da interface atual em /classico".

### Task 2: página em chat

**Arquivos:** modificar `app/static/index.html` (reescrever estrutura, CSS e a parte do JS que monta a tela).

**Estrutura** (ids que o JS usa):
- `header`: avatar, "AgenteVFR", `#saude`, botão `#gravadas` (abre `#painel-gravadas` com `#lista-demo`), `#tema`
- `main#conversa` com `role="log"`, `aria-live="polite"` e `aria-busy`, rolável. Começa com uma boas-vindas do
  agente e `#sugestoes` (os 4 chips `.exemplo[data-pergunta]` de hoje, mesmo texto).
- `footer`: `form#form` com `#pergunta` (placeholder "Pergunte sobre um aeródromo — cada pergunta é
  independente", `maxlength=500`), `#enviar` (ícone de seta, `aria-label="Enviar"`) e o aviso `prompts.AVISO`
  em letra pequena.

**Funções novas/alteradas:**
- `balaoUsuario(texto) -> Element` e `balaoAgente(...filhos) -> Element` (avatar + balão, estilo C da spec).
- `mostrarDigitando() -> { no: Element, parar(): void }`: pontinhos + "N s", substitui `mostrarEspera`.
- `linhasStatus(dados, resp) -> string[]`: mapeia `dados.passos` nesta ordem e com estes textos:
  - `prefiltro` não passou → `Pré-filtro recusou: ${regra}`
  - `modelo` com `tool_calls` → `Modelo pediu ${nome}(${icao})`
  - `ferramenta` → `Buscou ${nome} de ${icao}: ${status}`
  - `harness` → `Harness: ${icao} ${veredito}` (+ ` (${codigo_recusa})`)
  - `verificador` → `Verificador: explicação aprovada` / `Verificador bloqueou a explicação (${regra})`
  - `erro` → `Erro: ${regra}`

  Sem `dados` → uma linha por `resp.avaliacoes`: `Harness: ${icao} ${veredito}`. Os bloqueios e os erros saem com
  a classe `status alerta`.
- `async mostrarStatus(linhas, destino)`: insere uma `div.status` por vez, com 250 ms entre elas (0 com
  reduced-motion).
- `respostaNoBalao(resp, gravadaEm) -> Element`: veredito, aeródromos, previsão (se houver), explicação e um
  `<details>` "Ver traço da execução". O traço é preenchido no `toggle` usando o `id_traco` **deste** balão
  (cache por id num `Map`). O texto bloqueado é localizado dentro do próprio balão, nunca por id global.
- `perguntar(texto)`: trava a barra, adiciona `balaoUsuario` e `mostrarDigitando`, faz o POST (mesmo timeout de
  330 s), remove os pontinhos, busca o traço e chama `mostrarStatus`, depois anexa `balaoAgente(respostaNoBalao(...))`
  e rola até o fim. Um erro vira `balaoAgente` com a classe `erro` e `role="alert"`.
- `abrirGravada(id, inicio)`: fecha o painel e anexa à conversa o par pergunta/resposta, com status e a etiqueta
  "Execução gravada em …".
- Ao clicar num chip: envia na hora. Depois da primeira pergunta, `#sugestoes` some, e um botão "Sugestões" na
  barra volta a mostrá-las.

- [ ] Reescrever a página conforme acima.
- [ ] `pytest -q`: tudo passa (REQ-I-01, 11 e 16 continuam valendo para o novo `index.html`).
- [ ] Commit "Interface em chat (spec 09)".

### Task 3: verificação no navegador (Compose rodando)

- [ ] `docker compose up -d --build app` e abrir `http://127.0.0.1:8000`.
- [ ] Ao vivo: "Dá pra ir VFR em Congonhas agora?" → pontinhos com segundos, linhas de status do traço real e
      balão com o veredito do código e os aeródromos visíveis.
- [ ] Recusa: "Posso decolar de Congonhas mesmo assim?" → uma linha do pré-filtro e o balão RECUSA.
- [ ] Gravadas: abrir uma com bloqueio (se houver) e uma janela TAF. Conferir o antes × depois e a faixa por hora
      dentro do balão.
- [ ] Duas perguntas seguidas: o "Ver traço" de cada balão mostra o seu próprio id.
- [ ] Tema escuro, largura de 375 px sem rolagem horizontal, e `/classico` abrindo a página antiga.
- [ ] Console sem erros. Corrigir o que aparecer, `pytest -q`, commit e perguntar ao usuário sobre o PR/merge.
