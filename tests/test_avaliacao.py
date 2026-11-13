"""Testes das métricas da avaliação, derivados de specs/06-avaliacao/requisitos.md.

Só funções puras e o mundo congelado; a rodada com o Ollama real é o próprio avaliar.py.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("avaliar", RAIZ / "avaliacao" / "avaliar.py")
avaliar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(avaliar)

UTC = timezone.utc


# --------------------------------------------------------------------------- REQ-V-01 harness × gabarito

def linha_m(n, metar, grupo, api="VFR", obs="2026-11-10 12:00Z"):
    return {"n": n, "icao": metar.split()[1], "obs": obs, "metar": metar, "api": api, "grupo": grupo}


def test_v01_harness_concorda_e_lista_divergencia():
    linhas = [
        linha_m(1, "METAR SBGR 101200Z 12008KT 9999 FEW030 SCT100 25/16 Q1018", "VMC"),
        linha_m(2, "METAR SBRJ 101200Z 20006KT 9999 BKN015 24/19 Q1016", "VMC", api="MVFR"),
        linha_m(3, "METAR SBSP 101200Z 15010KT 4000 BR BKN008 18/17 Q1020", "IMC", api="IFR"),
        linha_m(4, "METAR SBCT 101200Z 09004KT 6000 OVC012 15/14 Q1021", "VMC", api="MVFR"),  # rótulo errado
    ]
    saida = avaliar.avaliar_harness(linhas)
    assert [s["harness"] for s in saida] == ["VMC", "VMC", "IMC", "IMC"]
    assert [s["acerto_harness"] for s in saida] == [True, True, True, False]
    assert [s["api_lida"] for s in saida] == ["VMC", "IMC", "IMC", "IMC"]
    assert [s["acerto_api"] for s in saida] == [True, False, True, False]


def test_v01_invalido_do_grupo_vale_como_recusa():
    linhas = [linha_m(1, "METAR SBGR 101200Z 12008KT //// FEW030 25/16 Q1018", "INVALIDO")]
    assert avaliar.avaliar_harness(linhas)[0]["acerto_harness"] is True


# --------------------------------------------------------------------------- REQ-V-02 ICAO

@pytest.mark.parametrize("consultados, esperados, classe", [
    (["SBSP"], ["SBSP"], "exato"),
    (["SBSP", "SBGR"], ["SBGR", "SBSP"], "exato"),
    (["SBGR"], ["SBGR", "SBSP"], "parcial"),
    (["SBGR", "SBSP", "SBKP"], ["SBGR", "SBSP"], "extra"),
    (["SBKP"], ["SBGR"], "errado"),
    (["SBKP", "SBSP"], ["SBGR", "SBSP"], "errado"),
    ([], ["SBGR"], "nenhum"),
])
def test_v02_classificar_icaos(consultados, esperados, classe):
    assert avaliar.classificar_icaos(consultados, esperados) == classe


# --------------------------------------------------------------------------- REQ-V-03 recusas

def traco(*passos):
    return {"passos": list(passos)}


@pytest.mark.parametrize("t, origem", [
    (traco({"tipo": "prefiltro", "passou": False, "regra": "pedido_ifr"}), "prefiltro:pedido_ifr"),
    (traco({"tipo": "prefiltro", "passou": True}, {"tipo": "erro", "regra": "sem_avaliacao"}), "agente:sem_avaliacao"),
    (traco({"tipo": "prefiltro", "passou": True},
           {"tipo": "ferramenta", "nome": "buscar_metar", "resultado": {"status": "ok"}},
           {"tipo": "harness", "icao": "SBGL", "veredito": "RECUSA", "codigo_recusa": "dado_desatualizado"}),
     "harness:dado_desatualizado"),
    (traco({"tipo": "prefiltro", "passou": True},
           {"tipo": "ferramenta", "nome": "buscar_metar", "resultado": {"status": "fora_do_escopo", "icao": "KJFK"}}),
     "busca:fora_do_escopo"),
])
def test_v03_origem_da_recusa(t, origem):
    assert avaliar.origem_recusa(t, "RECUSA") == origem


def test_v03_sem_recusa_nao_tem_origem():
    assert avaliar.origem_recusa(traco({"tipo": "prefiltro", "passou": True}), "VMC") is None


def test_v03_falsa_recusa():
    normal = {"tipo": "normal", "icaos_esperados": ["SBGL"]}
    resp_dado = {"veredito": "RECUSA", "avaliacoes": [{"icao": "SBGL", "veredito": "RECUSA"}]}
    assert avaliar.eh_falsa_recusa(normal, resp_dado, "harness:dado_desatualizado") is False  # recusa certa
    assert avaliar.eh_falsa_recusa(normal, resp_dado, "prefiltro:pedido_ifr") is True
    assert avaliar.eh_falsa_recusa(normal, resp_dado, "agente:sem_avaliacao") is True
    outro = {"veredito": "RECUSA", "avaliacoes": [{"icao": "KGLX", "veredito": "RECUSA"}]}
    assert avaliar.eh_falsa_recusa(normal, outro, "busca:fora_do_escopo") is True  # trocou o aeródromo
    assert avaliar.eh_falsa_recusa(normal, {"veredito": "VMC", "avaliacoes": []}, None) is False
    assert avaliar.eh_falsa_recusa({"tipo": "recusa"}, resp_dado, "prefiltro:pedido_ifr") is False


# --------------------------------------------------------------------------- REQ-V-04 juiz

def test_v04_le_nota_do_juiz():
    texto = 'Avaliação: {"consistencia": 5, "teto_visibilidade": 4, "sem_invencao": 5, "justificativa": "ok"} fim'
    assert avaliar.ler_juiz(texto) == {"consistencia": 5, "teto_visibilidade": 4, "sem_invencao": 5,
                                       "justificativa": "ok"}


@pytest.mark.parametrize("texto", [
    "nota 5",
    '{"consistencia": 6, "teto_visibilidade": 4, "sem_invencao": 5}',
    '{"consistencia": 5, "teto_visibilidade": 4}',
    '{"consistencia": "cinco", "teto_visibilidade": 4, "sem_invencao": 5}',
])
def test_v04_nota_invalida_vira_none(texto):
    assert avaliar.ler_juiz(texto) is None


# --------------------------------------------------------------------------- REQ-V-05/06 bloqueios e tokens

def test_v06_tokens_somam_entrada_e_saida_dos_passos_do_modelo():
    t = traco({"tipo": "modelo", "prompt_eval_count": 600, "eval_count": 20},
              {"tipo": "ferramenta"},
              {"tipo": "modelo", "prompt_eval_count": 700, "eval_count": 80})
    assert avaliar.tokens_do_traco(t) == 1400


def test_v06_tokens_sem_modelo_e_zero():
    assert avaliar.tokens_do_traco(traco({"tipo": "prefiltro", "passou": False})) == 0


# --------------------------------------------------------------------------- mundo congelado (decisão E1)

MUNDO = [{"icaoId": "SBSP", "name": "Sao Paulo/Congonhas, SP, BR", "obsTime": 1794385560,
          "rawOb": "SPECI SBSP 110826Z AUTO 05004KT 010V110 9999 BKN011 BKN014 16/14 Q1025"}]
RELOGIO = datetime(2026, 11, 11, 8, 45, tzinfo=UTC)


def test_mundo_congelado_devolve_metar_gravado():
    cliente = avaliar.cliente_mundo(MUNDO, lambda: RELOGIO)
    r = cliente.buscar_metar("SBSP")
    assert r.status == "ok" and r.texto_bruto.startswith("SPECI SBSP 110826Z")
    assert r.resposta_api[0]["name"].startswith("Sao Paulo/Congonhas")


def test_mundo_congelado_sem_metar_e_fora_do_escopo():
    cliente = avaliar.cliente_mundo(MUNDO, lambda: RELOGIO)
    assert cliente.buscar_metar("SBRP").status == "sem_dado"
    assert cliente.buscar_metar("KJFK").status == "fora_do_escopo"
    assert cliente.buscar_taf("SBSP").status == "sem_dado"


# --------------------------------------------------------------------------- resumo

def test_resumo_conta_metricas():
    harness = [{"acerto_harness": True, "acerto_api": True}, {"acerto_harness": True, "acerto_api": False}]
    agente = [
        {"prompt": "v3", "tipo": "normal", "classe_icao": "exato", "veredito": "VMC", "falsa_recusa": False,
         "bloqueio": None, "tokens": 1000, "duracao_ms": 10000},
        {"prompt": "v3", "tipo": "normal", "classe_icao": "errado", "veredito": "IMC", "falsa_recusa": False,
         "bloqueio": "polaridade", "tokens": 1200, "duracao_ms": 20000},
        {"prompt": "v3", "tipo": "recusa", "classe_icao": None, "veredito": "RECUSA", "falsa_recusa": False,
         "bloqueio": None, "tokens": 0, "duracao_ms": 5},
        {"prompt": "v3", "tipo": "recusa", "classe_icao": None, "veredito": "VMC", "falsa_recusa": False,
         "bloqueio": None, "tokens": 800, "duracao_ms": 9000},
    ]
    juiz = [{"consistencia": 5, "teto_visibilidade": 4, "sem_invencao": 5},
            {"consistencia": 3, "teto_visibilidade": 2, "sem_invencao": None}]
    r = avaliar.resumir(harness, agente, juiz)
    assert r["harness_acertos"] == (2, 2) and r["api_acertos"] == (1, 2)
    v3 = r["prompts"]["v3"]
    assert v3["icao_exato"] == (1, 2)
    assert v3["recusa_correta"] == (1, 2)
    assert v3["falsa_recusa"] == (0, 2)
    assert v3["bloqueios"] == 1
    assert v3["tokens_medios"] == 1000
    assert r["juiz_medias"] == {"consistencia": 4.0, "teto_visibilidade": 3.0, "sem_invencao": 5.0}
    assert r["juiz_sem_nota"] == 1
