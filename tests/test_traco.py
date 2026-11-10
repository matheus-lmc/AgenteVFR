"""Testes do traço (REQ-A-13)."""

import json
import re
from datetime import datetime, timezone

import pytest

from app.traco import TIPOS_PASSO, Traco

AGORA = datetime(2026, 11, 10, 14, 10, 5, tzinfo=timezone.utc)
CHAVES = {"id", "inicio", "pergunta", "modelo", "versao_prompt", "passos", "resposta", "duracao_ms"}


def novo(pasta, pergunta="dá pra ir VFR em Guarulhos?"):
    return Traco(pergunta, modelo="llama3.1:8b", versao_prompt="v1", relogio=lambda: AGORA, pasta=pasta)


def test_req_a13_id_12_hex_e_unico(tmp_path):
    ids = {novo(tmp_path).id for _ in range(50)}
    assert len(ids) == 50
    assert all(re.fullmatch(r"[0-9a-f]{12}", i) for i in ids)


def test_req_a13_nome_do_arquivo(tmp_path):
    t = novo(tmp_path)
    caminho = t.gravar({"veredito": "VMC"})
    assert caminho.parent == tmp_path
    assert caminho.name == f"20261110T141005Z_{t.id}.json"


def test_req_a13_conteudo(tmp_path):
    t = novo(tmp_path)
    t.passo("prefiltro", passou=True, regra=None, motivo=None)
    t.passo("modelo", mensagens=[{"role": "user", "content": "oi"}], prompt_eval_count=10)
    dados = json.loads(t.gravar({"veredito": "VMC"}).read_text(encoding="utf-8"))
    assert set(dados) == CHAVES
    assert dados["id"] == t.id
    assert dados["inicio"] == "2026-11-10T14:10:05Z"
    assert dados["pergunta"] == "dá pra ir VFR em Guarulhos?"
    assert dados["modelo"] == "llama3.1:8b"
    assert dados["versao_prompt"] == "v1"
    assert dados["resposta"] == {"veredito": "VMC"}
    assert isinstance(dados["duracao_ms"], int) and dados["duracao_ms"] >= 0
    assert [p["tipo"] for p in dados["passos"]] == ["prefiltro", "modelo"]
    assert all(isinstance(p["t_ms"], int) for p in dados["passos"])
    assert dados["passos"][1]["prompt_eval_count"] == 10


def test_req_a13_tipo_de_passo_invalido(tmp_path):
    with pytest.raises(ValueError):
        novo(tmp_path).passo("palpite")


def test_req_a13_tipos_permitidos():
    assert TIPOS_PASSO == {"prefiltro", "modelo", "ferramenta", "harness", "verificador", "erro"}


def test_req_a13_utf8_legivel_e_objetos_nao_json(tmp_path):
    t = novo(tmp_path, pergunta="Congonhas está em condição visual?")
    t.passo("erro", quando=AGORA, objeto=object())
    texto = t.gravar(None).read_text(encoding="utf-8")
    assert "Congonhas está" in texto
    assert json.loads(texto)["passos"][0]["quando"].startswith("2026-11-10")


def test_req_a13_cria_pasta(tmp_path):
    pasta = tmp_path / "a" / "b"
    assert novo(pasta).gravar(None).exists()


def test_req_a13_pasta_do_ambiente(tmp_path, monkeypatch):
    monkeypatch.setenv("TRACES_DIR", str(tmp_path / "do_ambiente"))
    t = Traco("p", modelo="m", versao_prompt="v1", relogio=lambda: AGORA)
    assert t.gravar(None).parent == tmp_path / "do_ambiente"
