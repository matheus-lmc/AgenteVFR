"""Testes do harness do TAF (janela VFR), derivados de specs/05-janela-taf/requisitos.md.

Usa os 14 TAFs reais gravados em 10/11/2026 e TAFs sintéticos para cada regra. "Agora" sempre fixo.
"""

from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app import harness_taf
from app.harness_taf import avaliar_taf, texto_modelo_janela, veredito_na_hora

UTC = timezone.utc
REAIS = {d["icaoId"]: d["rawTAF"] for d in json.loads(
    (Path(__file__).parent / "fixtures" / "awc" / "taf_14_aerodromos_20261110.json").read_text(encoding="utf-8"))}
AGORA = datetime(2026, 11, 11, 0, 30, tzinfo=UTC)
CHAVES = {"icao", "emitido_utc", "validade_inicio", "validade_fim", "periodos", "melhor_janela", "veredito",
          "motivo", "taf_bruto"}


def taf(corpo: str, validade: str = "1100/1112", emissao: str = "102222Z", icao: str = "SBGR") -> str:
    return f"TAF {icao} {emissao} {validade} {corpo}"


def avaliar(texto: str, agora: datetime = AGORA, icao: str = "SBGR"):
    return avaliar_taf(texto, icao, agora)


def mapa(resultado) -> dict[str, str]:
    """{'00Z': 'IMC', ...} das horas avaliadas (só a hora, dia implícito)."""
    return {h["hora"][11:13] + "Z": h["veredito"] for h in resultado.horas}


def periodos(resultado) -> list[tuple[str, str, str]]:
    return [(p["inicio"][8:13], p["fim"][8:13], p["veredito"]) for p in resultado.resumo.periodos]


def assert_recusa(resultado, codigo):
    assert resultado.veredito == "RECUSA"
    assert resultado.codigo_recusa == codigo
    assert resultado.resumo.veredito == "RECUSA"


# --------------------------------------------------------------------------- TAFs reais

@pytest.mark.parametrize("icao", sorted(REAIS))
def test_reais_os_14_tafs_decodificam(icao):
    r = avaliar(REAIS[icao], icao=icao)
    assert r.veredito == "JANELA", (icao, r.codigo_recusa)
    assert r.horas and r.resumo.periodos


def test_reais_sbgr_periodos_e_melhor_janela():
    r = avaliar(REAIS["SBGR"])
    assert periodos(r) == [("11T00", "11T05", "IMC"), ("11T05", "11T08", "VMC"), ("11T08", "11T14", "IMC"),
                           ("11T14", "12T06", "VMC")]
    assert [p["grupo"] for p in r.resumo.periodos if p["veredito"] == "IMC"] == ["base", "BECMG 1108/1110"]
    assert r.resumo.melhor_janela == {"inicio": "2026-11-11T14:00:00Z", "fim": "2026-11-12T06:00:00Z", "horas": 16}


def test_reais_sbct_imc_ate_14z():
    r = avaliar(REAIS["SBCT"], icao="SBCT")
    assert periodos(r) == [("11T00", "11T14", "IMC"), ("11T14", "12T00", "VMC")]
    assert r.resumo.validade_fim == "2026-11-12T00:00:00Z"  # 1100/1124 → 24 h = 00 h do dia seguinte


# --------------------------------------------------------------------------- REQ-J-01 formato

def test_req_j01_cabecalho_e_datas():
    r = avaliar(REAIS["SBGR"])
    assert r.resumo.icao == "SBGR"
    assert r.resumo.emitido_utc == "2026-11-10T22:22:00Z"
    assert r.resumo.validade_inicio == "2026-11-11T00:00:00Z"
    assert r.resumo.validade_fim == "2026-11-12T06:00:00Z"
    assert r.resumo.taf_bruto == REAIS["SBGR"]


@pytest.mark.parametrize("prefixo", ["TAF", "TAF AMD", "TAF COR"])
def test_req_j01_amd_cor(prefixo):
    r = avaliar(f"{prefixo} SBGR 102222Z 1100/1112 09005KT CAVOK")
    assert r.veredito == "JANELA"


def test_req_j01_igual_espacos_e_quebras():
    r = avaliar("TAF  SBGR\n102222Z 1100/1112   09005KT CAVOK=\n")
    assert r.veredito == "JANELA"


@pytest.mark.parametrize("texto", ["", "TAF 102222Z 1100/1112 CAVOK", "TAF SBGR 1022Z 1100/1112 CAVOK",
                                   "TAF SBGR 102222Z 1100-1112 CAVOK", "TAF SBGR 102222Z 1125/1130 CAVOK"])
def test_req_j01_formato_invalido(texto):
    assert_recusa(avaliar(texto), "formato_invalido")


def test_req_j01_escopo_antes_do_resto():
    assert_recusa(avaliar("TAF KJFK ...", icao="KJFK"), "fora_do_escopo")


def test_req_j01_icao_divergente():
    assert_recusa(avaliar(taf("09005KT CAVOK"), icao="SBSP"), "icao_divergente")


# --------------------------------------------------------------------------- REQ-J-02 TAF sem uso

def test_req_j02_nil():
    assert_recusa(avaliar("TAF SBGR 102222Z NIL"), "sem_dado")


def test_req_j02_cnl():
    assert_recusa(avaliar("TAF AMD SBGR 102222Z 1100/1112 CNL"), "taf_cancelado")


def test_req_j02_vencido():
    assert_recusa(avaliar(taf("CAVOK"), agora=datetime(2026, 11, 11, 12, 0, tzinfo=UTC)), "taf_vencido")


def test_req_j02_ultima_hora_ainda_vale():
    r = avaliar(taf("CAVOK"), agora=datetime(2026, 11, 11, 11, 59, tzinfo=UTC))
    assert list(mapa(r)) == ["11Z"]


def test_req_j02_emissao_no_futuro():
    assert_recusa(avaliar(taf("CAVOK", emissao="110040Z"), agora=AGORA), "horario_futuro")


def test_req_j02_virada_de_mes():
    r = avaliar("TAF SBGR 302200Z 0100/0112 CAVOK", agora=datetime(2026, 12, 1, 0, 30, tzinfo=UTC))
    assert r.resumo.emitido_utc == "2026-11-30T22:00:00Z"
    assert r.resumo.validade_inicio == "2026-12-01T00:00:00Z"


def test_req_j02_virada_de_ano():
    r = avaliar("TAF SBGR 312200Z 0100/0112 CAVOK", agora=datetime(2027, 1, 1, 0, 30, tzinfo=UTC))
    assert r.resumo.validade_inicio == "2027-01-01T00:00:00Z"


def test_req_j02_agora_antes_do_inicio_comeca_no_inicio():
    r = avaliar(taf("CAVOK"), agora=datetime(2026, 11, 10, 22, 40, tzinfo=UTC))
    assert list(mapa(r))[0] == "00Z"


def test_req_j02_agora_sem_fuso():
    with pytest.raises(ValueError):
        avaliar_taf(taf("CAVOK"), "SBGR", datetime(2026, 11, 11, 0, 30))


# --------------------------------------------------------------------------- REQ-J-03 condições

@pytest.mark.parametrize("corpo,esperado", [
    ("09005KT CAVOK", "VMC"),
    ("09005KT 9999 NSC", "VMC"),
    ("09005KT 0800 FG VV002", "IMC"),
    ("09005KT 9999 BKN015 TX25/1118Z TN15/1109Z", "VMC"),
    ("09005KT 9999 BKN030 RMK BKN002", "VMC"),
])
def test_req_j03_condicoes_da_base(corpo, esperado):
    assert set(mapa(avaliar(taf(corpo))).values()) == {esperado}


def test_req_j03_nsw_ignorado():
    r = avaliar(taf("09005KT 4000 RA BKN008 BECMG 1102/1104 9999 NSW BKN030"))
    assert mapa(r)["05Z"] == "VMC"


@pytest.mark.parametrize("corpo", ["09005KT BKN030", "09005KT 9999 TX25/1118Z", "09005KT 9999 BKN///"])
def test_req_j03_base_incompleta(corpo):
    assert_recusa(avaliar(taf(corpo)), "taf_incompleto")


# --------------------------------------------------------------------------- REQ-J-04 grupos de mudança

def test_req_j04_becmg_so_vento_nao_muda_nada():
    r = avaliar(taf("09005KT 4000 BR BKN008 BECMG 1102/1104 27010KT"))
    assert set(mapa(r).values()) == {"IMC"}


def test_req_j04_becmg_so_visibilidade_mantem_nuvens():
    r = avaliar(taf("09005KT 9999 BKN008 BECMG 1102/1104 8000"))
    assert mapa(r)["06Z"] == "IMC"


def test_req_j04_becmg_nuvens_substituem_camadas_e_transicao_e_pior_caso():
    m = mapa(avaliar(taf("09005KT 9999 BKN008 BECMG 1102/1104 SCT020")))
    assert (m["01Z"], m["02Z"], m["03Z"], m["04Z"]) == ("IMC", "IMC", "IMC", "VMC")


def test_req_j04_becmg_cavok():
    m = mapa(avaliar(taf("09005KT 3000 BR BKN005 BECMG 1102/1104 CAVOK")))
    assert m["04Z"] == "VMC" and m["03Z"] == "IMC"


@pytest.mark.parametrize("grupo", ["TEMPO", "PROB30", "PROB40", "PROB40 TEMPO", "PROB30 TEMPO"])
def test_req_j04_temporario_e_pior_caso_so_no_periodo(grupo):
    m = mapa(avaliar(taf(f"09005KT CAVOK {grupo} 1105/1107 3000 BR")))
    assert (m["04Z"], m["05Z"], m["06Z"], m["07Z"]) == ("VMC", "IMC", "IMC", "VMC")


def test_req_j04_temporario_herda_o_que_nao_informa():
    m = mapa(avaliar(taf("09005KT 9999 BKN008 TEMPO 1105/1107 SCT030")))  # nuvens melhoram, mas vigente é IMC
    assert m["05Z"] == "IMC"


# --------------------------------------------------------------------------- REQ-J-05 veredito por hora

def test_req_j05_comeca_na_hora_atual_e_vai_ate_o_fim():
    r = avaliar(taf("CAVOK"), agora=datetime(2026, 11, 11, 3, 40, tzinfo=UTC))
    assert list(mapa(r)) == [f"{h:02d}Z" for h in range(3, 12)]


@pytest.mark.parametrize("corpo,esperado", [("5000 BKN015", "VMC"), ("4900 BKN015", "IMC"), ("5000 BKN014", "IMC")])
def test_req_j05_limites_inclusivos(corpo, esperado):
    assert set(mapa(avaliar(taf("09005KT " + corpo))).values()) == {esperado}


def test_req_j05_grupo_responsavel_e_motivo():
    r = avaliar(taf("09005KT CAVOK PROB40 1105/1107 3000 BR"))
    hora = [h for h in r.horas if h["hora"].endswith("05:00:00Z")][0]
    assert hora["grupo"] == "PROB40 1105/1107"
    assert "visibilidade 3000 m" in hora["motivo"].lower()


# --------------------------------------------------------------------------- REQ-J-06 períodos e melhor janela

def test_req_j06_empate_fica_com_a_mais_cedo():
    r = avaliar(taf("09005KT CAVOK TEMPO 1104/1106 3000 BR", validade="1100/1110"))
    assert r.resumo.melhor_janela == {"inicio": "2026-11-11T00:00:00Z", "fim": "2026-11-11T04:00:00Z", "horas": 4}


def test_req_j06_sem_vmc():
    assert avaliar(taf("09005KT 2000 BR OVC003")).resumo.melhor_janela is None


def test_req_j06_vmc_nao_se_quebra_por_becmg_que_nao_muda_o_resultado():
    r = avaliar(taf("09005KT CAVOK BECMG 1102/1104 27010KT BECMG 1106/1108 SCT030"))
    assert periodos(r) == [("11T00", "11T12", "VMC")]


# --------------------------------------------------------------------------- REQ-J-07 resumo

@pytest.mark.parametrize("texto", [REAIS["SBGR"], "TAF KJFK ...", "TAF SBGR 102222Z NIL"])
def test_req_j07_chaves_exatas(texto):
    icao = "KJFK" if "KJFK" in texto else "SBGR"
    assert set(avaliar(texto, icao=icao).resumo.para_dict()) == CHAVES


def test_req_j07_recusa_sem_periodos():
    d = avaliar("TAF SBGR 102222Z NIL").resumo.para_dict()
    assert d["periodos"] == [] and d["melhor_janela"] is None and d["motivo"]


# --------------------------------------------------------------------------- REQ-J-08 independência

def test_req_j08_so_biblioteca_padrao():
    permitidos = {"__future__", "re", "datetime", "dataclasses", "enum", "unicodedata", "typing", "app"}
    arvore = ast.parse(Path(harness_taf.__file__).read_text(encoding="utf-8"))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados |= {a.name.split(".")[0] for a in no.names}
        elif isinstance(no, ast.ImportFrom):
            importados.add((no.module or "").split(".")[0])
    assert importados <= permitidos, importados - permitidos


def test_req_j08_deterministico():
    assert avaliar(REAIS["SBGR"]) == avaliar(REAIS["SBGR"])


# --------------------------------------------------------------------------- auxiliares do agente

def test_veredito_na_hora():
    resumo = avaliar(REAIS["SBGR"]).resumo
    assert veredito_na_hora(resumo, datetime(2026, 11, 11, 9, 15, tzinfo=UTC)) == "IMC"
    assert veredito_na_hora(resumo, datetime(2026, 11, 11, 15, 0, tzinfo=UTC)) == "VMC"
    assert veredito_na_hora(resumo, datetime(2026, 11, 12, 6, 0, tzinfo=UTC)) is None


def test_texto_modelo_janela():
    t = texto_modelo_janela(avaliar(REAIS["SBGR"]).resumo)
    assert "SBGR" in t and "Melhor janela" in t and "14Z" in t and "previsão" in t.lower()


def test_texto_modelo_janela_recusa():
    t = texto_modelo_janela(avaliar("TAF SBGR 102222Z NIL").resumo)
    assert "SBGR" in t and "NIL" in t
