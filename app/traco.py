"""Traço de cada execução do agente: prova de que rodou (REQ-A-13)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Callable

TIPOS_PASSO = {"prefiltro", "modelo", "ferramenta", "harness", "verificador", "erro"}


class Traco:
    def __init__(self, pergunta: str, *, modelo: str, versao_prompt: str,
                 relogio: Callable[[], datetime], pasta: Path | None = None):
        raise NotImplementedError

    def passo(self, tipo: str, **dados) -> None:
        raise NotImplementedError

    def gravar(self, resposta: dict | None) -> Path:
        raise NotImplementedError
