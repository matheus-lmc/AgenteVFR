"""Loop do agente com tool calling do Ollama.

Especificação: specs/03-agente/requisitos.md e specs/03-agente/design.md.
O modelo escolhe aeródromos, ferramentas e texto; veredito, recusas, bloqueios e limites saem de código.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import httpx

from app import ferramentas
from app.ferramentas import agora_utc

MAX_CHAMADAS_FERRAMENTA = 5
MAX_CARACTERES_PERGUNTA = 500


class ErroModelo(Exception):
    """Falha ao falar com o Ollama (rede, HTTP, formato)."""


class ClienteOllama:
    def __init__(self, *, url: str | None = None, modelo: str | None = None,
                 temperatura: float | None = None, timeout_s: float | None = None,
                 http: httpx.Client | None = None):
        raise NotImplementedError

    def conversar(self, mensagens: list[dict], ferramentas: list[dict]) -> dict:
        raise NotImplementedError


@dataclass(frozen=True)
class RespostaAgente:
    id_traco: str
    veredito: str
    motivo: str
    avaliacoes: list[dict]
    explicacao: str
    origem_explicacao: str
    bloqueio: dict | None
    aviso: str
    duracao_ms: int

    def para_dict(self) -> dict:
        raise NotImplementedError


class Agente:
    def __init__(self, *, ollama: ClienteOllama | None = None,
                 buscar_metar=ferramentas.buscar_metar, buscar_taf=ferramentas.buscar_taf,
                 relogio=agora_utc, pasta_traces: Path | None = None):
        raise NotImplementedError

    def perguntar(self, pergunta: str) -> RespostaAgente:
        raise NotImplementedError
