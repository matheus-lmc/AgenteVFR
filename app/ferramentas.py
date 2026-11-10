"""Ferramentas do AgenteVFR: busca de METAR e TAF na API aviationweather.gov.

Especificação: specs/02-ferramentas/requisitos.md e specs/02-ferramentas/design.md.
Não decide nada sobre o tempo: devolve o texto bruto para o harness e o JSON da API para o traço.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from typing import Callable

import httpx

from app.harness import PREFIXOS_BR  # REQ-F-02: um só lugar para o escopo

BASE_URL_PADRAO = "https://aviationweather.gov/api/data"
TIMEOUT_PADRAO_S = 10.0
USER_AGENT = "AgenteVFR/0.1 (projeto academico TE251)"
CACHE_TTL_S = 300               # 5 min (REQ-F-07)
CACHE_IDADE_MAX_METAR_MIN = 55  # decisão D3
MAX_TENTATIVAS = 2              # decisão D5
STATUS = {"ok", "sem_dado", "icao_invalido", "fora_do_escopo", "erro_api", "limite_api"}

_RE_ICAO = re.compile(r"^[A-Z]{4}$")
_CAMPO_TEXTO = {"metar": "rawOb", "taf": "rawTAF"}


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class ResultadoBusca:
    """Resultado de uma busca (REQ-F-08). Os campos são as chaves do traço."""

    icao: str
    tipo: str
    status: str
    texto_bruto: str | None          # vai para o harness
    resposta_api: list | dict | None  # vai só para o traço
    url: str | None
    http_status: int | None
    de_cache: bool
    tentativas: int
    buscado_em: str
    duracao_ms: int
    erro: str | None

    def para_dict(self) -> dict:
        return asdict(self)


class ClienteAWC:
    def __init__(self, *, base_url: str | None = None, timeout_s: float | None = None,
                 http: httpx.Client | None = None,
                 relogio: Callable[[], datetime] = agora_utc):
        self._base_url = (base_url or os.environ.get("AWC_BASE_URL") or BASE_URL_PADRAO).rstrip("/")
        if timeout_s is None:
            timeout_s = float(os.environ.get("AWC_TIMEOUT_S", TIMEOUT_PADRAO_S))
        self._timeout_s = float(timeout_s)
        self._http = http or httpx.Client()
        self._relogio = relogio
        self._cache: dict[tuple[str, str], tuple[ResultadoBusca, datetime]] = {}
        self._trava = threading.Lock()

    def buscar_metar(self, icao: str) -> ResultadoBusca:
        return self._buscar("metar", icao)

    def buscar_taf(self, icao: str) -> ResultadoBusca:
        return self._buscar("taf", icao)

    def limpar_cache(self) -> None:
        with self._trava:
            self._cache.clear()

    # ------------------------------------------------------------------ fluxo (design, seção 4)

    def _buscar(self, tipo: str, icao: str) -> ResultadoBusca:
        campo = _CAMPO_TEXTO[tipo]
        inicio = time.perf_counter()
        agora = self._relogio()
        icao_norm = icao.strip().upper() if isinstance(icao, str) else str(icao)

        def resultado(status: str, **campos) -> ResultadoBusca:
            base = dict(texto_bruto=None, resposta_api=None, url=None, http_status=None,
                        de_cache=False, tentativas=0, erro=None)
            base.update(campos)
            return ResultadoBusca(icao=icao_norm, tipo=tipo, status=status, buscado_em=_iso(agora),
                                  duracao_ms=_ms_desde(inicio), **base)

        # Validações sem rede (REQ-F-01, REQ-F-02)
        if not _RE_ICAO.match(icao_norm):
            return resultado("icao_invalido", erro="ICAO deve ter 4 letras")
        if not icao_norm.startswith(PREFIXOS_BR):
            return resultado("fora_do_escopo", erro="ICAO fora dos prefixos brasileiros")

        # Cache (REQ-F-07)
        chave = (tipo, icao_norm)
        with self._trava:
            entrada = self._cache.get(chave)
        if entrada and self._cache_valido(tipo, *entrada, agora):
            return replace(entrada[0], de_cache=True, tentativas=0, buscado_em=_iso(agora),
                           duracao_ms=_ms_desde(inicio))

        # Requisição com uma nova tentativa (REQ-F-03, REQ-F-06)
        url = f"{self._base_url}/{tipo}"
        params = {"ids": icao_norm, "format": "json"}
        url_completa = str(httpx.URL(url, params=params))
        resposta: httpx.Response | None = None
        erro: str | None = None
        for tentativa in range(1, MAX_TENTATIVAS + 1):
            try:
                resposta = self._http.get(url, params=params, headers={"User-Agent": USER_AGENT},
                                          timeout=self._timeout_s)
            except httpx.TransportError as e:
                resposta, erro = None, f"{type(e).__name__}: {e}"
                continue
            if resposta.status_code >= 500:
                erro = f"HTTP {resposta.status_code}"
                continue
            break

        comum = dict(url=url_completa, tentativas=tentativa,
                     http_status=resposta.status_code if resposta is not None else None)
        if resposta is None or resposta.status_code >= 500:
            return resultado("erro_api", erro=erro, **comum)
        if resposta.status_code == 429:
            return resultado("limite_api", erro="HTTP 429", **comum)
        if resposta.status_code == 204:
            return resultado("sem_dado", **comum)

        try:
            dados, json_valido = resposta.json(), True
        except ValueError:
            dados, json_valido = None, False

        if resposta.status_code != 200:
            mensagem = dados.get("error") if isinstance(dados, dict) else None
            erro = f"HTTP {resposta.status_code}" + (f": {mensagem}" if mensagem else "")
            return resultado("erro_api", erro=erro, resposta_api=dados, **comum)
        if not json_valido or not isinstance(dados, list):
            return resultado("erro_api", erro="resposta da API não é uma lista JSON", resposta_api=dados, **comum)
        if not dados:
            return resultado("sem_dado", resposta_api=dados, **comum)

        texto = dados[0].get(campo) if isinstance(dados[0], dict) else None
        if not isinstance(texto, str) or not texto.strip():
            return resultado("erro_api", erro=f"campo {campo} ausente ou vazio", resposta_api=dados, **comum)

        r = resultado("ok", texto_bruto=texto, resposta_api=dados, **comum)
        with self._trava:
            self._cache[chave] = (r, agora)  # só "ok" vai para o cache (decisão D2)
        return r

    @staticmethod
    def _cache_valido(tipo: str, guardado: ResultadoBusca, guardado_em: datetime, agora: datetime) -> bool:
        if (agora - guardado_em).total_seconds() >= CACHE_TTL_S:
            return False
        if tipo != "metar":
            return True
        try:  # obsTime só decide o cache; o veredito sai do texto bruto (REQ-H-11)
            obs = datetime.fromtimestamp(guardado.resposta_api[0]["obsTime"], timezone.utc)
        except (KeyError, IndexError, TypeError, ValueError, OverflowError, OSError):
            return False
        return (agora - obs).total_seconds() <= CACHE_IDADE_MAX_METAR_MIN * 60


def _iso(momento: datetime) -> str:
    return momento.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ms_desde(inicio: float) -> int:
    return int((time.perf_counter() - inicio) * 1000)


# ---------------------------------------------------------------------- atalhos para o agente (REQ-F-09)

_cliente_padrao: ClienteAWC | None = None  # criado na primeira chamada dos atalhos


def _padrao() -> ClienteAWC:
    global _cliente_padrao
    if _cliente_padrao is None:
        _cliente_padrao = ClienteAWC()
    return _cliente_padrao


def buscar_metar(icao: str) -> ResultadoBusca:
    return _padrao().buscar_metar(icao)


def buscar_taf(icao: str) -> ResultadoBusca:
    return _padrao().buscar_taf(icao)
