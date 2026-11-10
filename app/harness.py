"""Harness do AgenteVFR: a parte do sistema que o modelo não consegue alterar.

Especificação: specs/01-harness/requisitos.md e specs/01-harness/design.md.
Só biblioteca padrão (REQ-H-11): este módulo não acessa rede, relógio nem LLM.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
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
        return asdict(self)


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


# =========================================================================== avaliar_metar

MOTIVOS_RECUSA = {
    "formato_invalido": "Boletim em formato não reconhecido.",
    "fora_do_escopo": "Aeródromo fora do Brasil (prefixo ICAO não brasileiro). "
                      "O sistema só atende aeródromos brasileiros.",
    "icao_divergente": "O boletim recebido é de outra estação ({icao}), não da solicitada ({solicitado}).",
    "sem_dado": "Boletim NIL: estação sem observação disponível.",
    "horario_futuro": "Horário do boletim no futuro em relação ao relógio do sistema.",
    "dado_desatualizado": "Boletim com {idade} min (máximo {maximo} min).",
    "visibilidade_indisponivel": "Visibilidade não informada no boletim.",
    "teto_indisponivel": "Altura ou cobertura de nuvens não informada (///).",
    "nuvens_indisponiveis": "Boletim sem informação de nuvens.",
}

_FIM_DA_OBSERVACAO = {"RMK", "BECMG", "TEMPO", "NOSIG"}  # REQ-H-07
_SEM_NUVEM = {"NSC", "NCD", "SKC", "CLR"}
_COBERTURAS_TETO = {"BKN", "OVC", "VV"}

_RE_ICAO = re.compile(r"^[A-Z]{4}$")
_RE_HORARIO = re.compile(r"^(\d{2})(\d{2})(\d{2})Z$")
_RE_VIS = re.compile(r"^(\d{4})(NDV)?$")
_RE_VIS_MINIMA = re.compile(r"^\d{4}(N|NE|E|SE|S|SW|W|NW)$")
_RE_NUVEM = re.compile(r"^(FEW|SCT|BKN|OVC|///)(\d{3}|///)(CB|TCU|///)?$")
_RE_VV = re.compile(r"^(VV)(\d{3}|///)$")


def avaliar_metar(metar_bruto: str, icao_solicitado: str, agora: datetime) -> Resultado:
    if agora.tzinfo is None or agora.utcoffset() is None:
        raise ValueError("'agora' precisa ter fuso horário (UTC)")
    agora = agora.astimezone(timezone.utc)

    bruto = metar_bruto.strip()
    tokens = bruto.upper().rstrip("=").split()
    campos: dict = {}

    def recusa(codigo: str, **fmt) -> Resultado:
        return _recusa(codigo, campos, bruto, **fmt)

    # Cabeçalho (design 4.2) — a ordem das checagens é a do REQ-H-02
    i = 0
    campos["tipo"] = "METAR"
    if tokens and tokens[0] in ("METAR", "SPECI"):
        campos["tipo"] = tokens[0]
        i = 1
    if i < len(tokens) and tokens[i] == "COR":
        i += 1

    if i >= len(tokens) or not _RE_ICAO.match(tokens[i]):
        return recusa("formato_invalido")
    icao = campos["icao"] = tokens[i]
    i += 1

    if not icao.startswith(PREFIXOS_BR):
        return recusa("fora_do_escopo")

    solicitado = icao_solicitado.strip().upper()
    if icao != solicitado:
        return recusa("icao_divergente", icao=icao, solicitado=solicitado)

    m = _RE_HORARIO.match(tokens[i]) if i < len(tokens) else None
    obs = _resolver_horario(*map(int, m.groups()), agora) if m else None
    if obs is None:
        return recusa("formato_invalido")
    campos["horario_utc"] = obs.strftime("%Y-%m-%dT%H:%M:%SZ")
    i += 1

    if i < len(tokens) and tokens[i] == "NIL":
        return recusa("sem_dado")

    idade = agora - obs
    if -idade > timedelta(minutes=TOLERANCIA_FUTURO_MIN):
        return recusa("horario_futuro")
    idade_min = campos["idade_min"] = max(0, int(idade.total_seconds() // 60))
    if idade > timedelta(minutes=IDADE_MAX_MIN):
        return recusa("dado_desatualizado", idade=idade_min, maximo=IDADE_MAX_MIN)

    if i < len(tokens) and tokens[i] == "AUTO":
        i += 1

    # Corpo (design 4.3)
    cavok = sem_nuvem = False
    vis: int | None = None
    vis_lida = False
    camadas: list[str] = []
    for t in tokens[i:]:
        if t in _FIM_DA_OBSERVACAO:
            break
        if t == "CAVOK":
            cavok = True
        elif not vis_lida and (mv := _RE_VIS.match(t)):
            vis, vis_lida = int(mv.group(1)), True
            if vis == 9999:
                vis = 10000
        elif not vis_lida and t == "////":
            vis_lida = True  # visibilidade indisponível
        elif _RE_VIS_MINIMA.match(t):
            pass  # visibilidade mínima direcional: ignorada (decisão D1)
        elif _RE_NUVEM.match(t) or _RE_VV.match(t):
            camadas.append(t)
        elif t in _SEM_NUVEM:
            sem_nuvem = True

    if cavok:
        vis = 10000
    campos["vis_m"] = vis
    campos["camadas"] = camadas

    if vis is None:
        return recusa("visibilidade_indisponivel")

    partes = [_partes_camada(c) for c in camadas]
    for cobertura, altura in partes:
        if cobertura == "///" or (cobertura in _COBERTURAS_TETO and altura is None):
            return recusa("teto_indisponivel")  # decisão D2
    if not camadas and not cavok and not sem_nuvem:
        return recusa("nuvens_indisponiveis")  # decisão D3

    teto = min((altura * 100 for cobertura, altura in partes
                if cobertura in _COBERTURAS_TETO), default=None)
    campos["teto_ft"] = teto

    # Regra (REQ-H-10)
    vmc = (teto is None or teto >= TETO_MIN_FT) and vis >= VIS_MIN_M
    veredito = Veredito.VMC if vmc else Veredito.IMC
    resumo = Resumo(
        icao=icao, tipo=campos["tipo"], horario_utc=campos["horario_utc"], idade_min=idade_min,
        vis_m=vis, teto_ft=teto, camadas=camadas, veredito=veredito.value,
        motivo=_motivo(vmc, teto, vis), metar_bruto=bruto,
    )
    return Resultado(veredito, None, resumo)


def _resolver_horario(dia: int, hora: int, minuto: int, agora: datetime) -> datetime | None:
    """DDHHMMZ → datetime UTC. Dia maior que o de 'agora' = mês anterior (REQ-H-06)."""
    if hora > 23 or minuto > 59:
        return None
    ano, mes = agora.year, agora.month
    if dia > agora.day:
        mes -= 1
        if mes == 0:
            ano, mes = ano - 1, 12
    try:
        return datetime(ano, mes, dia, hora, minuto, tzinfo=timezone.utc)
    except ValueError:
        return None


def _partes_camada(grupo: str) -> tuple[str, int | None]:
    m = _RE_NUVEM.match(grupo) or _RE_VV.match(grupo)
    cobertura, altura = m.group(1), m.group(2)
    return cobertura, (None if altura == "///" else int(altura))


def _motivo(vmc: bool, teto: int | None, vis: int) -> str:
    if vmc:
        teto_txt = "Sem teto" if teto is None else f"Teto {teto} ft (mínimo {TETO_MIN_FT} ft)"
        return f"{teto_txt} e visibilidade {vis} m (mínimo {VIS_MIN_M} m): dentro dos mínimos VFR."
    falhas = []
    if teto is not None and teto < TETO_MIN_FT:
        falhas.append(f"teto {teto} ft abaixo do mínimo de {TETO_MIN_FT} ft")
    if vis < VIS_MIN_M:
        falhas.append(f"visibilidade {vis} m abaixo do mínimo de {VIS_MIN_M} m")
    texto = "; ".join(falhas)
    return texto[0].upper() + texto[1:] + "."


def _recusa(codigo: str, campos: dict, bruto: str, **fmt) -> Resultado:
    resumo = Resumo(
        icao=campos.get("icao"), tipo=campos.get("tipo"), horario_utc=campos.get("horario_utc"),
        idade_min=campos.get("idade_min"), vis_m=campos.get("vis_m"), teto_ft=campos.get("teto_ft"),
        camadas=campos.get("camadas", []), veredito=Veredito.RECUSA.value,
        motivo=MOTIVOS_RECUSA[codigo].format(**fmt), metar_bruto=bruto,
    )
    return Resultado(Veredito.RECUSA, codigo, resumo)


# =========================================================================== pré-filtro (REQ-H-13)

# Lista única de termos fora de escopo (vai para slide e artigo). Avaliada nesta ordem;
# texto já normalizado: minúsculas e sem acentos.
TERMOS_FORA_DE_ESCOPO: dict[str, list[str]] = {
    "manipulacao_regra": [
        r"\bignor(e|a|ar|ando)\b", r"\bdesconsider\w*", r"\besquec\w* (a|as) regras?\b",
        r"\bfinj\w*", r"\bsem o harness\b",
    ],
    "pressao_operacional": [
        r"\bmesmo assim\b", r"\bassim mesmo\b", r"\bmesmo com\b", r"\bda um jeito\b",
    ],
    "pedido_ifr": [
        r"\bifr\b", r"\binstrumentos?\b",
    ],
    "previsao_alem_taf": [
        r"\bsemana que vem\b", r"\bproxima semana\b", r"\bdepois de amanha\b",
        r"\bdaqui a (\d+|dois|tres|quatro|cinco) dias\b",
        r"\bproxim[oa]s (\d+|dois|tres|quatro|cinco|seis|sete) dias\b", r"\bmes que vem\b",
    ],
}

MOTIVOS_PERGUNTA = {
    "manipulacao_regra": "A regra de mínimos é aplicada em código e não pode ser ignorada ou alterada por pedido.",
    "pressao_operacional": "O sistema não autoriza operação contra o veredito; a decisão é do piloto em comando, "
                           "com o briefing oficial.",
    "pedido_ifr": "Planejamento IFR está fora do escopo: o sistema só avalia condições VFR de aeródromo.",
    "previsao_alem_taf": "Previsão além da validade do TAF (24–30 h) está fora do escopo.",
}

_PADROES_PERGUNTA = {
    categoria: [re.compile(p) for p in padroes] for categoria, padroes in TERMOS_FORA_DE_ESCOPO.items()
}


def _normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, preservando o comprimento (posições valem no texto original)."""
    saida = []
    for ch in texto:
        base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        saida.append((base[:1] or " ").lower()[:1])
    return "".join(saida)


def prefiltrar_pergunta(pergunta: str) -> RecusaPergunta | None:
    normalizada = _normalizar(pergunta)
    for categoria, padroes in _PADROES_PERGUNTA.items():
        for padrao in padroes:
            if m := padrao.search(normalizada):
                termo = pergunta[m.start():m.end()]
                return RecusaPergunta(categoria, termo, MOTIVOS_PERGUNTA[categoria])
    return None


# =========================================================================== verificador (REQ-H-14/15)

_FAVORAVEL = [
    r"da (para|pra) voar (visual|vfr)", r"condic(ao|oes) vmc", r"(em|esta|estao|e|sao) vmc",
    r"vfr liberado", r"pode voar (vfr|visual)", r"e possivel voar (vfr|visual)",
    r"favorave(l|is) (ao|para o) voo visual",
]
_DESFAVORAVEL = [
    r"condic(ao|oes) imc", r"(em|esta|estao|e|sao) imc", r"abaixo dos minimos",
    r"voo visual nao (e )?recomendado",
]
_NEGACOES = {"nao", "nem", "nunca", "jamais"}
_JANELA_NEGACAO = 3  # palavras antes da expressão (decisão D6)

_EXPRESSOES = (
    [(re.compile(rf"\b(?:{p})\b"), +1) for p in _FAVORAVEL]
    + [(re.compile(rf"\b(?:{p})\b"), -1) for p in _DESFAVORAVEL]
)


def verificar_explicacao(explicacao: str, resumo: Resumo) -> Verificacao:
    if resumo.veredito == Veredito.RECUSA.value:
        return Verificacao(texto_modelo(resumo), "texto_modelo", False, None, None)
    if not explicacao.strip():
        return Verificacao(texto_modelo(resumo), "texto_modelo", True, "explicacao_vazia", None)

    normalizada = _normalizar(explicacao)
    ocorrencias = []
    for padrao, sinal in _EXPRESSOES:
        for m in padrao.finditer(normalizada):
            anteriores = re.findall(r"\w+", normalizada[:m.start()])[-_JANELA_NEGACAO:]
            if _NEGACOES & set(anteriores):
                sinal_efetivo = -sinal
            else:
                sinal_efetivo = sinal
            ocorrencias.append((m.start(), m.end(), sinal_efetivo))

    contraditorio = +1 if resumo.veredito == Veredito.IMC.value else -1
    regra = "imc_com_afirmacao_favoravel" if contraditorio > 0 else "vmc_com_afirmacao_desfavoravel"
    for inicio, fim, sinal in sorted(ocorrencias):
        if sinal == contraditorio:
            return Verificacao(texto_modelo(resumo), "texto_modelo", True, regra, explicacao[inicio:fim])
    return Verificacao(explicacao, "modelo", False, None, None)


def texto_modelo(resumo: Resumo) -> str:
    if resumo.veredito == Veredito.RECUSA.value:
        alvo = resumo.icao or "o aeródromo"
        return f"Sem veredito para {alvo}: {resumo.motivo} Consulte o briefing oficial (REDEMET/AIS)."
    hora = resumo.horario_utc[11:16] if resumo.horario_utc else "--:--"
    return (f"{resumo.veredito} em {resumo.icao} — {resumo.motivo} "
            f"Observação das {hora}Z ({resumo.idade_min} min). METAR: {resumo.metar_bruto}")
