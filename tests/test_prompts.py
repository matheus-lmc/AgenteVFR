"""Testes do prompt e dos esquemas das ferramentas (REQ-A-12, REQ-A-02)."""

import re

from app import prompts


def test_req_a12_versao_e_prompt_atual():
    assert prompts.VERSAO_PROMPT == "v2"                                 # REQ-A-12 revisado
    assert prompts.PROMPT_SISTEMA is prompts.PROMPT_SISTEMA_V2
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
    textos = [prompts.PROMPT_SISTEMA_V1, prompts.PROMPT_SISTEMA_V2, prompts.LEMBRETE_FERRAMENTA]
    textos += [f["function"]["description"] for f in prompts.FERRAMENTAS]
    textos += [f["function"]["parameters"]["properties"]["icao"]["description"] for f in prompts.FERRAMENTAS]
    for texto in textos:
        assert not re.search(r"\bS[BDIJNSW][A-Z]{2}\b", texto), texto


def test_req_a12_lembrete_e_aviso():
    assert "buscar_metar" in prompts.LEMBRETE_FERRAMENTA
    assert prompts.AVISO == "Ferramenta acadêmica. Não substitui o briefing meteorológico oficial."


def test_req_a02_esquemas_das_ferramentas():
    assert [f["function"]["name"] for f in prompts.FERRAMENTAS] == ["buscar_metar", "buscar_taf"]
    for f in prompts.FERRAMENTAS:
        assert f["type"] == "function"
        params = f["function"]["parameters"]
        assert params["type"] == "object"
        assert params["required"] == ["icao"]
        assert params["properties"]["icao"]["type"] == "string"
        assert f["function"]["description"]
