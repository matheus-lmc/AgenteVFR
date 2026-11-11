"""Harness do TAF: janela VFR por hora, calculada em código (módulo 05).

Especificação: specs/05-janela-taf/requisitos.md e design.md.
Mesmas garantias do harness do METAR (REQ-J-08): só biblioteca padrão, sem rede, sem relógio, sem LLM.
A regra de mínimos e a leitura de visibilidade/nuvens são as do `harness.py` (uma regra só).
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

from app.harness import (
    MOTIVOS_RECUSA,
    PREFIXOS_BR,
    TOLERANCIA_FUTURO_MIN,
    _motivo,
    _resolver_horario,
    eh_vmc,
    ler_condicoes,
    teto_das_camadas,
)

MOTIVOS_TAF = {
    "formato_invalido": "TAF em formato não reconhecido.",
    "fora_do_escopo": MOTIVOS_RECUSA["fora_do_escopo"],
    "icao_divergente": "O TAF recebido é de outra estação ({icao}), não da solicitada ({solicitado}).",
    "horario_futuro": "Horário de emissão do TAF no futuro em relação ao relógio do sistema.",
    "sem_dado": "TAF NIL: estação sem previsão disponível.",
    "taf_cancelado": "TAF cancelado (CNL).",
    "taf_vencido": "TAF vencido: a validade terminou em {fim}.",
    "taf_incompleto": "TAF sem visibilidade ou nuvens legíveis na condição prevista.",
}
MOTIVO_VMC_PERIODO = "Dentro dos mínimos VFR em todas as horas (pior caso dos grupos do TAF)."

_RE_ICAO = re.compile(r"^[A-Z]{4}$")
_RE_EMISSAO = re.compile(r"^(\d{2})(\d{2})(\d{2})Z$")
_RE_PERIODO = re.compile(r"^(\d{2})(\d{2})/(\d{2})(\d{2})$")
_INICIO_GRUPO = {"BECMG", "TEMPO", "PROB30", "PROB40"}


@dataclass(frozen=True)
class ResumoJanela:
    """Resumo compacto da janela para o modelo (REQ-J-07). Os campos são as chaves."""

    icao: str | None
    emitido_utc: str | None
    validade_inicio: str | None
    validade_fim: str | None
    periodos: list[dict]
    melhor_janela: dict | None
    veredito: str                 # "JANELA" | "RECUSA"
    motivo: str
    taf_bruto: str

    def para_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ResultadoJanela:
    veredito: str                 # "JANELA" | "RECUSA"
    codigo_recusa: str | None
    resumo: ResumoJanela
    horas: list[dict]             # [{hora, veredito, motivo, grupo}] — traço e testes


@dataclass(frozen=True)
class _Cond:
    """Condição prevista. None = o grupo não informou (o elemento não muda) — DJ3."""

    vis: int | None
    camadas: list[str] | None     # [] = sem nuvens que formem teto (CAVOK/NSC)


@dataclass(frozen=True)
class _Grupo:
    rotulo: str                   # ex.: "BECMG 1108/1110"
    tipo: str                     # "BECMG" ou "TEMP" (TEMPO/PROB)
    inicio: datetime
    fim: datetime
    cond: _Cond


class _Recusa(Exception):
    def __init__(self, codigo: str, **fmt):
        super().__init__(codigo)
        self.codigo, self.fmt = codigo, fmt


# =========================================================================== avaliar_taf

def avaliar_taf(taf_bruto: str, icao_solicitado: str, agora: datetime) -> ResultadoJanela:
    if agora.tzinfo is None or agora.utcoffset() is None:
        raise ValueError("'agora' precisa ter fuso horário (UTC)")
    agora = agora.astimezone(timezone.utc)
    bruto = taf_bruto.strip()
    campos: dict = {}
    try:
        return _avaliar(bruto, icao_solicitado, agora, campos)
    except _Recusa as r:
        resumo = ResumoJanela(icao=campos.get("icao"), emitido_utc=campos.get("emitido_utc"),
                              validade_inicio=campos.get("validade_inicio"), validade_fim=campos.get("validade_fim"),
                              periodos=[], melhor_janela=None, veredito="RECUSA",
                              motivo=MOTIVOS_TAF[r.codigo].format(**r.fmt), taf_bruto=bruto)
        return ResultadoJanela("RECUSA", r.codigo, resumo, [])


def _avaliar(bruto: str, icao_solicitado: str, agora: datetime, campos: dict) -> ResultadoJanela:
    tokens = bruto.upper().rstrip("=").split()

    # Cabeçalho (design 2.1, passo 1) — mesma ordem do METAR
    i = 1 if tokens and tokens[0] == "TAF" else 0
    while i < len(tokens) and tokens[i] in ("AMD", "COR"):
        i += 1
    if i >= len(tokens) or not _RE_ICAO.match(tokens[i]):
        raise _Recusa("formato_invalido")
    icao = campos["icao"] = tokens[i]
    i += 1
    if not icao.startswith(PREFIXOS_BR):
        raise _Recusa("fora_do_escopo")
    solicitado = icao_solicitado.strip().upper()
    if icao != solicitado:
        raise _Recusa("icao_divergente", icao=icao, solicitado=solicitado)

    m = _RE_EMISSAO.match(tokens[i]) if i < len(tokens) else None
    emissao = _resolver_horario(*map(int, m.groups()), agora) if m else None
    if emissao is None:
        raise _Recusa("formato_invalido")
    if emissao - agora > timedelta(minutes=TOLERANCIA_FUTURO_MIN):
        raise _Recusa("horario_futuro")
    campos["emitido_utc"] = _iso(emissao)
    i += 1

    if i < len(tokens) and tokens[i] == "NIL":
        raise _Recusa("sem_dado")
    inicio, fim = _periodo(tokens[i] if i < len(tokens) else "", emissao)
    campos["validade_inicio"], campos["validade_fim"] = _iso(inicio), _iso(fim)
    i += 1
    if i < len(tokens) and tokens[i] == "CNL":
        raise _Recusa("taf_cancelado")
    if agora >= fim:
        raise _Recusa("taf_vencido", fim=_iso(fim))

    # Segmentos: base + grupos de mudança, até o RMK (passo 4)
    corpo = []
    for t in tokens[i:]:
        if t == "RMK":
            break
        corpo.append(t)
    base_tokens, grupos = _segmentos(corpo, emissao)
    base = _cond(base_tokens)
    if base.vis is None or base.camadas is None:
        raise _Recusa("taf_incompleto")

    # Hora a hora (passo 6) e períodos (passo 7)
    hora = max(agora.replace(minute=0, second=0, microsecond=0), inicio)
    horas = []
    while hora < fim:
        horas.append(_avaliar_hora(hora, base, grupos))
        hora += timedelta(hours=1)
    periodos = _periodos(horas)
    melhor = _melhor_janela(horas)
    motivo = (f"Melhor janela VMC: {_hz(melhor['inicio'])}–{_hz(melhor['fim'])} ({melhor['horas']} h)."
              if melhor else "Nenhuma hora VMC na validade do TAF.")
    resumo = ResumoJanela(icao=icao, emitido_utc=campos["emitido_utc"], validade_inicio=campos["validade_inicio"],
                          validade_fim=campos["validade_fim"], periodos=periodos, melhor_janela=melhor,
                          veredito="JANELA", motivo=motivo, taf_bruto=bruto)
    return ResultadoJanela("JANELA", None, resumo, horas)


def _periodo(token: str, referencia: datetime) -> tuple[datetime, datetime]:
    """DDHH/DDHH resolvido a partir da emissão (passo 2); HH=24 = 00 h do dia seguinte."""
    m = _RE_PERIODO.match(token)
    if not m:
        raise _Recusa("formato_invalido")
    d1, h1, d2, h2 = map(int, m.groups())
    inicio = _dia_hora(d1, h1, referencia)
    fim = _dia_hora(d2, h2, inicio or referencia)
    if inicio is None or fim is None or fim <= inicio:
        raise _Recusa("formato_invalido")
    return inicio, fim


def _dia_hora(dia: int, hora: int, referencia: datetime) -> datetime | None:
    if hora > 24:
        return None
    ano, mes = referencia.year, referencia.month
    for _ in range(2):  # mês da referência ou o seguinte
        try:
            momento = datetime(ano, mes, dia, tzinfo=timezone.utc) + timedelta(hours=hora)
        except ValueError:
            momento = None
        if momento is not None and momento >= referencia - timedelta(hours=1):
            return momento
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return None


def _segmentos(corpo: list[str], emissao: datetime) -> tuple[list[str], list[_Grupo]]:
    i = 0
    while i < len(corpo) and corpo[i] not in _INICIO_GRUPO:
        i += 1
    base, grupos = corpo[:i], []
    while i < len(corpo):
        tipo = corpo[i]
        rotulo = tipo
        if tipo.startswith("PROB") and i + 1 < len(corpo) and corpo[i + 1] == "TEMPO":
            rotulo, i = f"{tipo} TEMPO", i + 1
        periodo = corpo[i + 1] if i + 1 < len(corpo) else ""
        inicio, fim = _periodo(periodo, emissao)
        j = i + 2
        while j < len(corpo) and corpo[j] not in _INICIO_GRUPO:
            j += 1
        grupos.append(_Grupo(f"{rotulo} {periodo}", "BECMG" if tipo == "BECMG" else "TEMP", inicio, fim,
                             _cond(corpo[i + 2:j])))
        i = j
    return base, grupos


def _cond(tokens: list[str]) -> _Cond:
    c = ler_condicoes(tokens)
    if c.cavok or c.sem_nuvem:
        camadas: list[str] | None = []
    else:
        camadas = c.camadas or None
    if camadas and teto_das_camadas(camadas)[1]:
        raise _Recusa("taf_incompleto")  # camada com altura ou cobertura ///
    return _Cond(c.vis_m, camadas)


def _aplicar(vigente: _Cond, mudanca: _Cond) -> _Cond:
    """Só os elementos informados mudam (REQ-J-04)."""
    return _Cond(mudanca.vis if mudanca.vis is not None else vigente.vis,
                 mudanca.camadas if mudanca.camadas is not None else vigente.camadas)


def _avaliar_hora(hora: datetime, base: _Cond, grupos: list[_Grupo]) -> dict:
    vigente, grupo_vigente = base, "base"
    for g in grupos:
        if g.tipo == "BECMG" and g.fim <= hora:
            vigente = _aplicar(vigente, g.cond)
            if g.cond.vis is not None or g.cond.camadas is not None:  # BECMG só de vento não é "responsável"
                grupo_vigente = g.rotulo
    candidatos = [(vigente, grupo_vigente)]
    for g in grupos:
        if g.inicio <= hora < g.fim:  # transição de BECMG ou TEMPO/PROB ativo: pior caso (D1)
            candidatos.append((_aplicar(vigente, g.cond), g.rotulo))
    escolhido = None
    for cond, grupo in candidatos:
        teto, _ = teto_das_camadas(cond.camadas or [])
        vmc = eh_vmc(teto, cond.vis)
        if escolhido is None or (not vmc and escolhido[0]):
            escolhido = (vmc, teto, cond.vis, grupo)
        if not vmc:
            break
    vmc, teto, vis, grupo = escolhido
    return {"hora": _iso(hora), "veredito": "VMC" if vmc else "IMC", "motivo": _motivo(vmc, teto, vis),
            "grupo": grupo}


def _periodos(horas: list[dict]) -> list[dict]:
    """IMC agrupado por veredito + grupo; VMC só pelo veredito (DJ4)."""
    periodos: list[dict] = []
    for h in horas:
        chave = (h["veredito"], h["grupo"] if h["veredito"] == "IMC" else None)
        fim = _iso(_dt(h["hora"]) + timedelta(hours=1))
        if periodos and (periodos[-1]["veredito"], periodos[-1]["grupo"]) == chave:
            periodos[-1]["fim"] = fim
        else:
            periodos.append({"inicio": h["hora"], "fim": fim, "veredito": h["veredito"],
                             "motivo": h["motivo"] if h["veredito"] == "IMC" else MOTIVO_VMC_PERIODO,
                             "grupo": chave[1]})
    return periodos


def _melhor_janela(horas: list[dict]) -> dict | None:
    """VMC contínuo mais longo; empate → o mais cedo (D3)."""
    melhor = None
    inicio = n = 0
    for k, h in enumerate(horas + [{"veredito": "FIM"}]):
        if h["veredito"] == "VMC":
            if n == 0:
                inicio = k
            n += 1
            continue
        if n and (melhor is None or n > melhor[1]):
            melhor = (inicio, n)
        n = 0
    if melhor is None:
        return None
    k, n = melhor
    return {"inicio": horas[k]["hora"], "fim": _iso(_dt(horas[k]["hora"]) + timedelta(hours=n)), "horas": n}


# =========================================================================== auxiliares do agente

def veredito_na_hora(resumo: ResumoJanela, momento: datetime) -> str | None:
    """Veredito previsto para o momento, ou None se fora dos períodos calculados."""
    for p in resumo.periodos:
        if _dt(p["inicio"]) <= momento < _dt(p["fim"]):
            return p["veredito"]
    return None


def texto_modelo_janela(resumo: ResumoJanela) -> str:
    if resumo.veredito != "JANELA":
        return f"Sem janela para {resumo.icao or 'o aeródromo'}: {resumo.motivo}"
    partes = []
    for p in resumo.periodos:
        trecho = f"{_hz(p['inicio'])}–{_hz(p['fim'])} {p['veredito']}"
        if p["veredito"] == "IMC":
            trecho += f" ({p['motivo'].rstrip('.')}; {p['grupo']})"
        partes.append(trecho)
    m = resumo.melhor_janela
    melhor = (f"Melhor janela VMC: {_hz(m['inicio'])}–{_hz(m['fim'])} ({m['horas']} h)." if m
              else "Melhor janela VMC: nenhuma.")
    fim = _dt(resumo.validade_fim)
    return (f"Previsão (TAF) para {resumo.icao}, válida até {fim:%d/%m} {fim:%H}Z: " + "; ".join(partes) + ". "
            + melhor + " É previsão, não observação.")


def _iso(momento: datetime) -> str:
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _hz(iso: str) -> str:
    return iso[11:13] + "Z"
