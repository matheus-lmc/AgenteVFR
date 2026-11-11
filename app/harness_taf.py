"""Harness do TAF: janela VFR por hora, calculada em código (módulo 05).

Especificação: specs/05-janela-taf/requisitos.md e design.md.
Mesmas garantias do harness do METAR (REQ-J-08): só biblioteca padrão, sem rede, sem relógio, sem LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ResumoJanela:
    """Resumo compacto da janela para o modelo (REQ-J-07). Os campos são as chaves."""

    icao: str | None
    emitido_utc: str | None
    validade_inicio: str | None
    validade_fim: str | None
    periodos: list[dict]
    melhor_janela: dict | None
    veredito: str
    motivo: str
    taf_bruto: str

    def para_dict(self) -> dict:
        raise NotImplementedError


@dataclass(frozen=True)
class ResultadoJanela:
    veredito: str
    codigo_recusa: str | None
    resumo: ResumoJanela
    horas: list[dict]


def avaliar_taf(taf_bruto: str, icao_solicitado: str, agora: datetime) -> ResultadoJanela:
    raise NotImplementedError


def veredito_na_hora(resumo: ResumoJanela, momento: datetime) -> str | None:
    raise NotImplementedError


def texto_modelo_janela(resumo: ResumoJanela) -> str:
    raise NotImplementedError
