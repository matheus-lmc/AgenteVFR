"""Ferramentas do AgenteVFR: busca de METAR e TAF na API aviationweather.gov.

Especificação: specs/02-ferramentas/requisitos.md e specs/02-ferramentas/design.md.
Não decide nada sobre o tempo: devolve o texto bruto para o harness e o JSON da API para o traço.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import httpx

BASE_URL_PADRAO = "https://aviationweather.gov/api/data"
TIMEOUT_PADRAO_S = 10.0
USER_AGENT = "AgenteVFR/0.1 (projeto academico TE251)"
CACHE_TTL_S = 300
CACHE_IDADE_MAX_METAR_MIN = 55
MAX_TENTATIVAS = 2
STATUS = {"ok", "sem_dado", "icao_invalido", "fora_do_escopo", "erro_api", "limite_api"}


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ResultadoBusca:
    icao: str
    tipo: str
    status: str
    texto_bruto: str | None
    resposta_api: list | dict | None
    url: str | None
    http_status: int | None
    de_cache: bool
    tentativas: int
    buscado_em: str
    duracao_ms: int
    erro: str | None

    def para_dict(self) -> dict:
        raise NotImplementedError


class ClienteAWC:
    def __init__(self, *, base_url: str | None = None, timeout_s: float | None = None,
                 http: httpx.Client | None = None,
                 relogio: Callable[[], datetime] = agora_utc):
        raise NotImplementedError

    def buscar_metar(self, icao: str) -> ResultadoBusca:
        raise NotImplementedError

    def buscar_taf(self, icao: str) -> ResultadoBusca:
        raise NotImplementedError

    def limpar_cache(self) -> None:
        raise NotImplementedError


_cliente_padrao: ClienteAWC | None = None  # criado na primeira chamada dos atalhos


def buscar_metar(icao: str) -> ResultadoBusca:
    raise NotImplementedError


def buscar_taf(icao: str) -> ResultadoBusca:
    raise NotImplementedError
