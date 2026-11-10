"""Testes das ferramentas, derivados de specs/02-ferramentas/requisitos.md.

Sem rede: a API é simulada com httpx.MockTransport e respostas reais gravadas em tests/fixtures/awc/.
O único teste que usa a rede está marcado com @pytest.mark.rede (rodar com: pytest -m rede).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app import ferramentas, harness
from app.ferramentas import STATUS, USER_AGENT, ClienteAWC

UTC = timezone.utc
FIXTURES = Path(__file__).parent / "fixtures" / "awc"


def carregar(nome: str):
    return json.loads((FIXTURES / nome).read_text(encoding="utf-8"))


METAR_SBGR = carregar("metar_SBGR.json")
METAR_SBGR_3H = carregar("metar_SBGR_3h.json")
TAF_SBGR = carregar("taf_SBGR.json")
ERRO_400 = carregar("erro_400.json")

OBS_SBGR = datetime.fromtimestamp(METAR_SBGR[0]["obsTime"], UTC)
AGORA = OBS_SBGR + timedelta(minutes=10)
CHAVES = {
    "icao", "tipo", "status", "texto_bruto", "resposta_api", "url", "http_status",
    "de_cache", "tentativas", "buscado_em", "duracao_ms", "erro",
}


# --------------------------------------------------------------------------- helpers

def ok(dados):
    return httpx.Response(200, json=dados)


class ApiFalsa:
    """Handler do MockTransport. Devolve as respostas em ordem (a última se repete) e registra as requisições.

    Cada resposta pode ser um httpx.Response, uma exceção (lançada) ou uma função request -> Response.
    """

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.requisicoes: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requisicoes.append(request)
        if not self.respostas:
            raise AssertionError("a API não deveria ter sido chamada")
        r = self.respostas.pop(0) if len(self.respostas) > 1 else self.respostas[0]
        if isinstance(r, Exception):
            raise r
        return r(request) if callable(r) else r


class Relogio:
    def __init__(self, t: datetime):
        self.t = t

    def __call__(self) -> datetime:
        return self.t

    def avancar(self, **delta):
        self.t += timedelta(**delta)


def montar(*respostas, agora: datetime = AGORA, **kwargs):
    api = ApiFalsa(*respostas)
    relogio = Relogio(agora)
    http = httpx.Client(transport=httpx.MockTransport(api))
    return ClienteAWC(http=http, relogio=relogio, **kwargs), api, relogio


def por_caminho(request: httpx.Request) -> httpx.Response:
    return ok(METAR_SBGR if request.url.path.endswith("/metar") else TAF_SBGR)


# --------------------------------------------------------------------------- REQ-F-01 ICAO

@pytest.mark.parametrize("icao", ["SB;GR", "SBGR,KJFK", "SBG", "SBGR1", "", "S1GR", "SB GR"])
def test_req_f01_icao_invalido_sem_rede(icao):
    c, api, _ = montar()
    r = c.buscar_metar(icao)
    assert r.status == "icao_invalido"
    assert r.tentativas == 0
    assert r.url is None
    assert api.requisicoes == []


def test_req_f01_icao_nao_texto():
    c, api, _ = montar()
    assert c.buscar_metar(None).status == "icao_invalido"
    assert api.requisicoes == []


def test_req_f01_normaliza_espacos_e_minusculas():
    c, api, _ = montar(ok(METAR_SBGR))
    r = c.buscar_metar(" sbgr ")
    assert r.status == "ok"
    assert r.icao == "SBGR"
    assert api.requisicoes[0].url.params["ids"] == "SBGR"


# --------------------------------------------------------------------------- REQ-F-02 escopo

@pytest.mark.parametrize("icao", ["KMIA", "KJFK", "SAEZ"])
@pytest.mark.parametrize("metodo", ["buscar_metar", "buscar_taf"])
def test_req_f02_fora_do_escopo_sem_rede(icao, metodo):
    c, api, _ = montar()
    r = getattr(c, metodo)(icao)
    assert r.status == "fora_do_escopo"
    assert r.tentativas == 0
    assert api.requisicoes == []


def test_req_f02_prefixos_vem_do_harness():
    assert ferramentas.PREFIXOS_BR is harness.PREFIXOS_BR


# --------------------------------------------------------------------------- REQ-F-03 requisição

def test_req_f03_requisicao_metar():
    c, api, _ = montar(ok(METAR_SBGR))
    c.buscar_metar("SBGR")
    req = api.requisicoes[0]
    assert req.method == "GET"
    assert str(req.url).startswith("https://aviationweather.gov/api/data/metar?")
    assert req.url.params["ids"] == "SBGR"
    assert req.url.params["format"] == "json"


def test_req_f03_requisicao_taf():
    c, api, _ = montar(ok(TAF_SBGR))
    c.buscar_taf("SBGR")
    req = api.requisicoes[0]
    assert req.url.path == "/api/data/taf"
    assert req.url.params["ids"] == "SBGR"
    assert req.url.params["format"] == "json"


def test_req_f03_user_agent_do_projeto():
    c, api, _ = montar(ok(METAR_SBGR))
    c.buscar_metar("SBGR")
    assert api.requisicoes[0].headers["user-agent"] == USER_AGENT


def test_req_f03_timeout_padrao():
    c, api, _ = montar(ok(METAR_SBGR))
    c.buscar_metar("SBGR")
    assert api.requisicoes[0].extensions["timeout"]["read"] == 10.0


def test_req_f03_configuracao_pelo_ambiente(monkeypatch):
    monkeypatch.setenv("AWC_BASE_URL", "https://exemplo.test/api")
    monkeypatch.setenv("AWC_TIMEOUT_S", "3")
    c, api, _ = montar(ok(METAR_SBGR))
    c.buscar_metar("SBGR")
    req = api.requisicoes[0]
    assert req.url.host == "exemplo.test"
    assert req.url.path == "/api/metar"
    assert req.extensions["timeout"]["read"] == 3.0


def test_req_f03_parametro_vence_ambiente(monkeypatch):
    monkeypatch.setenv("AWC_BASE_URL", "https://exemplo.test/api")
    c, api, _ = montar(ok(METAR_SBGR), base_url="https://outro.test/x", timeout_s=2)
    c.buscar_metar("SBGR")
    req = api.requisicoes[0]
    assert req.url.host == "outro.test"
    assert req.extensions["timeout"]["read"] == 2.0


# --------------------------------------------------------------------------- REQ-F-04 resposta com dado

def test_req_f04_metar_ok_texto_exato():
    c, _, _ = montar(ok(METAR_SBGR))
    r = c.buscar_metar("SBGR")
    assert r.status == "ok"
    assert r.texto_bruto == METAR_SBGR[0]["rawOb"]
    assert r.http_status == 200
    assert r.tentativas == 1
    assert r.de_cache is False
    assert r.erro is None


def test_req_f04_taf_ok_texto_exato():
    c, _, _ = montar(ok(TAF_SBGR))
    r = c.buscar_taf("SBGR")
    assert r.status == "ok"
    assert r.tipo == "taf"
    assert r.texto_bruto == TAF_SBGR[0]["rawTAF"]


def test_req_f04_usa_o_primeiro_boletim():
    c, _, _ = montar(ok(METAR_SBGR_3H), agora=datetime.fromtimestamp(METAR_SBGR_3H[0]["obsTime"], UTC))
    assert c.buscar_metar("SBGR").texto_bruto == METAR_SBGR_3H[0]["rawOb"]


@pytest.mark.parametrize("elemento", [{"icaoId": "SBGR"}, {"rawOb": ""}, {"rawOb": 123}, {"rawOb": None}])
def test_req_f04_texto_bruto_ausente_e_erro(elemento):
    c, _, _ = montar(ok([elemento]))
    r = c.buscar_metar("SBGR")
    assert r.status == "erro_api"
    assert r.texto_bruto is None


# --------------------------------------------------------------------------- REQ-F-05 sem dado

def test_req_f05_204_sem_dado():
    c, _, _ = montar(httpx.Response(204))
    r = c.buscar_metar("SBXX")
    assert r.status == "sem_dado"
    assert r.http_status == 204
    assert r.texto_bruto is None
    assert r.resposta_api is None


def test_req_f05_lista_vazia_sem_dado():
    c, _, _ = montar(ok([]))
    r = c.buscar_taf("SDCO")
    assert r.status == "sem_dado"
    assert r.resposta_api == []


# --------------------------------------------------------------------------- REQ-F-06 falhas

def test_req_f06_timeout_duas_vezes():
    c, api, _ = montar(httpx.ReadTimeout("lento"), httpx.ReadTimeout("lento"))
    r = c.buscar_metar("SBGR")
    assert r.status == "erro_api"
    assert r.tentativas == 2
    assert len(api.requisicoes) == 2
    assert "Timeout" in r.erro


@pytest.mark.parametrize("falha", [httpx.ReadTimeout("lento"), httpx.ConnectError("sem rede"),
                                   httpx.Response(503)])
def test_req_f06_nova_tentativa_recupera(falha):
    c, api, _ = montar(falha, ok(METAR_SBGR))
    r = c.buscar_metar("SBGR")
    assert r.status == "ok"
    assert r.tentativas == 2
    assert len(api.requisicoes) == 2


def test_req_f06_5xx_duas_vezes():
    c, _, _ = montar(httpx.Response(500), httpx.Response(500))
    r = c.buscar_metar("SBGR")
    assert r.status == "erro_api"
    assert r.tentativas == 2
    assert r.http_status == 500
    assert "500" in r.erro


def test_req_f06_429_limite_sem_nova_tentativa():
    c, api, _ = montar(httpx.Response(429), ok(METAR_SBGR))
    r = c.buscar_metar("SBGR")
    assert r.status == "limite_api"
    assert r.tentativas == 1
    assert len(api.requisicoes) == 1


def test_req_f06_400_com_mensagem_da_api():
    c, api, _ = montar(httpx.Response(400, json=ERRO_400), ok(METAR_SBGR))
    r = c.buscar_metar("SBGR")
    assert r.status == "erro_api"
    assert r.tentativas == 1
    assert len(api.requisicoes) == 1
    assert r.http_status == 400
    assert ERRO_400["error"] in r.erro
    assert r.resposta_api == ERRO_400


@pytest.mark.parametrize("resposta", [
    httpx.Response(200, content=b"<html>fora do ar</html>"),
    httpx.Response(200, json={"rawOb": "METAR SBGR ..."}),
])
def test_req_f06_json_invalido_ou_nao_lista(resposta):
    c, _, _ = montar(resposta)
    r = c.buscar_metar("SBGR")
    assert r.status == "erro_api"
    assert r.texto_bruto is None


@pytest.mark.parametrize("respostas", [
    (httpx.ReadTimeout("x"),),
    (httpx.ConnectError("x"),),
    (httpx.Response(500),),
    (httpx.Response(429),),
    (httpx.Response(404),),
    (httpx.Response(200, content=b"nao e json"),),
])
def test_req_f06_falha_nunca_lanca_nem_tem_texto(respostas):
    c, _, _ = montar(*respostas)
    r = c.buscar_metar("SBGR")
    assert r.status in {"erro_api", "limite_api"}
    assert r.texto_bruto is None
    assert r.erro


# --------------------------------------------------------------------------- REQ-F-07 cache

def test_req_f07_cache_dentro_de_5_min():
    c, api, rel = montar(ok(METAR_SBGR))
    r1 = c.buscar_metar("SBGR")
    rel.avancar(minutes=4)
    r2 = c.buscar_metar("SBGR")
    assert len(api.requisicoes) == 1
    assert r2.de_cache is True
    assert r2.tentativas == 0
    assert r2.texto_bruto == r1.texto_bruto
    assert r2.url == r1.url
    assert r2.buscado_em != r1.buscado_em


def test_req_f07_cache_vence_em_5_min():
    c, api, rel = montar(ok(METAR_SBGR))
    c.buscar_metar("SBGR")
    rel.avancar(minutes=6)
    r2 = c.buscar_metar("SBGR")
    assert len(api.requisicoes) == 2
    assert r2.de_cache is False


def test_req_f07_metar_com_mais_de_55_min_ignora_cache():
    c, api, rel = montar(ok(METAR_SBGR), agora=OBS_SBGR + timedelta(minutes=52))
    c.buscar_metar("SBGR")
    rel.avancar(minutes=4)  # cache ainda no prazo, mas o boletim já tem 56 min
    r2 = c.buscar_metar("SBGR")
    assert len(api.requisicoes) == 2
    assert r2.de_cache is False


def test_req_f07_metar_sem_obstime_ignora_cache():
    c, api, rel = montar(ok([{"rawOb": METAR_SBGR[0]["rawOb"]}]))
    c.buscar_metar("SBGR")
    rel.avancar(minutes=1)
    c.buscar_metar("SBGR")
    assert len(api.requisicoes) == 2


def test_req_f07_taf_nao_tem_regra_dos_55_min():
    c, api, rel = montar(ok(TAF_SBGR), agora=datetime(2026, 11, 10, 23, 0, tzinfo=UTC))
    c.buscar_taf("SBGR")
    rel.avancar(minutes=4)
    assert c.buscar_taf("SBGR").de_cache is True
    assert len(api.requisicoes) == 1


def test_req_f07_sem_dado_nao_vai_para_o_cache():
    c, api, _ = montar(httpx.Response(204))
    c.buscar_metar("SBXX")
    c.buscar_metar("SBXX")
    assert len(api.requisicoes) == 2


def test_req_f07_erro_nao_vai_para_o_cache():
    c, api, _ = montar(httpx.Response(500))
    c.buscar_metar("SBGR")
    c.buscar_metar("SBGR")
    assert len(api.requisicoes) == 4


def test_req_f07_metar_e_taf_nao_se_misturam():
    c, api, _ = montar(por_caminho)
    m = c.buscar_metar("SBGR")
    t = c.buscar_taf("SBGR")
    assert len(api.requisicoes) == 2
    assert m.texto_bruto.startswith("METAR")
    assert t.texto_bruto.startswith("TAF")


def test_req_f07_falha_depois_do_cache_vencer_nao_devolve_texto_antigo():
    c, _, rel = montar(ok(METAR_SBGR), httpx.Response(500))
    c.buscar_metar("SBGR")
    rel.avancar(minutes=6)
    r = c.buscar_metar("SBGR")
    assert r.status == "erro_api"
    assert r.texto_bruto is None


def test_req_f07_limpar_cache():
    c, api, _ = montar(ok(METAR_SBGR))
    c.buscar_metar("SBGR")
    c.limpar_cache()
    c.buscar_metar("SBGR")
    assert len(api.requisicoes) == 2


# --------------------------------------------------------------------------- REQ-F-08 resultado

def _resultados_variados():
    casos = []
    for respostas, icao in [((ok(METAR_SBGR),), "SBGR"), ((httpx.Response(204),), "SBXX"),
                            ((), "SB;GR"), ((httpx.Response(500),), "SBGR")]:
        c, _, _ = montar(*respostas)
        casos.append(c.buscar_metar(icao))
    return casos


def test_req_f08_chaves_exatas_e_status_valido():
    for r in _resultados_variados():
        assert set(r.para_dict()) == CHAVES
        assert r.status in STATUS
        assert r.tipo == "metar"


def test_req_f08_metadados():
    c, _, _ = montar(ok(METAR_SBGR))
    r = c.buscar_metar("SBGR")
    assert r.buscado_em == AGORA.strftime("%Y-%m-%dT%H:%M:%SZ")
    assert isinstance(r.duracao_ms, int) and r.duracao_ms >= 0
    assert "ids=SBGR" in r.url and "format=json" in r.url
    assert r.resposta_api == METAR_SBGR


def test_req_f08_buscado_em_formato_iso():
    for r in _resultados_variados():
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", r.buscado_em)


def test_req_f08_texto_bruto_separado_do_json():
    c, _, _ = montar(ok(METAR_SBGR))
    r = c.buscar_metar("SBGR")
    assert isinstance(r.texto_bruto, str)
    assert isinstance(r.resposta_api, list)
    assert "fltCat" not in r.texto_bruto


# --------------------------------------------------------------------------- REQ-F-09 atalhos e rede

def test_req_f09_atalhos_usam_a_instancia_padrao(monkeypatch):
    c, api, _ = montar(por_caminho)
    monkeypatch.setattr(ferramentas, "_cliente_padrao", c)
    assert ferramentas.buscar_metar("SBGR").status == "ok"
    assert ferramentas.buscar_taf("SBGR").status == "ok"
    assert len(api.requisicoes) == 2


@pytest.mark.rede
def test_req_f09_api_real_sbgr():
    r = ClienteAWC().buscar_metar("SBGR")
    assert r.status == "ok", r.erro
    assert re.match(r"^(METAR|SPECI) SBGR \d{6}Z", r.texto_bruto)
