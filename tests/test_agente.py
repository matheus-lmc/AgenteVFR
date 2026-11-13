"""Testes do loop do agente, derivados de specs/03-agente/requisitos.md.

O Ollama é substituído por um modelo roteirizado e as ferramentas por buscas falsas.
O teste com o Ollama real está marcado com @pytest.mark.ollama (rodar com: pytest -m ollama).
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app import harness, harness_taf, prompts
from app.agente import Agente, ClienteOllama, ErroModelo
from app.ferramentas import ResultadoBusca

UTC = timezone.utc
FIXTURE_METAR = json.loads((Path(__file__).parent / "fixtures" / "awc" / "metar_SBGR.json").read_text())
AGORA = datetime.fromtimestamp(FIXTURE_METAR[0]["obsTime"], UTC) + timedelta(minutes=10)
CHAVES_RESPOSTA = {"id_traco", "veredito", "motivo", "avaliacoes", "janelas", "explicacao", "origem_explicacao",
                   "bloqueio", "aviso", "duracao_ms"}


# --------------------------------------------------------------------------- METARs de teste

def metar(icao: str, corpo: str, minutos_atras: int = 10) -> str:
    obs = AGORA - timedelta(minutes=minutos_atras)
    return f"METAR {icao} {obs:%d%H%M}Z {corpo}"


METAR_SBGR = FIXTURE_METAR[0]["rawOb"]                                   # real, VMC
METAR_SBKP = metar("SBKP", "32005KT CAVOK 28/12 Q1015")                  # VMC
METAR_SBSP_IMC = metar("SBSP", "15010KT 4000 BR BKN008 18/17 Q1020")     # IMC
METAR_SBSP_VMC = metar("SBSP", "15010KT 9999 FEW030 18/17 Q1020")        # VMC
TAF_SBGR = "TAF SBGR 101200Z 1012/1118 08005KT 9999 BKN025"


def busca(icao: str, status: str = "ok", texto: str | None = None, tipo: str = "metar",
          nome: str | None = None) -> ResultadoBusca:
    resposta = [{"rawOb" if tipo == "metar" else "rawTAF": texto, "fltCat": "MVFR",
                 "receiptTime": "2026-11-10T13:56:00Z", **({"name": nome} if nome else {})}] if texto else None
    return ResultadoBusca(icao=icao, tipo=tipo, status=status, texto_bruto=texto, resposta_api=resposta,
                          url=f"https://aviationweather.gov/api/data/{tipo}?ids={icao}&format=json",
                          http_status=200 if texto else None, de_cache=False, tentativas=1,
                          buscado_em="2026-11-10T14:10:00Z", duracao_ms=5, erro=None)


class BuscasFalsas:
    """Ferramentas falsas. Cada ICAO aponta para um resultado ou uma lista (consumida em ordem)."""

    def __init__(self, metars: dict | None = None, tafs: dict | None = None):
        self.metars = metars or {}
        self.tafs = tafs or {}
        self.chamadas: list[tuple[str, str]] = []

    def _resolver(self, tabela, icao, tipo):
        self.chamadas.append((tipo, icao))
        valor = tabela.get(icao)
        if isinstance(valor, list):
            valor = valor.pop(0) if len(valor) > 1 else valor[0]
        if valor is not None:
            return valor
        if len(icao) != 4 or not icao.isalpha():
            return busca(icao, "icao_invalido", tipo=tipo)
        return busca(icao, "sem_dado", tipo=tipo)

    def metar(self, icao):
        return self._resolver(self.metars, icao, "metar")

    def taf(self, icao):
        return self._resolver(self.tafs, icao, "taf")


PADRAO_METARS = {
    "SBGR": busca("SBGR", texto=METAR_SBGR, nome="Sao Paulo Intl, PR, BR"),
    "SBKP": busca("SBKP", texto=METAR_SBKP, nome="Campinas/Viracopos Arpt, SP, BR"),
    "SBSP": busca("SBSP", texto=METAR_SBSP_IMC, nome="Sao Paulo/Congonhas, SP, BR"),
    "KMIA": busca("KMIA", "fora_do_escopo"),
}


# --------------------------------------------------------------------------- modelo roteirizado

def chamada(nome: str, **argumentos) -> dict:
    return {"function": {"name": nome, "arguments": argumentos}}


def ferramentas_(*chamadas) -> dict:
    return {"message": {"role": "assistant", "content": "", "tool_calls": list(chamadas)},
            "prompt_eval_count": 300, "eval_count": 20, "done": True}


def texto(t: str) -> dict:
    return {"message": {"role": "assistant", "content": t}, "prompt_eval_count": 500, "eval_count": 60,
            "done": True}


class ModeloRoteirizado:
    modelo = "roteirizado:1b"

    def __init__(self, *respostas):
        self.respostas = list(respostas)
        self.recebidas: list[tuple[list[dict], list[dict]]] = []

    def conversar(self, mensagens, ferramentas):
        self.recebidas.append((copy.deepcopy(mensagens), ferramentas))
        if not self.respostas:
            raise AssertionError("o modelo foi chamado mais vezes que o roteiro")
        r = self.respostas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def rodar(tmp_path):
    """rodar(pergunta, *roteiro, metars=..., tafs=...) -> (resposta, modelo, buscas, traco_dict)"""

    def _rodar(pergunta, *roteiro, metars=None, tafs=None):
        modelo = ModeloRoteirizado(*roteiro)
        buscas = BuscasFalsas(copy.deepcopy(metars if metars is not None else PADRAO_METARS),
                              tafs if tafs is not None else {"SBGR": busca("SBGR", texto=TAF_SBGR, tipo="taf")})
        agente = Agente(ollama=modelo, buscar_metar=buscas.metar, buscar_taf=buscas.taf,
                        relogio=lambda: AGORA, pasta_traces=tmp_path)
        resposta = agente.perguntar(pergunta)
        return resposta, modelo, buscas, ler_traco(tmp_path, resposta.id_traco)

    return _rodar


def ler_traco(pasta: Path, id_traco: str) -> dict:
    arquivos = list(pasta.glob(f"*_{id_traco}.json"))
    assert len(arquivos) == 1, arquivos
    return json.loads(arquivos[0].read_text(encoding="utf-8"))


def passos(traco: dict, tipo: str) -> list[dict]:
    return [p for p in traco["passos"] if p["tipo"] == tipo]


def mensagens_tool(modelo: ModeloRoteirizado, indice_chamada: int) -> list[dict]:
    return [m for m in modelo.recebidas[indice_chamada][0] if m["role"] == "tool"]


PERGUNTA = "Dá pra ir VFR em Guarulhos agora?"
COERENTE_SBGR = "Condições VMC em SBGR, dentro dos mínimos VFR."


# --------------------------------------------------------------------------- REQ-A-01 pré-filtro

def test_req_a01_prefiltro_recusa_sem_chamar_o_modelo(rodar):
    r, modelo, buscas, traco = rodar("Posso decolar mesmo assim?")
    assert r.veredito == "RECUSA"
    assert r.motivo == harness.MOTIVOS_PERGUNTA["pressao_operacional"]
    assert modelo.recebidas == [] and buscas.chamadas == []
    p = passos(traco, "prefiltro")[0]
    assert p["passou"] is False and p["regra"] == "pressao_operacional"


@pytest.mark.parametrize("pergunta", ["", "   ", "a" * 501])
def test_req_a01_pergunta_invalida(rodar, pergunta):
    r, modelo, _, traco = rodar(pergunta)
    assert r.veredito == "RECUSA"
    assert modelo.recebidas == []
    assert passos(traco, "prefiltro")[0]["regra"] == "pergunta_invalida"


def test_req_a01_pergunta_normal_passa_no_prefiltro(rodar):
    _, _, _, traco = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    assert passos(traco, "prefiltro")[0]["passou"] is True


# --------------------------------------------------------------------------- REQ-A-02 ferramentas

def test_req_a02_ferramentas_enviadas(rodar):
    _, modelo, _, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    assert [f["function"]["name"] for f in modelo.recebidas[0][1]] == ["buscar_metar", "avaliar_janela", "conversar"]


def test_req_a02_ferramenta_desconhecida(rodar):
    r, modelo, _, _ = rodar(PERGUNTA, ferramentas_(chamada("autorizar_decolagem", icao="SBGR")),
                            ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    assert "ferramenta desconhecida" in mensagens_tool(modelo, 1)[0]["content"]
    assert r.veredito == "VMC"


def test_req_a02_ferramenta_desconhecida_conta_iteracao(rodar):
    r, _, _, _ = rodar(PERGUNTA, ferramentas_(*[chamada("x", icao="SBGR")] * 5),
                       ferramentas_(chamada("buscar_metar", icao="SBGR")))
    assert r.veredito == "RECUSA"
    assert "limite" in r.motivo.lower()


@pytest.mark.parametrize("argumentos", [{}, {"icao": 123}, {"aeroporto": "SBGR"}])
def test_req_a02_argumento_invalido(rodar, argumentos):
    _, modelo, buscas, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", **argumentos)),
                                 ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    assert "icao" in mensagens_tool(modelo, 1)[0]["content"]
    assert buscas.chamadas == [("metar", "SBGR")]


def test_req_a02_argumentos_em_texto_json(rodar):
    bruto = {"function": {"name": "buscar_metar", "arguments": '{"icao": "SBGR"}'}}
    r, _, _, _ = rodar(PERGUNTA, ferramentas_(bruto), texto(COERENTE_SBGR))
    assert [a["icao"] for a in r.avaliacoes] == ["SBGR"]


# --------------------------------------------------------------------------- REQ-A-03 janela

def test_req_a03_resultado_do_metar_e_o_resumo_do_harness(rodar):
    _, modelo, _, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    tool = mensagens_tool(modelo, 1)[0]
    assert tool["tool_name"] == "buscar_metar"
    esperado = {**harness.avaliar_metar(METAR_SBGR, "SBGR", AGORA).resumo.para_dict(),
                "nome_estacao": "Sao Paulo Intl, PR, BR"}                       # REQ-A-03 revisado
    assert json.loads(tool["content"]) == esperado


def test_req_a03_json_da_api_nunca_entra_na_janela(rodar):
    _, modelo, _, _ = rodar(PERGUNTA,
                            ferramentas_(chamada("buscar_metar", icao="SBGR"), chamada("avaliar_janela", icao="SBGR")),
                            texto(COERENTE_SBGR))
    for mensagens, _ in modelo.recebidas:
        janela = json.dumps(mensagens, ensure_ascii=False)
        for proibido in ["resposta_api", "fltCat", "receiptTime"]:
            assert proibido not in janela


def test_req_j09_janela_do_taf_e_o_resumo_do_harness(rodar):
    r, modelo, _, _ = rodar(PERGUNTA,
                            ferramentas_(chamada("buscar_metar", icao="SBGR"), chamada("avaliar_janela", icao="SBGR")),
                            texto(COERENTE_SBGR))
    esperado = harness_taf.avaliar_taf(TAF_SBGR, "SBGR", AGORA).resumo.para_dict()
    assert json.loads(mensagens_tool(modelo, 1)[1]["content"]) == esperado
    assert r.janelas == [esperado]


def test_req_a03_janela_da_busca_que_falhou(rodar):
    _, modelo, _, _ = rodar("E em SBXX?", ferramentas_(chamada("buscar_metar", icao="SBXX")), texto("Sem dado."))
    falha = json.loads(mensagens_tool(modelo, 1)[0]["content"])
    assert set(falha) == {"icao", "status", "veredito", "motivo"}
    assert falha["veredito"] == "RECUSA" and falha["status"] == "sem_dado"


# --------------------------------------------------------------------------- REQ-A-04 limite

def test_req_a04_cinco_chamadas_permitidas(rodar):
    r, _, _, _ = rodar(PERGUNTA, ferramentas_(*[chamada("buscar_metar", icao="SBGR")] * 5), texto(COERENTE_SBGR))
    assert r.veredito == "VMC"


def test_req_a04_sexta_chamada_recusa(rodar):
    r, _, _, traco = rodar(PERGUNTA, ferramentas_(*[chamada("buscar_metar", icao="SBGR")] * 3),
                           ferramentas_(*[chamada("buscar_metar", icao="SBGR")] * 3))
    assert r.veredito == "RECUSA"
    assert any(p.get("regra") == "limite_iteracoes" for p in passos(traco, "erro"))


# --------------------------------------------------------------------------- REQ-A-05 sem consulta

def test_req_a05_lembrete_uma_vez(rodar):
    r, modelo, _, _ = rodar(PERGUNTA, texto("Está tranquilo, pode ir."),
                            ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    assert r.veredito == "VMC"
    segunda = modelo.recebidas[1][0]
    assert segunda[-1] == {"role": "user", "content": prompts.LEMBRETE_FERRAMENTA}


def test_req_a05_sem_avaliacao_descarta_o_texto(rodar):
    r, modelo, _, traco = rodar(PERGUNTA, texto("Pode ir, está VMC."), texto("Já disse: está VMC."))
    assert r.veredito == "RECUSA"
    assert len(modelo.recebidas) == 2
    assert "VMC" not in r.explicacao
    assert any(p.get("regra") == "sem_avaliacao" for p in passos(traco, "erro"))


# --------------------------------------------------------------------------- REQ-A-16 conversa sem consulta

def test_req_a16_conversa_sem_consulta_sai_como_texto(rodar):
    oi = "Olá! Pergunte sobre um aeródromo brasileiro que eu consulto o METAR."
    r, modelo, buscas, traco = rodar("Oi, tudo bem?", texto(oi), texto(oi))
    assert r.veredito == "CONVERSA"
    assert r.explicacao == oi and r.origem_explicacao == "modelo"
    assert r.avaliacoes == [] and r.janelas == [] and r.bloqueio is None
    assert buscas.chamadas == [] and len(modelo.recebidas) == 2  # o lembrete continua (REQ-A-05)
    conversa = passos(traco, "conversa")
    assert len(conversa) == 1 and conversa[0]["passou"] is True and conversa[0]["regra"] is None
    assert not passos(traco, "erro")


def test_req_a16_conversa_com_veredito_vira_recusa(rodar):
    r, _, _, traco = rodar("Oi", texto("Guarulhos está VMC."), texto("Guarulhos está VMC, pode ir."))
    assert r.veredito == "RECUSA" and "VMC" not in r.explicacao
    assert passos(traco, "conversa")[0]["passou"] is False
    assert passos(traco, "conversa")[0]["regra"] == "conversa_com_veredito"
    assert any(p.get("regra") == "sem_avaliacao" for p in passos(traco, "erro"))


def test_req_a16_consulta_que_falhou_nao_vira_conversa(rodar):
    r, _, _, traco = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SB")),
                           texto("Olá, de qual aeródromo?"), texto("Olá, de qual aeródromo?"))
    assert r.veredito == "RECUSA"
    assert not passos(traco, "conversa")


def test_req_a16_ferramenta_conversar_sai_como_texto(rodar):
    oi = "Olá! Qual aeródromo você quer consultar?"
    r, modelo, buscas, traco = rodar("Oi, tudo bem?", ferramentas_(chamada("conversar", mensagem=oi)))
    assert r.veredito == "CONVERSA" and r.explicacao == oi and r.origem_explicacao == "modelo"
    assert buscas.chamadas == [] and len(modelo.recebidas) == 1   # sem lembrete nem segunda chamada
    assert passos(traco, "ferramenta")[0]["nome"] == "conversar"
    assert passos(traco, "conversa")[0]["passou"] is True


def test_req_a16_ferramenta_conversar_passa_pela_trava(rodar):
    r, _, buscas, traco = rodar("Oi", ferramentas_(chamada("conversar", mensagem="SBGR está VMC, pode ir.")))
    assert r.veredito == "RECUSA" and "VMC" not in r.explicacao
    assert passos(traco, "conversa")[0]["regra"] == "conversa_cita_aerodromo"
    assert buscas.chamadas == []


@pytest.mark.parametrize("argumentos", [{}, {"mensagem": 3}, {"mensagem": ""}])
def test_req_a16_ferramenta_conversar_sem_mensagem_vira_recusa(rodar, argumentos):
    r, _, _, traco = rodar("Oi", ferramentas_(chamada("conversar", **argumentos)))
    assert r.veredito == "RECUSA"
    assert passos(traco, "conversa")[0]["regra"] == "conversa_vazia"


def test_req_a16_conversar_fora_do_tema_descarta_a_mensagem(rodar):
    r, _, buscas, traco = rodar("Quanto é a área de um círculo de raio 2?",
                                ferramentas_(chamada("conversar", mensagem="A área é 4π.")))
    assert r.veredito == "RECUSA" and r.motivo == harness.MOTIVOS_PERGUNTA["fora_do_tema"]
    assert "4π" not in r.explicacao and r.origem_explicacao == "texto_modelo"
    assert passos(traco, "conversa")[0] == {**passos(traco, "conversa")[0], "passou": False, "regra": "fora_do_tema"}
    assert buscas.chamadas == []


def test_req_a16_texto_sem_ferramenta_fora_do_tema_vira_recusa(rodar):
    r, _, _, traco = rodar("Quanto é 15 vezes 23?", texto("345."), texto("É 345."))
    assert r.veredito == "RECUSA" and "345" not in r.explicacao
    assert passos(traco, "conversa")[0]["regra"] == "fora_do_tema"


def test_req_a16_prefiltro_fora_do_tema_nem_chama_o_modelo(rodar):
    r, modelo, _, traco = rodar("Calcule a integral de x² de 0 a 2")
    assert r.veredito == "RECUSA" and modelo.recebidas == []
    assert passos(traco, "prefiltro")[0]["regra"] == "fora_do_tema"


def test_req_a16_conversar_depois_de_consulta_e_ignorada(rodar):
    r, modelo, _, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")),
                            ferramentas_(chamada("conversar", mensagem="Olá!")), texto(COERENTE_SBGR))
    assert r.veredito == "VMC"
    assert "conversar só vale sozinha" in mensagens_tool(modelo, 2)[-1]["content"]


def test_req_a16_conversar_junto_com_consulta_e_ignorada(rodar):
    r, modelo, _, _ = rodar(PERGUNTA, ferramentas_(chamada("conversar", mensagem="Olá!"),
                                                   chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    assert r.veredito == "VMC"
    assert "conversar só vale sozinha" in mensagens_tool(modelo, 1)[0]["content"]


# --------------------------------------------------------------------------- REQ-A-06 falha do modelo

def test_req_a06_erro_modelo_vira_recusa(rodar):
    r, _, _, traco = rodar(PERGUNTA, ErroModelo("conexão recusada"))
    assert r.veredito == "RECUSA"
    erros = passos(traco, "erro")
    assert erros and erros[0]["regra"] == "erro_modelo" and "conexão recusada" in erros[0]["mensagem"]


def test_req_a06_erro_modelo_no_meio_do_loop(rodar):
    r, _, _, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")), ErroModelo("tempo esgotado"))
    assert r.veredito == "RECUSA"


def _cliente(handler, **kwargs):
    return ClienteOllama(http=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)


@pytest.mark.parametrize("handler", [
    lambda req: (_ for _ in ()).throw(httpx.ConnectError("recusada")),
    lambda req: httpx.Response(404, json={"error": "model 'llama3.1:8b' not found"}),
    lambda req: httpx.Response(200, content=b"<html>"),
    lambda req: httpx.Response(200, json={"done": True}),
])
def test_req_a06_cliente_ollama_falhas(handler):
    with pytest.raises(ErroModelo):
        _cliente(handler).conversar([{"role": "user", "content": "oi"}], [])


def test_req_a06_mensagem_de_modelo_nao_baixado():
    c = _cliente(lambda req: httpx.Response(404, json={"error": "model 'llama3.1:8b' not found"}))
    with pytest.raises(ErroModelo, match="not found"):
        c.conversar([], [])


def test_req_a13_traco_gravado_em_excecao_inesperada(tmp_path):
    def quebra(icao):
        raise RuntimeError("bug")

    agente = Agente(ollama=ModeloRoteirizado(ferramentas_(chamada("buscar_metar", icao="SBGR"))),
                    buscar_metar=quebra, buscar_taf=quebra, relogio=lambda: AGORA, pasta_traces=tmp_path)
    with pytest.raises(RuntimeError):
        agente.perguntar(PERGUNTA)
    arquivos = list(tmp_path.glob("*.json"))
    assert len(arquivos) == 1
    traco = json.loads(arquivos[0].read_text(encoding="utf-8"))
    assert any("bug" in p.get("mensagem", "") for p in passos(traco, "erro"))


# --------------------------------------------------------------------------- REQ-A-07 veredito geral

def test_req_a07_vmc_e_vmc(rodar):
    r, _, _, _ = rodar("Guarulhos e Campinas?", ferramentas_(chamada("buscar_metar", icao="SBGR"),
                                                           chamada("buscar_metar", icao="SBKP")),
                       texto("Condições VMC em SBGR e SBKP."))
    assert r.veredito == "VMC"
    assert [a["icao"] for a in r.avaliacoes] == ["SBGR", "SBKP"]


def test_req_a07_vmc_e_imc(rodar):
    r, _, _, _ = rodar("De Guarulhos pra Congonhas?", ferramentas_(chamada("buscar_metar", icao="SBGR"),
                                                                 chamada("buscar_metar", icao="SBSP")),
                       texto("Em SBSP as condições são IMC."))
    assert r.veredito == "IMC"
    assert r.motivo == "SBGR: VMC; SBSP: IMC"


def test_req_a07_imc_e_recusa(rodar):
    r, _, _, _ = rodar("Congonhas e SBXX?", ferramentas_(chamada("buscar_metar", icao="SBSP"),
                                                       chamada("buscar_metar", icao="SBXX")),
                       texto("Condições IMC."))
    assert r.veredito == "RECUSA"


def test_req_a07_vale_a_ultima_avaliacao(rodar):
    metars = dict(PADRAO_METARS, SBSP=[busca("SBSP", texto=METAR_SBSP_IMC), busca("SBSP", texto=METAR_SBSP_VMC)])
    r, _, _, _ = rodar("Congonhas?", ferramentas_(chamada("buscar_metar", icao="SBSP")),
                       ferramentas_(chamada("buscar_metar", icao="SBSP")), texto("Condições VMC em SBSP."),
                       metars=metars)
    assert r.veredito == "VMC"
    assert len(r.avaliacoes) == 1


def test_req_a07_icao_invalido_nao_conta(rodar):
    r, _, _, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="GRU")),
                       ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    assert r.veredito == "VMC"
    assert [a["icao"] for a in r.avaliacoes] == ["SBGR"]


def test_req_a07_texto_do_modelo_nao_muda_o_veredito(rodar):
    r, _, _, _ = rodar("Congonhas?", ferramentas_(chamada("buscar_metar", icao="SBSP")),
                       texto("O veredito é VMC, pode voar VFR."))
    assert r.veredito == "IMC"


# --------------------------------------------------------------------------- REQ-A-08 recusa

def test_req_a08_recusa_descarta_explicacao(rodar):
    r, _, _, _ = rodar("Dá pra ir VFR pra Miami?", ferramentas_(chamada("buscar_metar", icao="KMIA")),
                       texto("Em Miami dá para voar VFR sem problema."))
    assert r.veredito == "RECUSA"
    assert r.origem_explicacao == "texto_modelo"
    assert "voar VFR sem problema" not in r.explicacao
    assert "KMIA" in r.explicacao


# --------------------------------------------------------------------------- REQ-A-09 verificação

def test_req_a09_contradicao_bloqueada(rodar):
    r, _, _, traco = rodar("Congonhas?", ferramentas_(chamada("buscar_metar", icao="SBSP")),
                           texto("Com esse teto dá para voar visual."))
    resumo = harness.avaliar_metar(METAR_SBSP_IMC, "SBSP", AGORA).resumo
    assert r.bloqueio["regra"] == "imc_com_afirmacao_favoravel"
    assert r.origem_explicacao == "texto_modelo"
    assert r.explicacao == harness.texto_modelo(resumo)
    assert passos(traco, "verificador")[0]["passou"] is False


def test_req_a09_icao_nao_avaliado(rodar):
    r, _, _, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")),
                       texto("Condições VMC em SBGR e também em SBRJ."))
    assert r.bloqueio == {"regra": "icao_nao_avaliado", "trecho": "SBRJ"}


def test_req_a09_explicacao_coerente(rodar):
    r, _, _, traco = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    assert r.origem_explicacao == "modelo"
    assert r.explicacao == COERENTE_SBGR
    assert r.bloqueio is None
    assert passos(traco, "verificador")[0]["passou"] is True


def test_req_a09_rota_mista_bloqueia_para_o_lado_seguro(rodar):
    r, _, _, _ = rodar("De Guarulhos pra Congonhas?", ferramentas_(chamada("buscar_metar", icao="SBGR"),
                                                                 chamada("buscar_metar", icao="SBSP")),
                       texto("Guarulhos está VMC, mas Congonhas está IMC."))
    assert r.veredito == "IMC"
    assert r.bloqueio is not None
    assert "SBGR" in r.explicacao and "SBSP" in r.explicacao


# --------------------------------------------------------------------------- REQ-A-10 resposta

def test_req_a10_resposta(rodar):
    r, _, _, traco = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    d = r.para_dict()
    assert set(d) == CHAVES_RESPOSTA
    assert d["aviso"] == prompts.AVISO
    assert d["veredito"] == "VMC"
    assert d["id_traco"] == traco["id"]
    assert isinstance(d["duracao_ms"], int)
    assert d["avaliacoes"][0] == {**harness.avaliar_metar(METAR_SBGR, "SBGR", AGORA).resumo.para_dict(),
                                  "nome_estacao": "Sao Paulo Intl, PR, BR"}   # REQ-A-10 revisado


def test_req_a10_recusa_cita_briefing_oficial(rodar):
    r, _, _, _ = rodar("Posso decolar mesmo assim?")
    assert "REDEMET" in r.explicacao


# --------------------------------------------------------------------------- REQ-A-11 chamada ao Ollama

def _capturar(**kwargs):
    capturadas = []

    def handler(req):
        capturadas.append(req)
        return httpx.Response(200, json=texto("ok"))

    return _cliente(handler, **kwargs), capturadas


def test_req_a11_corpo_da_requisicao(monkeypatch):
    for var in ["OLLAMA_URL", "OLLAMA_MODEL", "OLLAMA_TEMPERATURA", "OLLAMA_NUM_THREAD", "OLLAMA_TIMEOUT_S"]:
        monkeypatch.delenv(var, raising=False)
    c, capturadas = _capturar()
    mensagens = [{"role": "user", "content": "oi"}]
    c.conversar(mensagens, prompts.FERRAMENTAS)
    req = capturadas[0]
    assert str(req.url) == "http://localhost:11434/api/chat"
    corpo = json.loads(req.content)
    assert corpo["model"] == "llama3.1:8b"
    assert corpo["stream"] is False
    assert corpo["options"] == {"temperature": 0.1, "seed": 42, "num_thread": 4}
    assert corpo["tools"] == prompts.FERRAMENTAS
    assert corpo["messages"] == mensagens
    assert req.extensions["timeout"]["read"] == 300.0


def test_req_a11_configuracao_pelo_ambiente(monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://ollama:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2:3b")
    monkeypatch.setenv("OLLAMA_TEMPERATURA", "0")
    monkeypatch.setenv("OLLAMA_NUM_THREAD", "3")
    monkeypatch.setenv("OLLAMA_TIMEOUT_S", "60")
    c, capturadas = _capturar()
    c.conversar([], [])
    corpo = json.loads(capturadas[0].content)
    assert str(capturadas[0].url) == "http://ollama:11434/api/chat"
    assert c.modelo == corpo["model"] == "llama3.2:3b"
    assert corpo["options"]["temperature"] == 0.0
    assert corpo["options"]["num_thread"] == 3
    assert capturadas[0].extensions["timeout"]["read"] == 60.0


def test_req_a11_num_thread_por_parametro(monkeypatch):
    monkeypatch.setenv("OLLAMA_NUM_THREAD", "8")
    c, capturadas = _capturar(num_thread=2)
    c.conversar([], [])
    assert json.loads(capturadas[0].content)["options"]["num_thread"] == 2


def test_req_a11_resposta_devolvida_inteira():
    c, _ = _capturar()
    assert c.conversar([], [])["message"]["content"] == "ok"


# --------------------------------------------------------------------------- REQ-A-12 prompt no loop

def test_req_a12_prompt_e_versao_no_traco(rodar):
    _, modelo, _, traco = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    primeira = modelo.recebidas[0][0]
    assert primeira[0] == {"role": "system", "content": prompts.PROMPT_SISTEMA}
    assert primeira[1] == {"role": "user", "content": PERGUNTA}
    assert traco["versao_prompt"] == prompts.VERSAO_PROMPT
    assert traco["modelo"] == "roteirizado:1b"


# --------------------------------------------------------------------------- REQ-A-13 traço do loop

def test_req_a13_passos_do_loop(rodar):
    r, _, _, traco = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR))
    assert [p["tipo"] for p in traco["passos"]] == ["prefiltro", "modelo", "ferramenta", "harness", "modelo",
                                                    "verificador"]
    modelo = passos(traco, "modelo")[0]
    for chave in ["mensagens", "resposta", "prompt_eval_count", "eval_count", "tokens_estimados", "duracao_ms"]:
        assert chave in modelo, chave
    assert modelo["prompt_eval_count"] == 300
    ferramenta = passos(traco, "ferramenta")[0]
    assert ferramenta["nome"] == "buscar_metar"
    assert ferramenta["argumentos"] == {"icao": "SBGR"}
    assert ferramenta["resultado"]["resposta_api"][0]["fltCat"] == "MVFR"   # bruto fica no traço
    assert "fltCat" not in json.dumps(ferramenta["janela"])                   # ...mas não na janela
    assert passos(traco, "harness")[0]["veredito"] == "VMC"
    assert passos(traco, "harness")[0]["nome_estacao"] == "Sao Paulo Intl, PR, BR"
    assert traco["resposta"] == r.para_dict()


def test_req_a13_traco_tambem_na_recusa(rodar):
    r, _, _, traco = rodar("Posso decolar mesmo assim?")
    assert traco["resposta"]["veredito"] == "RECUSA"
    assert traco["id"] == r.id_traco


# --------------------------------------------------------------------------- REQ-A-14 Ollama real

@pytest.mark.ollama
def test_req_a14_ollama_real(tmp_path):
    r = Agente(pasta_traces=tmp_path).perguntar(PERGUNTA)
    assert r.veredito in {"VMC", "IMC", "RECUSA"}
    assert "SBGR" in [a["icao"] for a in r.avaliacoes], r


# --------------------------------------------------------------------------- REQ-A-15 nome da estação (H7)

def _com_resposta(icao, texto, resposta_api):
    b = busca(icao, texto=texto)
    return ResultadoBusca(**{**b.para_dict(), "resposta_api": resposta_api})


@pytest.mark.parametrize("resposta_api", [
    [{"rawOb": METAR_SBGR}],
    [{"rawOb": METAR_SBGR, "name": ""}],
    [{"rawOb": METAR_SBGR, "name": "   "}],
    [{"rawOb": METAR_SBGR, "name": 123}],
    ["nao e objeto"],
    [],
    {"rawOb": METAR_SBGR},
])
def test_req_a15_nome_ausente_vira_null(rodar, resposta_api):
    metars = dict(PADRAO_METARS, SBGR=_com_resposta("SBGR", METAR_SBGR, resposta_api))
    r, modelo, _, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR),
                            metars=metars)
    assert r.avaliacoes[0]["nome_estacao"] is None
    assert json.loads(mensagens_tool(modelo, 1)[0]["content"])["nome_estacao"] is None


def test_req_a15_nome_com_espacos_e_aparado(rodar):
    metars = dict(PADRAO_METARS, SBGR=busca("SBGR", texto=METAR_SBGR, nome="  Sao Paulo Intl, PR, BR "))
    r, _, _, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")), texto(COERENTE_SBGR),
                       metars=metars)
    assert r.avaliacoes[0]["nome_estacao"] == "Sao Paulo Intl, PR, BR"


def test_req_a15_nome_nao_muda_o_veredito(rodar):
    metars = dict(PADRAO_METARS, SBSP=busca("SBSP", texto=METAR_SBSP_IMC, nome="Rio de Janeiro/Dumont Arpt, RJ, BR"))
    r, _, _, _ = rodar("Congonhas?", ferramentas_(chamada("buscar_metar", icao="SBSP")),
                       texto("Em SBSP as condições são IMC."), metars=metars)
    assert r.veredito == "IMC"
    assert r.avaliacoes[0]["veredito"] == "IMC"


def test_req_a15_busca_que_falhou_tem_nome_null(rodar):
    r, _, _, _ = rodar("E em SBXX?", ferramentas_(chamada("buscar_metar", icao="SBXX")), texto("Sem dado."))
    assert r.avaliacoes[0]["nome_estacao"] is None


def test_req_a15_modelo_corrige_estacao_errada(rodar):
    """Roteiro do caso real: pede SBKP, vê 'Campinas', corrige para SBGR. As duas avaliações aparecem."""
    r, modelo, _, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBKP")),
                            ferramentas_(chamada("buscar_metar", icao="SBGR")), texto("Condições VMC em SBGR."))
    assert "Campinas" in json.loads(mensagens_tool(modelo, 1)[0]["content"])["nome_estacao"]
    assert [(a["icao"], a["nome_estacao"]) for a in r.avaliacoes] == [
        ("SBKP", "Campinas/Viracopos Arpt, SP, BR"), ("SBGR", "Sao Paulo Intl, PR, BR")]


# --------------------------------------------------------------------------- REQ-J-09 a J-12 janela pelo TAF

# 14–18Z VMC, 18–21Z IMC (TEMPO), 21Z–12Z VMC; validade até 11/12Z. AGORA = 10/11 14:10Z.
TAF_JANELA = "TAF SBGR 101100Z 1012/1112 09005KT CAVOK TEMPO 1018/1021 3000 BR BKN006"
TAFS_JANELA = {"SBGR": busca("SBGR", texto=TAF_JANELA, tipo="taf")}
PERGUNTA_JANELA = "Qual a melhor janela pra voar VFR em Guarulhos nas próximas horas?"


def rodar_janela(rodar, explicacao, tafs=None):
    return rodar(PERGUNTA_JANELA,
                 ferramentas_(chamada("buscar_metar", icao="SBGR"), chamada("avaliar_janela", icao="SBGR")),
                 texto(explicacao), tafs=TAFS_JANELA if tafs is None else tafs)


def test_req_j09_veredito_geral_continua_do_metar(rodar):
    r, _, _, _ = rodar_janela(rodar, "Agora está VMC em SBGR.")
    assert r.veredito == "VMC"
    assert r.janelas[0]["melhor_janela"] == {"inicio": "2026-11-10T21:00:00Z", "fim": "2026-11-11T12:00:00Z",
                                             "horas": 15}


def test_req_j09_janela_que_falhou(rodar):
    r, modelo, _, _ = rodar_janela(rodar, "Agora está VMC em SBGR.", tafs={})
    falha = json.loads(mensagens_tool(modelo, 1)[1]["content"])
    assert set(falha) == {"icao", "status", "veredito", "motivo"} and falha["veredito"] == "RECUSA"
    assert r.janelas[0]["veredito"] == "RECUSA"
    assert r.veredito == "VMC"  # a janela não mexe no veredito geral


def test_req_j09_traco_do_harness_do_taf(rodar):
    _, _, _, traco = rodar_janela(rodar, "Agora está VMC em SBGR.")
    taf = [p for p in passos(traco, "harness") if p.get("tipo_dado") == "taf"]
    assert len(taf) == 1 and taf[0]["horas"]


@pytest.mark.parametrize("explicacao,regra", [
    ("Às 19Z dá para voar visual.", "previsao_imc_com_afirmacao_favoravel"),
    ("Às 19h dá para voar visual.", "previsao_imc_com_afirmacao_favoravel"),
    ("Às 19:30Z dá para voar visual.", "previsao_imc_com_afirmacao_favoravel"),
    ("Às 16Z fica abaixo dos mínimos.", "previsao_vmc_com_afirmacao_desfavoravel"),
    ("Às 13Z dá para voar visual.", "horario_fora_da_validade"),
    ("Agora fica abaixo dos mínimos.", "vmc_com_afirmacao_desfavoravel"),
])
def test_req_j11_bloqueia(rodar, explicacao, regra):
    r, _, _, _ = rodar_janela(rodar, explicacao)
    assert r.bloqueio is not None and r.bloqueio["regra"] == regra
    assert "Melhor janela" in r.explicacao  # texto-modelo inclui a janela


@pytest.mark.parametrize("explicacao", [
    "Às 16Z dá para voar visual.",
    "A partir das 21 UTC dá para voar visual.",
    "Entre 18Z e 20Z fica abaixo dos mínimos.",
    "Agora dá para voar visual em SBGR. Das 18Z às 21Z as condições ficam abaixo dos mínimos; a melhor janela começa às 21Z.",
    # achado com o modelo real (10/11/2026): o fim da validade (12Z) citado como fim da janela não é "fora da validade"
    "A melhor janela para voar VFR é de 21Z a 12Z, com condições VMC previstas.",
])
def test_req_j11_passa(rodar, explicacao):
    r, _, _, _ = rodar_janela(rodar, explicacao)
    assert r.bloqueio is None and r.origem_explicacao == "modelo"


def test_req_j11_sem_janela_o_horario_nao_muda_nada(rodar):
    r, _, _, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR")), texto("Às 19Z dá para voar visual."))
    assert r.bloqueio is None


def test_req_j11_icao_da_janela_conta_como_consultado(rodar):
    tafs = {"SBSP": busca("SBSP", texto=TAF_JANELA.replace("SBGR", "SBSP"), tipo="taf")}
    r, _, _, _ = rodar(PERGUNTA, ferramentas_(chamada("buscar_metar", icao="SBGR"), chamada("avaliar_janela", icao="SBSP")),
                       texto("Agora está VMC em SBGR; veja a previsão de SBSP."), tafs=tafs)
    assert r.bloqueio is None


def test_req_j12_prefiltro_oferece_a_janela():
    assert "melhor janela" in harness.prefiltrar_pergunta("E daqui a 3 dias?").motivo.lower()


@pytest.mark.ollama
def test_req_j09_ollama_real_janela(tmp_path):
    r = Agente(pasta_traces=tmp_path).perguntar("Qual a melhor janela pra voar VFR em Congonhas nas próximas horas?")
    assert [j["icao"] for j in r.janelas] == ["SBSP"], r
    assert r.janelas[0]["veredito"] in {"JANELA", "RECUSA"}
