"""Testes da API e da página, derivados de specs/04-interface/requisitos.md.

O agente é falso e os traços ficam em tmp_path; nenhum teste chama o Ollama nem a API meteorológica.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app import prompts
from app.agente import RespostaAgente
from app.main import criar_app, verificar_saude_ollama

INDEX = Path(__file__).resolve().parent.parent / "app" / "static" / "index.html"
SAUDE_OK = {"ollama": True, "modelo": "llama3.1:8b", "modelo_baixado": True}


def resposta(veredito="VMC", id_traco="0123456789ab") -> RespostaAgente:
    return RespostaAgente(id_traco=id_traco, veredito=veredito, motivo="Dentro dos mínimos VFR.", avaliacoes=[],
                          explicacao="Condições VMC em SBSP.", origem_explicacao="modelo", bloqueio=None,
                          aviso=prompts.AVISO, duracao_ms=17000)


class AgenteFalso:
    def __init__(self, devolve: RespostaAgente | None = None, erro: Exception | None = None):
        self.devolve = devolve or resposta()
        self.erro = erro
        self.perguntas: list[str] = []

    def perguntar(self, pergunta: str) -> RespostaAgente:
        self.perguntas.append(pergunta)
        if self.erro:
            raise self.erro
        return self.devolve


def montar(tmp_path, agente=None, saude=None) -> tuple[TestClient, AgenteFalso]:
    agente = agente or AgenteFalso()
    app = criar_app(agente=agente, pasta_traces=tmp_path, verificar_saude=saude or (lambda: SAUDE_OK))
    return TestClient(app, raise_server_exceptions=False), agente


def gravar_traco(pasta: Path, id_traco: str, inicio="2026-11-10T22:18:00Z", veredito="VMC",
                 pergunta="Dá pra ir VFR em Congonhas agora?") -> dict:
    pasta.mkdir(parents=True, exist_ok=True)
    dados = {"id": id_traco, "inicio": inicio, "pergunta": pergunta, "modelo": "llama3.1:8b",
             "versao_prompt": "v2", "passos": [{"tipo": "prefiltro", "t_ms": 0, "passou": True}],
             "resposta": {"veredito": veredito, "id_traco": id_traco}, "duracao_ms": 17000}
    carimbo = inicio.replace("-", "").replace(":", "")
    (pasta / f"{carimbo}_{id_traco}.json").write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados


# --------------------------------------------------------------------------- REQ-I-01 página

def test_req_i01_pagina(tmp_path):
    c, _ = montar(tmp_path)
    r = c.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert 'lang="pt-BR"' in r.text
    assert prompts.AVISO in r.text


def test_req_i07_exemplos_na_pagina(tmp_path):
    texto = montar(tmp_path)[0].get("/").text
    for exemplo in ["Dá pra ir VFR em Congonhas agora?", "Posso decolar de Congonhas mesmo assim?",
                    "Qual o melhor dia pra ir pra Miami nos próximos 5 dias?"]:
        assert exemplo in texto, exemplo


# --------------------------------------------------------------------------- REQ-I-02 pergunta

def test_req_i02_pergunta(tmp_path):
    c, agente = montar(tmp_path)
    r = c.post("/api/perguntar", json={"pergunta": "Dá pra ir VFR em Congonhas agora?"})
    assert r.status_code == 200
    assert r.json() == resposta().para_dict()
    assert agente.perguntas == ["Dá pra ir VFR em Congonhas agora?"]


def test_req_i02_recusa_tambem_e_200(tmp_path):
    c, _ = montar(tmp_path, agente=AgenteFalso(resposta("RECUSA")))
    r = c.post("/api/perguntar", json={"pergunta": "Posso decolar mesmo assim?"})
    assert r.status_code == 200
    assert r.json()["veredito"] == "RECUSA"


def test_req_i02_texto_vazio_vai_para_o_agente(tmp_path):
    c, agente = montar(tmp_path)
    assert c.post("/api/perguntar", json={"pergunta": ""}).status_code == 200
    assert agente.perguntas == [""]


@pytest.mark.parametrize("corpo", [{}, {"pergunta": 5}, {"pergunta": None}, {"texto": "oi"}, ["oi"]])
def test_req_i02_corpo_invalido_422(tmp_path, corpo):
    c, agente = montar(tmp_path)
    assert c.post("/api/perguntar", json=corpo).status_code == 422
    assert agente.perguntas == []


def test_req_i02_json_malformado_422(tmp_path):
    c, agente = montar(tmp_path)
    r = c.post("/api/perguntar", content=b"{nao e json", headers={"content-type": "application/json"})
    assert r.status_code == 422
    assert agente.perguntas == []


def test_req_i02_excecao_500_sem_pilha(tmp_path):
    c, _ = montar(tmp_path, agente=AgenteFalso(erro=RuntimeError("segredo interno /Users/x/arquivo.py")))
    r = c.post("/api/perguntar", json={"pergunta": "oi"})
    assert r.status_code == 500
    assert set(r.json()) == {"erro"}
    assert "segredo" not in r.text and "Traceback" not in r.text


# --------------------------------------------------------------------------- REQ-I-03 traço

def test_req_i03_traco_existente(tmp_path):
    dados = gravar_traco(tmp_path, "0123456789ab")
    r = montar(tmp_path)[0].get("/api/traco/0123456789ab")
    assert r.status_code == 200
    assert r.json() == dados


def test_req_i03_traco_inexistente(tmp_path):
    assert montar(tmp_path)[0].get("/api/traco/0123456789ab").status_code == 404


@pytest.mark.parametrize("id_traco", ["ABCDEF012345", "0123456789a", "0123456789abc", "0123456789ag",
                                      "..%2F..%2Fetc%2Fpasswd", "*", "0123456789a*"])
def test_req_i03_id_invalido_nao_toca_no_disco(tmp_path, monkeypatch, id_traco):
    c, _ = montar(tmp_path)
    chamadas = []
    original = Path.glob
    monkeypatch.setattr(Path, "glob", lambda self, padrao: chamadas.append(padrao) or original(self, padrao))
    assert c.get(f"/api/traco/{id_traco}").status_code == 404
    assert chamadas == []


def test_req_i03_barra_no_caminho_404(tmp_path):
    assert montar(tmp_path)[0].get("/api/traco/../../etc/passwd").status_code == 404


# --------------------------------------------------------------------------- REQ-I-04 execuções gravadas

def test_req_i04_lista_demo_do_mais_novo_para_o_mais_antigo(tmp_path):
    gravar_traco(tmp_path / "demo", "aaaaaaaaaaaa", inicio="2026-11-10T22:18:00Z", veredito="VMC")
    gravar_traco(tmp_path / "demo", "bbbbbbbbbbbb", inicio="2026-11-11T06:00:00Z", veredito="IMC",
                 pergunta="Congonhas com nevoeiro?")
    gravar_traco(tmp_path, "cccccccccccc")  # traço comum: não entra na lista
    r = montar(tmp_path)[0].get("/api/demo")
    assert r.status_code == 200
    assert r.json() == [
        {"id": "bbbbbbbbbbbb", "pergunta": "Congonhas com nevoeiro?", "veredito": "IMC", "inicio": "2026-11-11T06:00:00Z"},
        {"id": "aaaaaaaaaaaa", "pergunta": "Dá pra ir VFR em Congonhas agora?", "veredito": "VMC",
         "inicio": "2026-11-10T22:18:00Z"},
    ]


def test_req_i04_traco_da_demo_abre(tmp_path):
    dados = gravar_traco(tmp_path / "demo", "aaaaaaaaaaaa")
    assert montar(tmp_path)[0].get("/api/traco/aaaaaaaaaaaa").json() == dados


def test_req_i04_sem_pasta_demo(tmp_path):
    assert montar(tmp_path)[0].get("/api/demo").json() == []


# --------------------------------------------------------------------------- REQ-I-05 saúde

def test_req_i05_rota_devolve_a_checagem(tmp_path):
    assert montar(tmp_path)[0].get("/api/saude").json() == SAUDE_OK


def test_req_i05_checagem_que_quebra_vira_indisponivel(tmp_path):
    def quebra():
        raise RuntimeError("x")

    r = montar(tmp_path, saude=quebra)[0].get("/api/saude")
    assert r.status_code == 200
    assert r.json()["ollama"] is False


def _ollama(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_req_i05_ollama_com_modelo():
    http = _ollama(lambda req: httpx.Response(200, json={"models": [{"name": "llama3.1:8b"}, {"name": "llama3.2:3b"}]}))
    s = verificar_saude_ollama(url="http://ollama:11434", modelo="llama3.1:8b", http=http)
    assert s == {"ollama": True, "modelo": "llama3.1:8b", "modelo_baixado": True}


def test_req_i05_ollama_sem_o_modelo():
    http = _ollama(lambda req: httpx.Response(200, json={"models": [{"name": "llama3.2:3b"}]}))
    s = verificar_saude_ollama(url="http://ollama:11434", modelo="llama3.1:8b", http=http)
    assert s == {"ollama": True, "modelo": "llama3.1:8b", "modelo_baixado": False}


@pytest.mark.parametrize("handler", [
    lambda req: (_ for _ in ()).throw(httpx.ConnectError("recusada")),
    lambda req: httpx.Response(500),
    lambda req: httpx.Response(200, content=b"<html>"),
])
def test_req_i05_ollama_fora(handler):
    s = verificar_saude_ollama(url="http://ollama:11434", modelo="llama3.1:8b", http=_ollama(handler))
    assert s["ollama"] is False and s["modelo_baixado"] is False


def test_req_i05_consulta_tags_com_timeout():
    capturadas = []

    def handler(req):
        capturadas.append(req)
        return httpx.Response(200, json={"models": []})

    verificar_saude_ollama(url="http://ollama:11434", modelo="m", http=_ollama(handler))
    assert str(capturadas[0].url) == "http://ollama:11434/api/tags"
    assert capturadas[0].extensions["timeout"]["read"] == 5.0


# --------------------------------------------------------------------------- REQ-I-06 configuração

def test_req_i06_criar_app_padrao(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACES_DIR", str(tmp_path))
    gravar_traco(tmp_path, "0123456789ab")
    c = TestClient(criar_app(verificar_saude=lambda: SAUDE_OK))
    assert c.get("/api/traco/0123456789ab").status_code == 200


# --------------------------------------------------------------------------- REQ-I-11 / REQ-I-16 (checagem do arquivo)

def test_req_i11_pagina_nao_insere_html_vindo_de_dado():
    html = INDEX.read_text(encoding="utf-8")
    for proibido in ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("]:
        assert proibido not in html, proibido


def test_req_i16_pagina_sem_recurso_externo():
    html = INDEX.read_text(encoding="utf-8")
    assert not re.search(r"https?://", html)
    assert "@import" not in html
