"""API e página do AgenteVFR (FastAPI).

Especificação: specs/04-interface/requisitos.md e specs/04-interface/design.md.
Rodar: uvicorn app.main:app --port 8000
"""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Callable

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, StrictStr

from app.agente import OLLAMA_MODEL_PADRAO, OLLAMA_URL_PADRAO, Agente

INDEX = Path(__file__).resolve().parent / "static" / "index.html"
CLASSICO = Path(__file__).resolve().parent / "static" / "classico.html"
TIMEOUT_SAUDE_S = 5.0
_RE_ID_TRACO = re.compile(r"[0-9a-f]{12}")  # REQ-I-03: validado antes de qualquer acesso ao disco
_log = logging.getLogger("agentevfr")


class Pergunta(BaseModel):
    pergunta: StrictStr  # número ou null → 422; texto vazio passa (quem recusa é o agente)


def verificar_saude_ollama(*, url: str | None = None, modelo: str | None = None,
                           http: httpx.Client | None = None) -> dict:
    """REQ-I-05: o Ollama responde e o modelo está baixado? Nunca lança exceção."""
    url = (url or os.environ.get("OLLAMA_URL") or OLLAMA_URL_PADRAO).rstrip("/")
    modelo = modelo or os.environ.get("OLLAMA_MODEL") or OLLAMA_MODEL_PADRAO
    cliente = http or httpx.Client()
    try:
        r = cliente.get(f"{url}/api/tags", timeout=TIMEOUT_SAUDE_S)
        r.raise_for_status()
        nomes = {m.get("name") for m in r.json().get("models", []) if isinstance(m, dict)}
    except (httpx.HTTPError, ValueError, AttributeError, TypeError):
        return {"ollama": False, "modelo": modelo, "modelo_baixado": False}
    finally:
        if http is None:
            cliente.close()
    return {"ollama": True, "modelo": modelo, "modelo_baixado": modelo in nomes}


def criar_app(*, agente=None, pasta_traces: Path | None = None, pasta_demo: Path | None = None,
              verificar_saude: Callable[[], dict] | None = None) -> FastAPI:
    pasta_traces = Path(pasta_traces if pasta_traces is not None else os.environ.get("TRACES_DIR", "traces"))
    pasta_demo = Path(pasta_demo) if pasta_demo is not None else pasta_traces / "demo"
    agente = agente or Agente(pasta_traces=pasta_traces)  # um agente por processo (D6)
    verificar_saude = verificar_saude or verificar_saude_ollama

    app = FastAPI(title="AgenteVFR", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/", include_in_schema=False)
    def pagina():  # REQ-I-01
        return FileResponse(INDEX, media_type="text/html")

    @app.get("/classico", include_in_schema=False)
    def pagina_classica():  # backup permanente da interface anterior (plano B da demo)
        return FileResponse(CLASSICO, media_type="text/html")

    @app.post("/api/perguntar")
    def perguntar(corpo: Pergunta):  # REQ-I-02
        try:
            return agente.perguntar(corpo.pergunta).para_dict()
        except Exception:
            _log.exception("falha ao processar a pergunta")  # detalhe só no log do servidor
            return JSONResponse(status_code=500, content={"erro": "falha interna ao processar a pergunta"})

    @app.get("/api/traco/{id_traco}")
    def traco(id_traco: str):  # REQ-I-03, REQ-I-04
        if not _RE_ID_TRACO.fullmatch(id_traco):
            raise HTTPException(status_code=404, detail="traço não encontrado")
        for pasta in (pasta_traces, pasta_demo):
            achados = sorted(pasta.glob(f"*_{id_traco}.json")) if pasta.is_dir() else []
            if achados:
                return json.loads(achados[0].read_text(encoding="utf-8"))
        raise HTTPException(status_code=404, detail="traço não encontrado")

    @app.get("/api/demo")
    def demo():  # REQ-I-04
        itens = []
        for arquivo in (pasta_demo.glob("*.json") if pasta_demo.is_dir() else []):
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            resposta = dados.get("resposta") or {}
            itens.append({"id": dados.get("id"), "pergunta": dados.get("pergunta"),
                          "veredito": resposta.get("veredito"), "inicio": dados.get("inicio")})
        return sorted(itens, key=lambda i: i["inicio"] or "", reverse=True)

    @app.get("/api/saude")
    def saude():  # REQ-I-05
        try:
            return verificar_saude()
        except Exception:
            return {"ollama": False, "modelo": None, "modelo_baixado": False}

    return app


app = criar_app()
