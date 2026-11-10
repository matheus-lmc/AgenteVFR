# 03 — Agente, prompt e traço: tarefas

Cada tarefa só é marcada quando os testes citados passam.

## Antes do portão 3

- [x] T1. Ollama no Compose de pé com `llama3.1:8b` e `llama3.2:3b`; confirmar o formato real de
      `/api/chat` com ferramentas (seção 3 do design) e ajustar o design se diferir — 10/11/2026: formato
      confirmado no Ollama 0.40.11 (`message.tool_calls[].function.{name, arguments}`, argumentos como objeto);
      única diferença: campo extra `id` em cada chamada, ignorado pelo agente. Design não precisou mudar.

## Portão 3 — testes (vermelho)

- [x] T2. `pyproject.toml`: marcador `ollama` fora da execução padrão
- [x] T3. Esqueletos de `prompts.py`, `traco.py`, `agente.py`
- [x] T4. `tests/test_prompts.py`, `tests/test_traco.py`, `tests/test_agente.py`
- [x] T5. Rodar `pytest`: novos falham; os 216 anteriores continuam verdes — 10/11/2026: 58 falham (54 `NotImplementedError`, 4 asserções sobre o esqueleto vazio); passam os 216 anteriores e 2 novos que o esqueleto já satisfaz (`TIPOS_PASSO`, prompt sem ICAO)

## Portão 4 — implementação (verde)

- [x] T6. `prompts.py` — A-12
- [x] T7. `traco.py` — A-13
- [x] T8. `ClienteOllama` — A-06, A-11
- [x] T9. Loop, `_executar`, veredito geral e verificação — A-01 a A-10
- [x] T10. `pytest` todo verde

## Portão 5 — fechamento

- [ ] T11. Teste `ollama` com o modelo real; medir tempo por pergunta com `llama3.1:8b` e `llama3.2:3b` —
      10/11/2026, com `num_thread=4` no código (REQ-A-11 revisado): `llama3.1:8b` respondeu em 16 s, mas
      `test_req_a14_ollama_real` **falha** de forma reprodutível — o modelo avalia `SBKP` (Campinas) para
      "Guarulhos" (perigo H7). O teste fica como está até a mitigação do H7 entrar.
- [ ] T12. Rodar à mão os 3 exemplos da demo (VMC, IMC/recusa, Miami) e guardar os traços
- [ ] T13. Matriz de rastreabilidade e commit

## Achados com o modelo real (10/11/2026)

- **Velocidade depende de `num_thread`.** O M3 tem 4 núcleos de desempenho + 4 de eficiência; o Ollama usa 8
  threads por padrão e a geração despenca. Medido no contêiner:

  | Modelo | Threads | Leitura do prompt | Geração |
  |---|---|---|---|
  | `llama3.2:3b` | 8 (padrão) | 10,4 tok/s | **0,49 tok/s** |
  | `llama3.2:3b` | 4 | 128 tok/s | 31,7 tok/s |
  | `llama3.1:8b` | 4 | 40,9 tok/s | 13,7 tok/s |
  | `llama3.1:8b` | 3 | 37,0 tok/s | 14,3 tok/s |

  Com 8 threads, uma pergunta levou 618 s (e uma chamada estourou os 300 s). Com 4 threads (experimento fora
  do código), o agente com o 8b respondeu em 13–37 s. **Proposta:** revisar o REQ-A-11 para mandar
  `num_thread` (variável `OLLAMA_NUM_THREAD`, padrão 4).
- **Novo perigo — H7: o modelo mapeia o nome para o aeródromo errado.** O 8b converteu "Guarulhos" em `SBKP`
  (Campinas); o veredito saiu VMC para Campinas e a explicação dizia "Guarulhos". Nenhuma checagem pegou: o
  ICAO é válido, brasileiro e foi avaliado. A API devolve o nome da estação (`"Campinas/Viracopos Arpt, SP, BR"`),
  que hoje não chega à janela nem à resposta. **Proposta:** levar o nome da estação para a janela e para a
  resposta (a interface mostra "SBKP — Campinas/Viracopos") e, no prompt v2, pedir que o modelo confira se a
  estação é a pedida. Vai para STPA e AI Assurance.
- **O `llama3.2:3b` não serve para a demo.** Gerou `SGU` e `GRUO` para Guarulhos, depois inventou `SBJZ` e
  `SBBR` e escreveu explicação contraditória. O harness segurou (RECUSA, texto descartado), mas a experiência é
  ruim. Manter `llama3.1:8b` como padrão.
- **O que funcionou como esperado com o modelo real:** "Miami nos próximos 5 dias" recusada pelo pré-filtro em
  0 s; "Miami agora" virou `KIMM` (deveria ser `KMIA`) e foi recusada por escopo sem chamar a API; Congonhas
  com internet lenta → 2 × tempo esgotado na API → RECUSA (`erro_api`), sem dado inventado.
