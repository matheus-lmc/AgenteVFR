# 04 — Interface e Docker: tarefas

Cada tarefa só é marcada quando os testes citados passam.

## Portão 3 — testes (vermelho)

- [ ] T1. `requirements.txt` com `fastapi`, `uvicorn`, `pydantic` fixados; instalar na `.venv`
- [ ] T2. `app/main.py` só com `criar_app` e rotas respondendo 501; `app/static/index.html` mínimo
- [ ] T3. `tests/test_main.py` (I-01 a I-05, I-11, I-16)
- [ ] T4. Rodar `pytest`: novos falham; os anteriores continuam verdes

## Portão 4 — implementação (verde)

- [ ] T5. Rotas da API — I-01 a I-06
- [ ] T6. `index.html` — I-07 a I-16
- [ ] T7. `Dockerfile`, `.dockerignore`, serviço `app` no Compose — I-17, I-18
- [ ] T8. `pytest` todo verde

## Portão 5 — fechamento

- [ ] T9. Conferência no navegador (360 px e 1280 px, teclado, exemplos, execução gravada, Ollama desligado)
- [ ] T10. `docker compose up` e 5 perguntas pela página; tempo médio — I-19
- [ ] T11. Matriz de rastreabilidade e commit
