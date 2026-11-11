# 07 — STPA: plano (portão único)

**Estado:** aprovado em 11/11/2026 · **Pasta:** `stpa/` · **Base:** CLAUDE.md, seção STPA

## 1. Objetivo

Análise de perigos do AgenteVFR pelo método STPA, **gerada pelo Llama e revisada pelo grupo**. O resultado alimenta
dois pontos da apresentação: "o que o modelo decide × o que o sistema força" e "o limite que vai para o AI
Assurance" (cenários sem mitigação).

## 2. Como o Llama entra (o que é dele e o que é nosso)

- `stpa/rodar_stpa.py` manda ao `llama3.1:8b` do Compose (temperatura 0.1, semente 42) **quatro prompts em
  sequência**, um por passo do STPA. Cada saída é gravada sem edição em `stpa/saidas_llm/passo<N>.md` e entra como
  contexto do passo seguinte.
- O Llama recebe só a descrição do sistema (o que o usuário pergunta, os componentes, o que o modelo decide e o
  que o harness força), **sem** a lista de perigos que já temos (H1–H10). Assim dá para comparar o que ele achou
  sozinho com o que o grupo já tinha.
- `stpa/prompts_stpa.md` guarda os quatro prompts exatamente como foram enviados.
- `stpa/stpa.md` é a tabela final. Cada linha tem a origem: **LLM** (mantido), **LLM alterado** (com o que mudou),
  **grupo** (acrescentado), e uma seção com o que foi **descartado** da saída do LLM e por quê.
- Eu (Claude Code) escrevo um rascunho da revisão; **a revisão final é do grupo**, e o documento diz isso.

## 3. Os quatro passos

| Passo | Pede ao Llama | Sai em `stpa.md` |
|---|---|---|
| 1 | Perdas e perigos no nível do sistema | L1–L3, H1–Hn (comparados com H1–H10) |
| 2 | Estrutura de controle: controladores, ações de controle, realimentação | diagrama (texto) + lista de ações |
| 3 | Ações de controle inseguras (UCAs) nas 4 categorias: não fornecida, fornecida e insegura, cedo/tarde/fora de ordem, parada cedo/longa demais | tabela de UCAs ligada aos perigos |
| 4 | Cenários causais de cada UCA | tabela cenário → mecanismo do harness que mitiga (ou "não mitigado") |

**Estrutura de controle esperada** (para conferir a saída do passo 2): piloto ↔ interface ↔ agente (LLM) ↔
harness ↔ API meteorológica. Ações de controle principais: a pergunta do piloto; o LLM pedindo `buscar_metar` /
`avaliar_janela` com um ICAO; o harness emitindo veredito ou recusa; o verificador bloqueando a explicação; a
interface exibindo veredito e explicação; o piloto decidindo voar.

## 4. Saída que vai para a apresentação e o artigo

- Tabela curta "cenário → mecanismo que mitiga" com os 6–8 cenários mais importantes (slide).
- Lista dos **não mitigados**, que vai direto para a seção de AI Assurance. Já sabemos de alguns: H7 (aeródromo
  errado), H8 (aeródromo omitido), paráfrase que escapa do verificador, juiz = mesmo modelo, regra de pior caso do
  TAF, dependência da API.
- Uma figura simples da estrutura de controle (PNG, gerada em código), se couber no tempo.

## 5. Custo e ordem

- 4 chamadas ao Llama, ~2–4 min cada no CPU. **Rodam depois da avaliação**, que está usando o Ollama agora.
- Enquanto isso: escrevo os prompts e o script (sem rodar).
- Sem testes automatizados: é análise, não código do sistema. O script só grava saídas.

## 6. Fora do escopo

STPA de segurança da informação (STPA-Sec); análise quantitativa de probabilidade; revisão por especialista
externo. Ficam citados como trabalho futuro no artigo.
