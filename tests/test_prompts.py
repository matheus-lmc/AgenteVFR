"""Testes do prompt e dos esquemas das ferramentas (REQ-A-12, REQ-A-02)."""

import re

from app import prompts


def test_req_a12_versao_e_prompt_atual():
    assert prompts.VERSAO_PROMPT == "v4"                                 # REQ-A-16
    assert prompts.PROMPT_SISTEMA is prompts.PROMPT_SISTEMA_V4
    assert prompts.LEMBRETE_FERRAMENTA is prompts.LEMBRETE_FERRAMENTA_V4
    assert len(prompts.PROMPT_SISTEMA) > 200
    assert len(prompts.PROMPT_SISTEMA_V1) > 200                          # v1 preservado para comparação


def test_req_a12_v2_pede_para_conferir_a_estacao():
    assert "nome_estacao" in prompts.PROMPT_SISTEMA_V2
    assert "nome_estacao" not in prompts.PROMPT_SISTEMA_V1
    assert prompts.PROMPT_SISTEMA_V2.startswith(prompts.PROMPT_SISTEMA_V1.split("Como trabalhar:")[0])


def test_req_a12_instrucoes_obrigatorias():
    p = prompts.PROMPT_SISTEMA.lower()
    for termo in ["buscar_metar", "veredito", "teto", "visibilidade", "metar", "português",
                  "4 frases", "redemet", "invente"]:
        assert termo in p, termo


def test_req_a12_sem_tabela_de_icao():
    textos = [prompts.PROMPT_SISTEMA_V1, prompts.PROMPT_SISTEMA_V2, prompts.PROMPT_SISTEMA_V3,
              prompts.PROMPT_SISTEMA_V4, prompts.LEMBRETE_FERRAMENTA_V1, prompts.LEMBRETE_FERRAMENTA_V4]
    textos += [f["function"]["description"] for f in prompts.FERRAMENTAS]
    textos += [p["description"] for f in prompts.FERRAMENTAS for p in f["function"]["parameters"]["properties"].values()]
    for texto in textos:
        assert not re.search(r"\bS[BDIJNSW][A-Z]{2}\b", texto), texto


def test_req_a12_lembrete_e_aviso():
    assert "buscar_metar" in prompts.LEMBRETE_FERRAMENTA
    assert prompts.AVISO == "Ferramenta acadêmica. Não substitui o briefing meteorológico oficial."


def test_req_a02_esquemas_das_ferramentas():
    assert [f["function"]["name"] for f in prompts.FERRAMENTAS_V3] == ["buscar_metar", "avaliar_janela"]  # D8 do módulo 05
    assert prompts.FERRAMENTAS is prompts.FERRAMENTAS_V4
    assert [f["function"]["name"] for f in prompts.FERRAMENTAS] == ["buscar_metar", "avaliar_janela", "conversar"]
    conversar = prompts.FERRAMENTAS[2]["function"]["parameters"]
    assert conversar["required"] == ["mensagem"] and conversar["properties"]["mensagem"]["type"] == "string"
    for f in prompts.FERRAMENTAS_V3:
        assert f["type"] == "function"
        params = f["function"]["parameters"]
        assert params["type"] == "object"
        assert params["required"] == ["icao"]
        assert params["properties"]["icao"]["type"] == "string"
        assert f["function"]["description"]


def test_req_j10_prompt_v3():
    v3 = prompts.PROMPT_SISTEMA_V3
    assert "avaliar_janela" in v3 and "nome_estacao" in v3
    assert "previsão" in v3.lower() and "UTC" in v3
    assert "avaliar_janela" not in prompts.PROMPT_SISTEMA_V2


def test_req_a16_prompt_v4_conversa_sem_ferramenta():
    v3, v4 = prompts.PROMPT_SISTEMA_V3, prompts.PROMPT_SISTEMA_V4
    assert "Chame conversar" in v4 and "NÃO escolha um aeródromo" in v4
    assert "conversar" not in v3
    assert v4.split("1. Identifique")[0] == v3.split("1. Identifique")[0]   # mesmo cabeçalho
    assert "buscar_metar" in prompts.LEMBRETE_FERRAMENTA_V4 and "conversar" in prompts.LEMBRETE_FERRAMENTA_V4
