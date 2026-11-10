"""API e página do AgenteVFR (FastAPI).

Especificação: specs/04-interface/requisitos.md e specs/04-interface/design.md.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import httpx
from fastapi import FastAPI


def verificar_saude_ollama(*, url: str | None = None, modelo: str | None = None,
                           http: httpx.Client | None = None) -> dict:
    raise NotImplementedError


def criar_app(*, agente=None, pasta_traces: Path | None = None, pasta_demo: Path | None = None,
              verificar_saude: Callable[[], dict] | None = None) -> FastAPI:
    raise NotImplementedError
