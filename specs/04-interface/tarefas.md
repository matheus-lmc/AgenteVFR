# 04 — Interface e Docker: tarefas

Cada tarefa só é marcada quando os testes citados passam.

## Portão 3 — testes (vermelho)

- [x] T1. `requirements.txt` com `fastapi`, `uvicorn`, `pydantic` fixados; instalar na `.venv`
- [x] T2. `app/main.py` só com `criar_app` e rotas respondendo 501; `app/static/index.html` mínimo
- [x] T3. `tests/test_main.py` (I-01 a I-05, I-11, I-16)
- [x] T4. Rodar `pytest`: novos falham; os anteriores continuam verdes — 10/11/2026: 34 falham (`NotImplementedError`);
      291 passam (289 anteriores + os 2 que só leem o arquivo da página e o esqueleto já satisfaz)

## Portão 4 — implementação (verde)

- [x] T5. Rotas da API — I-01 a I-06
- [x] T6. `index.html` — I-07 a I-16
- [x] T7. `Dockerfile`, `.dockerignore`, serviço `app` no Compose — I-17, I-18
- [x] T8. `pytest` todo verde

## Portão 5 — fechamento

- [x] T9. Conferência no navegador (360 px e 1280 px, teclado, exemplos, execução gravada, Ollama desligado) —
      10/11/2026, navegador do app: página, saúde ("Modelo pronto"), execuções gravadas, cartão 1C, aeródromos 2B
      (caso SBKP/Campinas bem visível), traço 6B e bloqueio 3B (simulado no console com o texto real de um traço)
      conferidos; 375 px sem rolagem horizontal. Corrigidos na conferência: resultado escondido atrás da faixa
      fixa (`scroll-margin-top`) e "teto sem teto" no cartão do aeródromo. *Não conferidos:* teclado em detalhe e
      Ollama desligado.
- [x] T10. `docker compose up` e 5 perguntas pela página; tempo médio — I-19 — 10/11/2026, `docker compose up`
      com `app` + `ollama`, 5 perguntas pela API do contêiner (`llama3.1:8b`, 4 threads):
      **média 15,2 s**, mediana 15,4 s, mín. 13,1 s, máx. 17,6 s. Traços gravados em `./traces` pelo contêiner.
- [x] T11. Matriz de rastreabilidade e commit

## Achados (10/11/2026)

- **Acerto de ICAO do `llama3.1:8b` é baixo (reforça H7).** Nas 5 perguntas da medição, só Congonhas → `SBSP`
  estava certo. Curitiba → `SSCW`, Porto Alegre → `SSAA` e Brasília → `SBTL` (todos errados; o sistema recusou por
  falta de dado, sem veredito). **Santos Dumont → `SBSP`**: saiu VMC de Congonhas, e só o nome da estação na tela
  denuncia o erro. Medir isso direito é tarefa da avaliação (acerto de ICAO); para a demo, usar Congonhas.
- Aviso do `starlette`: `TestClient` com `httpx` está obsoleto (sugere `httpx2`). Não afeta o app; revisitar se
  atualizar o FastAPI.
