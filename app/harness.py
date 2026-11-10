"""Harness do AgenteVFR: a parte do sistema que o modelo não consegue alterar.

Especificação: specs/01-harness/requisitos.md e specs/01-harness/design.md.
Só biblioteca padrão (REQ-H-11): este módulo não acessa rede, relógio nem LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# Mínimos VFR de aeródromo — ICA 100-1, item 3.1.1 [pendência: conferir texto vigente] (REQ-H-10)
TETO_MIN_FT = 1500
VIS_MIN_M = 5000
IDADE_MAX_MIN = 60
TOLERANCIA_FUTURO_MIN = 5
PREFIXOS_BR = ("SB", "SD", "SI", "SJ", "SN", "SS", "SW")


class Veredito(str, Enum):
    VMC = "VMC"
    IMC = "IMC"
    RECUSA = "RECUSA"


@dataclass(frozen=True)
class Resumo:
    """Resumo compacto que entra na janela do modelo (REQ-H-12). Os campos são as chaves."""

    icao: str | None
    tipo: str | None
    horario_utc: str | None
    idade_min: int | None
    vis_m: int | None
    teto_ft: int | None
    camadas: list[str]
    veredito: str
    motivo: str
    metar_bruto: str

    def para_dict(self) -> dict:
        raise NotImplementedError


@dataclass(frozen=True)
class Resultado:
    veredito: Veredito
    codigo_recusa: str | None
    resumo: Resumo


@dataclass(frozen=True)
class RecusaPergunta:
    categoria: str
    termo: str
    motivo: str


@dataclass(frozen=True)
class Verificacao:
    texto_final: str
    origem: str  # "modelo" | "texto_modelo"
    bloqueada: bool
    regra: str | None
    trecho: str | None


def avaliar_metar(metar_bruto: str, icao_solicitado: str, agora: datetime) -> Resultado:
    raise NotImplementedError


def prefiltrar_pergunta(pergunta: str) -> RecusaPergunta | None:
    raise NotImplementedError


def verificar_explicacao(explicacao: str, resumo: Resumo) -> Verificacao:
    raise NotImplementedError


def texto_modelo(resumo: Resumo) -> str:
    raise NotImplementedError
