"""Loop do agente com tool calling do Ollama.

Especificação: specs/03-agente/requisitos.md e specs/03-agente/design.md.
O modelo escolhe aeródromos, ferramentas e texto; veredito, recusas, bloqueios e limites saem de código.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

from app import ferramentas, harness, prompts
from app.ferramentas import agora_utc
from app.harness import Resumo
from app.traco import Traco

MAX_CHAMADAS_FERRAMENTA = 5     # REQ-A-04
MAX_CARACTERES_PERGUNTA = 500   # REQ-A-01
OLLAMA_URL_PADRAO = "http://localhost:11434"
OLLAMA_MODEL_PADRAO = "llama3.1:8b"
OLLAMA_TEMPERATURA_PADRAO = 0.1
OLLAMA_NUM_THREAD_PADRAO = 4     # M3: 4 núcleos de desempenho; com 8 a geração fica ~60× mais lenta
OLLAMA_TIMEOUT_PADRAO_S = 300.0  # CPU no Docker do Mac é lenta
SEED = 42

_RE_ICAO_BR = re.compile(r"\bS[BDIJNSW][A-Z]{2}\b")
_AVISO_TAF = "Informativo: o TAF não entra no veredito."

MOTIVOS_AGENTE = {
    "pergunta_invalida": f"Pergunta vazia ou longa demais (máximo {MAX_CARACTERES_PERGUNTA} caracteres).",
    "erro_modelo": "O modelo de linguagem não respondeu; não foi possível montar o briefing.",
    "limite_iteracoes": f"Limite de {MAX_CHAMADAS_FERRAMENTA} consultas por pergunta atingido sem resposta final.",
    "sem_avaliacao": "Nenhum aeródromo foi consultado; o sistema não responde sem dado.",
}
MOTIVOS_BUSCA = {
    "sem_dado": "A API não tem METAR disponível para este aeródromo.",
    "fora_do_escopo": harness.MOTIVOS_RECUSA["fora_do_escopo"],
    "erro_api": "Falha ao consultar a API meteorológica.",
    "limite_api": "Limite de consultas da API meteorológica atingido.",
}


class ErroModelo(Exception):
    """Falha ao falar com o Ollama (rede, HTTP, formato)."""


class ClienteOllama:
    def __init__(self, *, url: str | None = None, modelo: str | None = None,
                 temperatura: float | None = None, num_thread: int | None = None,
                 timeout_s: float | None = None, http: httpx.Client | None = None):
        self.url = (url or os.environ.get("OLLAMA_URL") or OLLAMA_URL_PADRAO).rstrip("/")
        self.modelo = modelo or os.environ.get("OLLAMA_MODEL") or OLLAMA_MODEL_PADRAO
        if temperatura is None:
            temperatura = os.environ.get("OLLAMA_TEMPERATURA", OLLAMA_TEMPERATURA_PADRAO)
        self.temperatura = float(temperatura)
        if num_thread is None:
            num_thread = os.environ.get("OLLAMA_NUM_THREAD", OLLAMA_NUM_THREAD_PADRAO)
        self.num_thread = int(num_thread)
        if timeout_s is None:
            timeout_s = os.environ.get("OLLAMA_TIMEOUT_S", OLLAMA_TIMEOUT_PADRAO_S)
        self.timeout_s = float(timeout_s)
        self._http = http or httpx.Client()

    def conversar(self, mensagens: list[dict], ferramentas: list[dict]) -> dict:
        corpo = {"model": self.modelo, "messages": mensagens, "tools": ferramentas, "stream": False,
                 "options": {"temperature": self.temperatura, "seed": SEED, "num_thread": self.num_thread}}
        try:
            r = self._http.post(f"{self.url}/api/chat", json=corpo, timeout=self.timeout_s)
        except httpx.TransportError as e:
            raise ErroModelo(f"{type(e).__name__}: {e}") from e
        if r.status_code != 200:
            raise ErroModelo(f"HTTP {r.status_code}: {r.text[:300]}")
        try:
            dados = r.json()
        except ValueError as e:
            raise ErroModelo("resposta do Ollama não é JSON") from e
        if not isinstance(dados, dict) or not isinstance(dados.get("message"), dict):
            raise ErroModelo("resposta do Ollama sem 'message'")
        return dados


@dataclass(frozen=True)
class RespostaAgente:
    """Resposta final (REQ-A-10). O veredito vem sempre de código."""

    id_traco: str
    veredito: str
    motivo: str
    avaliacoes: list[dict]
    explicacao: str
    origem_explicacao: str      # "modelo" | "texto_modelo"
    bloqueio: dict | None       # {"regra", "trecho"} quando o verificador barrou a explicação
    aviso: str
    duracao_ms: int

    def para_dict(self) -> dict:
        return asdict(self)


class Agente:
    def __init__(self, *, ollama: ClienteOllama | None = None,
                 buscar_metar=ferramentas.buscar_metar, buscar_taf=ferramentas.buscar_taf,
                 relogio=agora_utc, pasta_traces: Path | None = None):
        self._ollama = ollama or ClienteOllama()
        self._buscar_metar = buscar_metar
        self._buscar_taf = buscar_taf
        self._relogio = relogio
        self._pasta = pasta_traces

    def perguntar(self, pergunta: str) -> RespostaAgente:
        traco = Traco(pergunta, modelo=getattr(self._ollama, "modelo", "?"),
                      versao_prompt=prompts.VERSAO_PROMPT, relogio=self._relogio, pasta=self._pasta)
        resposta: RespostaAgente | None = None
        try:
            resposta = self._responder(pergunta, traco, time.perf_counter())
            return resposta
        except Exception as e:  # bug: registra no traço e deixa subir
            traco.passo("erro", regra="excecao", mensagem=f"{type(e).__name__}: {e}")
            raise
        finally:
            traco.gravar(resposta.para_dict() if resposta else None)

    # ------------------------------------------------------------------ loop (design, seção 6.1)

    def _responder(self, pergunta: str, traco: Traco, t0: float) -> RespostaAgente:
        avaliacoes: dict[str, Resumo] = {}

        def resposta(veredito, motivo, explicacao, origem, bloqueio=None) -> RespostaAgente:
            return RespostaAgente(id_traco=traco.id, veredito=veredito, motivo=motivo,
                                  avaliacoes=[r.para_dict() for r in avaliacoes.values()],
                                  explicacao=explicacao, origem_explicacao=origem, bloqueio=bloqueio,
                                  aviso=prompts.AVISO, duracao_ms=_ms_desde(t0))

        def recusa(motivo: str) -> RespostaAgente:
            return resposta("RECUSA", motivo, f"{motivo} Consulte o briefing oficial (REDEMET/AIS).",
                            "texto_modelo")

        # Pré-filtro em código, antes do modelo (REQ-A-01)
        if not isinstance(pergunta, str) or not pergunta.strip() or len(pergunta) > MAX_CARACTERES_PERGUNTA:
            motivo = MOTIVOS_AGENTE["pergunta_invalida"]
            traco.passo("prefiltro", passou=False, regra="pergunta_invalida", motivo=motivo)
            return recusa(motivo)
        filtro = harness.prefiltrar_pergunta(pergunta)
        if filtro:
            traco.passo("prefiltro", passou=False, regra=filtro.categoria, termo=filtro.termo, motivo=filtro.motivo)
            return recusa(filtro.motivo)
        traco.passo("prefiltro", passou=True, regra=None, motivo=None)

        mensagens = [{"role": "system", "content": prompts.PROMPT_SISTEMA},
                     {"role": "user", "content": pergunta}]
        chamadas = 0
        lembrete_usado = False
        while True:
            inicio = time.perf_counter()
            try:
                dados = self._ollama.conversar(mensagens, prompts.FERRAMENTAS)
            except ErroModelo as e:
                traco.passo("erro", regra="erro_modelo", mensagem=str(e))
                return recusa(MOTIVOS_AGENTE["erro_modelo"])
            mensagem = dados["message"]
            traco.passo("modelo", mensagens=list(mensagens), resposta=mensagem,
                        prompt_eval_count=dados.get("prompt_eval_count"), eval_count=dados.get("eval_count"),
                        tokens_estimados=len(json.dumps(mensagens, ensure_ascii=False)) // 4,
                        duracao_ms=_ms_desde(inicio))

            pedidas = mensagem.get("tool_calls") or []
            if pedidas:
                mensagens.append({"role": "assistant", "content": mensagem.get("content") or "",
                                  "tool_calls": pedidas})
                for pedida in pedidas:
                    if chamadas >= MAX_CHAMADAS_FERRAMENTA:
                        traco.passo("erro", regra="limite_iteracoes", mensagem=MOTIVOS_AGENTE["limite_iteracoes"])
                        return recusa(MOTIVOS_AGENTE["limite_iteracoes"])
                    chamadas += 1
                    nome, argumentos = _ler_chamada(pedida)
                    janela = self._executar(nome, argumentos, traco, avaliacoes)
                    mensagens.append({"role": "tool", "tool_name": nome,
                                      "content": json.dumps(janela, ensure_ascii=False)})
                continue

            texto = mensagem.get("content") or ""
            if avaliacoes:
                break
            if not lembrete_usado:  # REQ-A-05
                lembrete_usado = True
                mensagens.append({"role": "assistant", "content": texto})
                mensagens.append({"role": "user", "content": prompts.LEMBRETE_FERRAMENTA})
                continue
            traco.passo("erro", regra="sem_avaliacao", mensagem=MOTIVOS_AGENTE["sem_avaliacao"])
            return recusa(MOTIVOS_AGENTE["sem_avaliacao"])

        # Veredito geral em código (REQ-A-07)
        resumos = list(avaliacoes.values())
        vereditos = {r.veredito for r in resumos}
        geral = "RECUSA" if "RECUSA" in vereditos else "IMC" if "IMC" in vereditos else "VMC"
        motivo = resumos[0].motivo if len(resumos) == 1 else "; ".join(f"{r.icao}: {r.veredito}" for r in resumos)

        if geral == "RECUSA":  # REQ-A-08: o modelo não "conserta" a recusa
            traco.passo("verificador", passou=None, regra="veredito_recusa",
                        motivo="explicação do modelo descartada")
            explicacao = "\n".join(harness.texto_modelo(r) for r in resumos if r.veredito == "RECUSA")
            return resposta("RECUSA", motivo, explicacao, "texto_modelo")

        # Verificação da explicação (REQ-A-09)
        referencia = next(r for r in resumos if r.veredito == geral)
        verificacao = harness.verificar_explicacao(texto, referencia)
        bloqueio = None
        if verificacao.bloqueada:
            bloqueio = {"regra": verificacao.regra, "trecho": verificacao.trecho}
        else:
            inventados = [c for c in _RE_ICAO_BR.findall(texto) if c not in avaliacoes]
            if inventados:
                bloqueio = {"regra": "icao_nao_avaliado", "trecho": inventados[0]}
        traco.passo("verificador", passou=bloqueio is None, **(bloqueio or {"regra": None, "trecho": None}))
        if bloqueio:
            return resposta(geral, motivo, "\n".join(harness.texto_modelo(r) for r in resumos),
                            "texto_modelo", bloqueio)
        return resposta(geral, motivo, texto, "modelo")

    # ------------------------------------------------------------------ ferramentas (design, seção 6.2)

    def _executar(self, nome, argumentos, traco: Traco, avaliacoes: dict[str, Resumo]) -> dict:
        def registrar(janela: dict, resultado=None) -> dict:
            traco.passo("ferramenta", nome=nome, argumentos=argumentos,
                        resultado=resultado.para_dict() if resultado else None, janela=janela)
            return janela

        if nome not in ("buscar_metar", "buscar_taf"):
            return registrar({"erro": f"ferramenta desconhecida: {nome}"})
        icao = argumentos.get("icao") if isinstance(argumentos, dict) else None
        if not isinstance(icao, str):
            return registrar({"erro": "argumento icao (texto) obrigatório"})

        if nome == "buscar_taf":
            r = self._buscar_taf(icao)
            return registrar({"icao": r.icao, "status": r.status, "taf_bruto": r.texto_bruto,
                              "aviso": _AVISO_TAF}, r)

        r = self._buscar_metar(icao)
        if r.status == "ok":
            avaliado = harness.avaliar_metar(r.texto_bruto, r.icao, self._relogio())
            janela = avaliado.resumo.para_dict()
            avaliacoes[r.icao] = avaliado.resumo
            registrar(janela, r)
            traco.passo("harness", icao=r.icao, veredito=avaliado.veredito.value,
                        codigo_recusa=avaliado.codigo_recusa, resumo=janela)
            return janela
        if r.status == "icao_invalido":  # erro de digitação do modelo: não conta (REQ-A-07)
            return registrar({"icao": r.icao, "status": r.status, "veredito": "RECUSA",
                              "motivo": "Use o código ICAO de 4 letras."}, r)
        motivo = MOTIVOS_BUSCA.get(r.status, "Falha na busca do METAR.")
        avaliacoes[r.icao] = Resumo(icao=r.icao, tipo=None, horario_utc=None, idade_min=None, vis_m=None,
                                    teto_ft=None, camadas=[], veredito="RECUSA", motivo=motivo, metar_bruto="")
        return registrar({"icao": r.icao, "status": r.status, "veredito": "RECUSA", "motivo": motivo}, r)


def _ler_chamada(pedida) -> tuple[object, object]:
    funcao = pedida.get("function") if isinstance(pedida, dict) else None
    if not isinstance(funcao, dict):
        return None, None
    argumentos = funcao.get("arguments")
    if isinstance(argumentos, str):  # modelos menores mandam os argumentos como texto JSON
        try:
            argumentos = json.loads(argumentos)
        except ValueError:
            argumentos = None
    return funcao.get("name"), argumentos


def _ms_desde(inicio: float) -> int:
    return int((time.perf_counter() - inicio) * 1000)
