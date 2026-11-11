"""Loop do agente com tool calling do Ollama.

Especificação: specs/03-agente/requisitos.md e specs/03-agente/design.md.
O modelo escolhe aeródromos, ferramentas e texto; veredito, recusas, bloqueios e limites saem de código.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import httpx

from app import ferramentas, harness, harness_taf, prompts
from app.ferramentas import agora_utc
from app.harness import Resumo
from app.harness_taf import ResumoJanela
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
# Horário citado numa frase (REQ-J-11): "15Z", "15:30Z", "15 UTC", "15h", "às 15"
_RE_HORA = [
    re.compile(r"\b([01]?\d|2[0-3])(?::[0-5]\d)?\s*(?:z|utc)\b"),
    re.compile(r"\b([01]?\d|2[0-3])h(?:[0-5]\d)?\b"),
    re.compile(r"\b(?:as|às)\s+([01]?\d|2[0-3])(?::[0-5]\d)?\b"),
]
_RE_FRASES = re.compile(r"(?<=[.!?])\s+|\n+")

MOTIVOS_AGENTE = {
    "pergunta_invalida": f"Pergunta vazia ou longa demais (máximo {MAX_CARACTERES_PERGUNTA} caracteres).",
    "erro_modelo": "O modelo de linguagem não respondeu; não foi possível montar o briefing.",
    "limite_iteracoes": f"Limite de {MAX_CHAMADAS_FERRAMENTA} consultas por pergunta atingido sem resposta final.",
    "sem_avaliacao": "Nenhum aeródromo foi consultado; o sistema não responde sem dado.",
}
MOTIVOS_BUSCA_TAF = {
    "sem_dado": "A API não tem TAF disponível para este aeródromo.",
    "fora_do_escopo": harness.MOTIVOS_RECUSA["fora_do_escopo"],
    "erro_api": "Falha ao consultar a API meteorológica.",
    "limite_api": "Limite de consultas da API meteorológica atingido.",
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
    janelas: list[dict] = field(default_factory=list)  # previsão pelo TAF (REQ-J-09); não muda o veredito

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
        nomes: dict[str, str | None] = {}  # nome da estação por ICAO (REQ-A-15); não entra no veredito
        janelas: dict[str, ResumoJanela] = {}  # previsão pelo TAF por ICAO (REQ-J-09)

        def resposta(veredito, motivo, explicacao, origem, bloqueio=None) -> RespostaAgente:
            return RespostaAgente(id_traco=traco.id, veredito=veredito, motivo=motivo,
                                  avaliacoes=[{**r.para_dict(), "nome_estacao": nomes.get(icao)}
                                              for icao, r in avaliacoes.items()],
                                  explicacao=explicacao, origem_explicacao=origem, bloqueio=bloqueio,
                                  aviso=prompts.AVISO, duracao_ms=_ms_desde(t0),
                                  janelas=[j.para_dict() for j in janelas.values()])

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
                    janela = self._executar(nome, argumentos, traco, avaliacoes, nomes, janelas)
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

        # Verificação da explicação (REQ-A-09; com horário, REQ-J-11)
        referencia = next(r for r in resumos if r.veredito == geral)
        validas = [j for j in janelas.values() if j.veredito == "JANELA"]
        if validas:
            bloqueio = _verificar_com_horario(texto, referencia, validas, self._relogio())
        else:
            verificacao = harness.verificar_explicacao(texto, referencia)
            bloqueio = {"regra": verificacao.regra, "trecho": verificacao.trecho} if verificacao.bloqueada else None
        if bloqueio is None:
            inventados = [c for c in _RE_ICAO_BR.findall(texto) if c not in avaliacoes and c not in janelas]
            if inventados:
                bloqueio = {"regra": "icao_nao_avaliado", "trecho": inventados[0]}
        traco.passo("verificador", passou=bloqueio is None, **(bloqueio or {"regra": None, "trecho": None}))
        if bloqueio:
            textos = [harness.texto_modelo(r) for r in resumos]
            textos += [harness_taf.texto_modelo_janela(j) for j in janelas.values()]
            return resposta(geral, motivo, "\n".join(textos), "texto_modelo", bloqueio)
        return resposta(geral, motivo, texto, "modelo")

    # ------------------------------------------------------------------ ferramentas (design, seção 6.2)

    def _executar(self, nome, argumentos, traco: Traco, avaliacoes: dict[str, Resumo],
                  nomes: dict[str, str | None], janelas: dict[str, ResumoJanela]) -> dict:
        def registrar(janela: dict, resultado=None) -> dict:
            traco.passo("ferramenta", nome=nome, argumentos=argumentos,
                        resultado=resultado.para_dict() if resultado else None, janela=janela)
            return janela

        if nome not in ("buscar_metar", "avaliar_janela"):
            return registrar({"erro": f"ferramenta desconhecida: {nome}"})
        icao = argumentos.get("icao") if isinstance(argumentos, dict) else None
        if not isinstance(icao, str):
            return registrar({"erro": "argumento icao (texto) obrigatório"})

        if nome == "avaliar_janela":  # REQ-J-09: só o resumo do harness do TAF vai para a janela
            r = self._buscar_taf(icao)
            if r.status == "ok":
                avaliado = harness_taf.avaliar_taf(r.texto_bruto, r.icao, self._relogio())
                janela = avaliado.resumo.para_dict()
                janelas[r.icao] = avaliado.resumo
                registrar(janela, r)
                traco.passo("harness", icao=r.icao, tipo_dado="taf", veredito=avaliado.veredito,
                            codigo_recusa=avaliado.codigo_recusa, horas=avaliado.horas, resumo=janela)
                return janela
            if r.status == "icao_invalido":
                return registrar({"icao": r.icao, "status": r.status, "veredito": "RECUSA",
                                  "motivo": "Use o código ICAO de 4 letras."}, r)
            motivo = MOTIVOS_BUSCA_TAF.get(r.status, "Falha na busca do TAF.")
            janelas[r.icao] = ResumoJanela(icao=r.icao, emitido_utc=None, validade_inicio=None, validade_fim=None,
                                           periodos=[], melhor_janela=None, veredito="RECUSA", motivo=motivo,
                                           taf_bruto="")
            return registrar({"icao": r.icao, "status": r.status, "veredito": "RECUSA", "motivo": motivo}, r)

        r = self._buscar_metar(icao)
        if r.status == "ok":
            avaliado = harness.avaliar_metar(r.texto_bruto, r.icao, self._relogio())
            nome_estacao = _nome_estacao(r)
            janela = {**avaliado.resumo.para_dict(), "nome_estacao": nome_estacao}  # REQ-A-03 revisado
            avaliacoes[r.icao] = avaliado.resumo
            nomes[r.icao] = nome_estacao
            registrar(janela, r)
            traco.passo("harness", icao=r.icao, veredito=avaliado.veredito.value,
                        codigo_recusa=avaliado.codigo_recusa, nome_estacao=nome_estacao, resumo=janela)
            return janela
        if r.status == "icao_invalido":  # erro de digitação do modelo: não conta (REQ-A-07)
            return registrar({"icao": r.icao, "status": r.status, "veredito": "RECUSA",
                              "motivo": "Use o código ICAO de 4 letras."}, r)
        motivo = MOTIVOS_BUSCA.get(r.status, "Falha na busca do METAR.")
        avaliacoes[r.icao] = Resumo(icao=r.icao, tipo=None, horario_utc=None, idade_min=None, vis_m=None,
                                    teto_ft=None, camadas=[], veredito="RECUSA", motivo=motivo, metar_bruto="")
        nomes[r.icao] = None
        return registrar({"icao": r.icao, "status": r.status, "veredito": "RECUSA", "motivo": motivo}, r)


def _verificar_com_horario(texto: str, referencia: Resumo, janelas: list[ResumoJanela],
                           agora: datetime) -> dict | None:
    """REQ-J-11: frase com horário → período daquela hora; frase sem horário → veredito de agora."""
    if not texto.strip():
        return {"regra": "explicacao_vazia", "trecho": None}
    sem_horario = []
    for frase in _RE_FRASES.split(texto):
        horas = _horas_citadas(frase)
        if not horas:
            sem_horario.append(frase)
            continue
        vereditos = []
        for hora in sorted(horas):
            momento = _proxima_ocorrencia(hora, agora)
            previstos = [v for v in (_veredito_previsto(j, momento) for j in janelas) if v]
            if not previstos:
                return {"regra": "horario_fora_da_validade", "trecho": frase.strip()}
            vereditos.append("IMC" if "IMC" in previstos else "VMC")  # vários aeródromos: o pior (DJ6)
        # afirmação favorável: basta uma hora citada ser IMC; desfavorável: todas as horas citadas VMC
        if "IMC" in vereditos and (achado := harness.contradicao(frase, "IMC")):
            return {"regra": "previsao_" + achado[0], "trecho": achado[1]}
        if all(v == "VMC" for v in vereditos) and (achado := harness.contradicao(frase, "VMC")):
            return {"regra": "previsao_" + achado[0], "trecho": achado[1]}
    resto = " ".join(sem_horario)
    if resto.strip() and (achado := harness.contradicao(resto, referencia.veredito)):
        return {"regra": achado[0], "trecho": achado[1]}
    return None


def _veredito_previsto(janela: ResumoJanela, momento: datetime) -> str | None:
    """Veredito da hora; o fim exato da validade ("de 07Z a 12Z") vale pela última hora prevista."""
    veredito = harness_taf.veredito_na_hora(janela, momento)
    if veredito is None and janela.validade_fim == momento.strftime("%Y-%m-%dT%H:%M:%SZ"):
        veredito = harness_taf.veredito_na_hora(janela, momento - timedelta(minutes=1))
    return veredito


def _horas_citadas(frase: str) -> set[int]:
    minusculas = frase.lower()
    return {int(m.group(1)) for padrao in _RE_HORA for m in padrao.finditer(minusculas)}


def _proxima_ocorrencia(hora: int, agora: datetime) -> datetime:
    """Primeira ocorrência daquela hora UTC a partir da hora atual (DJ6)."""
    base = agora.replace(minute=0, second=0, microsecond=0)
    momento = base.replace(hour=hora)
    return momento if momento >= base else momento + timedelta(days=1)


def _nome_estacao(resultado) -> str | None:
    """Nome da estação no JSON da API (REQ-A-15). Só identifica; nunca decide nada."""
    dados = resultado.resposta_api
    primeiro = dados[0] if isinstance(dados, list) and dados else None
    nome = primeiro.get("name") if isinstance(primeiro, dict) else None
    if not isinstance(nome, str) or not nome.strip():
        return None
    return nome.strip()


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
