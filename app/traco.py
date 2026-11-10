"""Traço de cada execução do agente: prova de que rodou (REQ-A-13)."""

from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

TIPOS_PASSO = {"prefiltro", "modelo", "ferramenta", "harness", "verificador", "erro"}


class Traco:
    def __init__(self, pergunta: str, *, modelo: str, versao_prompt: str,
                 relogio: Callable[[], datetime], pasta: Path | None = None):
        self.id = secrets.token_hex(6)
        self._inicio = relogio().astimezone(timezone.utc)
        self._t0 = time.perf_counter()
        self._pasta = Path(pasta if pasta is not None else os.environ.get("TRACES_DIR", "traces"))
        self._dados = {
            "id": self.id,
            "inicio": self._inicio.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "pergunta": pergunta,
            "modelo": modelo,
            "versao_prompt": versao_prompt,
            "passos": [],
        }

    def _ms(self) -> int:
        return int((time.perf_counter() - self._t0) * 1000)

    def passo(self, tipo: str, **dados) -> None:
        if tipo not in TIPOS_PASSO:
            raise ValueError(f"tipo de passo desconhecido: {tipo}")
        self._dados["passos"].append({"tipo": tipo, "t_ms": self._ms(), **dados})

    def gravar(self, resposta: dict | None) -> Path:
        self._pasta.mkdir(parents=True, exist_ok=True)
        caminho = self._pasta / f"{self._inicio:%Y%m%dT%H%M%SZ}_{self.id}.json"
        conteudo = {**self._dados, "resposta": resposta, "duracao_ms": self._ms()}
        caminho.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return caminho
