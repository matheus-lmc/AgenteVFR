"""Avaliação do AgenteVFR (specs/06-avaliacao/requisitos.md).

Mede: acurácia do harness contra o gabarito do grupo (REQ-V-01), acerto de ICAO com os prompts v1 e v3 (REQ-V-02),
recusas corretas e falsas (REQ-V-03), fidelidade da explicação por um modelo juiz (REQ-V-04), bloqueios do
verificador (REQ-V-05) e tokens/tempo por execução (REQ-V-06). Saídas em avaliacao/resultados/ (REQ-V-07).

O agente roda contra um "mundo congelado" (decisão E1): os METARs de uma rodada gravada e o relógio parado.

Uso:
    python avaliacao/avaliar.py --so-harness        # segundos, sem Ollama
    python avaliacao/avaliar.py                     # completo (~20 min no Compose)
    python avaliacao/avaliar.py --prompts v3 --sem-juiz
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import statistics
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app import harness, prompts  # noqa: E402
from app.agente import Agente, ClienteOllama, ErroModelo  # noqa: E402
from app.ferramentas import ClienteAWC  # noqa: E402

BASE = Path(__file__).resolve().parent
ROTULAGEM = BASE / "dados" / "rotulagem.xlsx"
CASOS = BASE / "casos.json"
RESULTADOS = BASE / "resultados"
UTC = timezone.utc
CRITERIOS = ("consistencia", "teto_visibilidade", "sem_invencao")
RECUSA_POR_DADO = {"harness:dado_desatualizado", "harness:sem_dado", "busca:sem_dado"}


# ============================================================================ REQ-V-01 harness × gabarito

def ler_rotulagem(caminho: Path = ROTULAGEM) -> list[dict]:
    from openpyxl import load_workbook

    ws = load_workbook(caminho, read_only=True, data_only=True)["Rotulagem"]
    linhas = []
    for n, icao, obs, metar, api, grupo, nota in ws.iter_rows(min_row=2, max_col=7, values_only=True):
        if n is None or not grupo:
            continue
        linhas.append({"n": n, "icao": icao, "obs": obs, "metar": metar, "api": api or "",
                       "grupo": str(grupo).strip().upper(), "nota": nota or ""})
    return linhas


def avaliar_harness(linhas: list[dict]) -> list[dict]:
    saida = []
    for l in linhas:
        agora = datetime.strptime(l["obs"], "%Y-%m-%d %H:%MZ").replace(tzinfo=UTC) + timedelta(minutes=10)
        r = harness.avaliar_metar(l["metar"], l["icao"], agora)
        veredito = getattr(r.veredito, "value", r.veredito)
        gabarito = "RECUSA" if l["grupo"] == "INVALIDO" else l["grupo"]
        api_lida = "VMC" if l["api"] == "VFR" else "IMC"
        saida.append({**l, "gabarito": gabarito, "harness": veredito, "motivo_harness": r.resumo.motivo,
                      "acerto_harness": veredito == gabarito, "api_lida": api_lida,
                      "acerto_api": api_lida == gabarito})
    return saida


# ============================================================================ REQ-V-02/03 agente

def classificar_icaos(consultados: list[str], esperados: list[str]) -> str:
    c, e = set(consultados), set(esperados)
    if not c:
        return "nenhum"
    if c == e:
        return "exato"
    if c < e:
        return "parcial"
    if c > e:
        return "extra"
    return "errado"


def origem_recusa(traco: dict, veredito: str) -> str | None:
    if veredito != "RECUSA":
        return None
    passos = traco.get("passos", [])
    for p in passos:
        if p.get("tipo") == "prefiltro" and p.get("passou") is False:
            return f"prefiltro:{p.get('regra')}"
    for p in passos:
        if p.get("tipo") == "erro":
            return f"agente:{p.get('regra')}"
    for p in passos:
        if p.get("tipo") == "harness" and p.get("codigo_recusa"):
            return f"harness:{p['codigo_recusa']}"
    for p in passos:
        status = (p.get("resultado") or {}).get("status") if p.get("tipo") == "ferramenta" else None
        if status and status not in ("ok", "icao_invalido"):
            return f"busca:{status}"
    return "desconhecida"


def eh_falsa_recusa(caso: dict, resposta: dict, origem: str | None) -> bool:
    if caso.get("tipo") != "normal" or resposta.get("veredito") != "RECUSA":
        return False
    if origem in RECUSA_POR_DADO:  # dado velho/ausente do aeródromo certo: a recusa é a resposta certa
        recusados = {a["icao"] for a in resposta.get("avaliacoes", []) if a.get("veredito") == "RECUSA"}
        return not (recusados & set(caso.get("icaos_esperados", [])))
    return True


def tokens_do_traco(traco: dict) -> int:
    return sum((p.get("prompt_eval_count") or 0) + (p.get("eval_count") or 0)
               for p in traco.get("passos", []) if p.get("tipo") == "modelo")


def cliente_mundo(objetos: list[dict], relogio) -> ClienteAWC:
    """ClienteAWC de verdade (validação, escopo, cache) com a API trocada pela rodada gravada."""
    por_icao = {o["icaoId"]: o for o in objetos}

    def responder(req: httpx.Request) -> httpx.Response:
        icao = req.url.params.get("ids", "")
        if req.url.path.endswith("/taf"):
            return httpx.Response(200, json=[])
        if icao in por_icao:
            return httpx.Response(200, json=[por_icao[icao]])
        return httpx.Response(204)

    return ClienteAWC(http=httpx.Client(transport=httpx.MockTransport(responder)), relogio=relogio)


# ============================================================================ REQ-V-04 juiz

PROMPT_JUIZ = """\
Você avalia explicações de um sistema de briefing meteorológico VFR. O VEREDITO foi calculado em código e está
certo por definição. Avalie só a EXPLICAÇÃO, de 1 (péssimo) a 5 (perfeito), em três critérios:
- consistencia: a explicação concorda com o veredito (não diz que dá para voar visual se é IMC, nem o contrário).
- teto_visibilidade: os valores de teto e visibilidade citados são os dos DADOS (se não citar nenhum, nota 3).
- sem_invencao: não inventa dado que não está nos DADOS (vento, tendência, outro aeródromo, previsão).
Responda SOMENTE com um JSON: {"consistencia": n, "teto_visibilidade": n, "sem_invencao": n, "justificativa": "..."}
"""


def ler_juiz(texto: str) -> dict | None:
    m = re.search(r"\{.*\}", texto or "", re.DOTALL)
    if not m:
        return None
    try:
        dados = json.loads(m.group(0))
    except ValueError:
        return None
    if not isinstance(dados, dict):
        return None
    notas = {}
    for k in CRITERIOS:
        v = dados.get(k)
        if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 5:
            return None
        notas[k] = v
    return {**notas, "justificativa": str(dados.get("justificativa", ""))}


def julgar(ollama: ClienteOllama, resposta: dict) -> tuple[dict | None, str]:
    dados = [{k: a.get(k) for k in ("icao", "veredito", "teto_ft", "vis_m", "camadas", "metar_bruto")}
             for a in resposta.get("avaliacoes", [])]
    usuario = (f"VEREDITO: {resposta['veredito']}\nDADOS: {json.dumps(dados, ensure_ascii=False)}\n"
               f"EXPLICAÇÃO:\n{resposta['explicacao']}")
    try:
        bruto = ollama.conversar([{"role": "system", "content": PROMPT_JUIZ},
                                  {"role": "user", "content": usuario}], [])["message"].get("content") or ""
    except ErroModelo as e:
        return None, f"erro: {e}"
    return ler_juiz(bruto), bruto


# ============================================================================ resumo

def _par(n, total):
    return (n, total)


def resumir(harness_linhas: list[dict], agente_linhas: list[dict], juiz_linhas: list[dict]) -> dict:
    r = {"harness_acertos": _par(sum(l["acerto_harness"] for l in harness_linhas), len(harness_linhas)),
         "api_acertos": _par(sum(l["acerto_api"] for l in harness_linhas), len(harness_linhas)),
         "prompts": {}}
    for prompt in dict.fromkeys(l["prompt"] for l in agente_linhas):
        ls = [l for l in agente_linhas if l["prompt"] == prompt]
        normais = [l for l in ls if l["tipo"] == "normal"]
        recusas = [l for l in ls if l["tipo"] == "recusa"]
        com_modelo = [l for l in ls if l["tokens"]]
        r["prompts"][prompt] = {
            "icao_exato": _par(sum(l["classe_icao"] == "exato" for l in normais), len(normais)),
            "icao_classes": dict(Counter(l["classe_icao"] for l in normais)),
            "recusa_correta": _par(sum(l["veredito"] == "RECUSA" for l in recusas), len(recusas)),
            "falsa_recusa": _par(sum(bool(l["falsa_recusa"]) for l in normais), len(normais)),
            "bloqueios": sum(bool(l["bloqueio"]) for l in ls),
            "tokens_medios": round(statistics.mean(l["tokens"] for l in com_modelo)) if com_modelo else 0,
            "tempo_medio_s": round(statistics.mean(l["duracao_ms"] for l in com_modelo) / 1000, 1) if com_modelo else 0,
        }
    medias = {}
    for k in CRITERIOS:
        notas = [j[k] for j in juiz_linhas if j.get(k) is not None]
        medias[k] = round(statistics.mean(notas), 2) if notas else None
    r["juiz_medias"] = medias
    r["juiz_sem_nota"] = sum(any(j.get(k) is None for k in CRITERIOS) for j in juiz_linhas)
    r["juiz_avaliadas"] = len(juiz_linhas)
    return r


def _pct(par):
    n, t = par
    return f"{n}/{t} ({100 * n / t:.0f}%)" if t else "—"


def resumo_markdown(r: dict, harness_linhas: list[dict], agente_linhas: list[dict], meta: dict) -> str:
    linhas = ["# Resultados da avaliação", "",
              f"Gerado em {meta['gerado_em']} · modelo `{meta['modelo']}` · mundo congelado `{meta['mundo']}` "
              f"(relógio {meta['relogio']}). Especificação: `specs/06-avaliacao/requisitos.md`.", "",
              "## Harness × gabarito do grupo (REQ-V-01)", "",
              "| Quem decide | Acertos |", "|---|---|",
              f"| Harness (regra em código) | {_pct(r['harness_acertos'])} |",
              f"| Categoria da API lida como VFR = VMC | {_pct(r['api_acertos'])} |", ""]
    div = [l for l in harness_linhas if not l["acerto_harness"]]
    linhas += ["Divergências do harness: " + ("nenhuma." if not div else
               "; ".join(f"#{l['n']} {l['icao']} grupo {l['grupo']} × harness {l['harness']}" for l in div)), ""]
    if r["prompts"]:
        ps = list(r["prompts"])
        linhas += ["## Agente (REQ-V-02 a 06)", "", "| Métrica | " + " | ".join(ps) + " |",
                   "|---|" + "---|" * len(ps)]
        rot = [("ICAO exato (o que o modelo decide)", lambda p: _pct(p["icao_exato"])),
               ("Classes de ICAO", lambda p: ", ".join(f"{k} {v}" for k, v in sorted(p["icao_classes"].items()))),
               ("Recusa correta", lambda p: _pct(p["recusa_correta"])),
               ("Falsa recusa", lambda p: _pct(p["falsa_recusa"])),
               ("Explicações bloqueadas pelo verificador", lambda p: str(p["bloqueios"])),
               ("Tokens médios por execução", lambda p: str(p["tokens_medios"])),
               ("Tempo médio por pergunta (s)", lambda p: str(p["tempo_medio_s"]))]
        for nome, f in rot:
            linhas.append(f"| {nome} | " + " | ".join(f(r["prompts"][p]) for p in ps) + " |")
        linhas += ["", "### Por pergunta", "", "| Prompt | Id | Pergunta | Esperado | Consultou | Classe | Veredito | Origem da recusa |",
                   "|---|---|---|---|---|---|---|---|"]
        for l in agente_linhas:
            linhas.append(f"| {l['prompt']} | {l['id']} | {l['texto'] or '(vazia)'} | {l['esperados']} | "
                          f"{l['consultados']} | {l['classe_icao'] or '—'} | {l['veredito']} | {l['origem_recusa'] or '—'} |")
    if r.get("juiz_avaliadas"):
        m = r["juiz_medias"]
        linhas += ["", "## Juiz (REQ-V-04)", "",
                   f"{r['juiz_avaliadas']} explicações do modelo avaliadas pelo próprio `{meta['modelo']}` "
                   "(viés de autoavaliação: limite registrado).", "",
                   "| Critério | Média (1–5) |", "|---|---|"]
        linhas += [f"| {k} | {m[k]} |" for k in CRITERIOS]
        linhas += [f"| sem nota (resposta do juiz ilegível) | {r['juiz_sem_nota']} |"]
    return "\n".join(linhas) + "\n"


def figuras(r: dict, pasta: Path) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    feitas = []
    fig, ax = plt.subplots(figsize=(6, 3.2))
    nomes = ["Harness\n(regra em código)", "Categoria da API\n(VFR = VMC)"]
    vals = [r["harness_acertos"], r["api_acertos"]]
    barras = ax.bar(nomes, [100 * n / t for n, t in vals], color=["#15803D", "#64748B"], width=0.55)
    for b, (n, t) in zip(barras, vals):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2, f"{n}/{t}", ha="center", fontsize=11)
    ax.set_ylim(0, 110)
    ax.set_ylabel("acerto contra o gabarito (%)")
    ax.set_title("Veredito VMC/IMC × rótulo do grupo")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    feitas.append(pasta / "fig_harness_api.png")
    fig.savefig(feitas[-1], dpi=200)
    plt.close(fig)

    if r["prompts"]:
        ps = list(r["prompts"])
        metricas = [("ICAO exato", "icao_exato"), ("Recusa correta", "recusa_correta"), ("Falsa recusa", "falsa_recusa")]
        fig, ax = plt.subplots(figsize=(7, 3.4))
        largura = 0.8 / len(ps)
        cores = ["#94A3B8", "#0369A1", "#B45309"]
        for i, p in enumerate(ps):
            ys = [100 * r["prompts"][p][k][0] / max(r["prompts"][p][k][1], 1) for _, k in metricas]
            xs = [j + i * largura for j in range(len(metricas))]
            bs = ax.bar(xs, ys, largura, label=f"prompt {p}", color=cores[i % len(cores)])
            for b, (_, k) in zip(bs, metricas):
                n, t = r["prompts"][p][k]
                ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 2, f"{n}/{t}", ha="center", fontsize=9)
        ax.set_xticks([j + largura * (len(ps) - 1) / 2 for j in range(len(metricas))], [m for m, _ in metricas])
        ax.set_ylim(0, 115)
        ax.set_ylabel("%")
        ax.set_title("Agente: o que o modelo decide × o que o sistema força")
        ax.legend(frameon=False)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        feitas.append(pasta / "fig_agente.png")
        fig.savefig(feitas[-1], dpi=200)
        plt.close(fig)
    return feitas


def _gravar_csv(caminho: Path, linhas: list[dict]) -> None:
    if not linhas:
        return
    chaves = list(dict.fromkeys(k for l in linhas for k in l))
    with caminho.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=chaves)
        w.writeheader()
        w.writerows(linhas)


# ============================================================================ execução

def rodar_agente(casos: dict, versoes: list[str], ollama: ClienteOllama, pasta_traces: Path) -> list[dict]:
    mundo = json.loads((BASE / casos["mundo"]).read_text(encoding="utf-8"))
    relogio_fixo = datetime.fromisoformat(casos["relogio"].replace("Z", "+00:00"))
    relogio = lambda: relogio_fixo  # noqa: E731
    original = (prompts.PROMPT_SISTEMA, prompts.VERSAO_PROMPT)
    linhas = []
    try:
        for v in versoes:
            prompts.PROMPT_SISTEMA = getattr(prompts, f"PROMPT_SISTEMA_{v.upper()}")
            prompts.VERSAO_PROMPT = v
            cliente = cliente_mundo(mundo, relogio)
            agente = Agente(ollama=ollama, buscar_metar=cliente.buscar_metar, buscar_taf=cliente.buscar_taf,
                            relogio=relogio, pasta_traces=pasta_traces)
            for caso in casos["perguntas"]:
                t0 = time.perf_counter()
                resp = agente.perguntar(caso["texto"]).para_dict()
                traco = json.loads(next(pasta_traces.glob(f"*_{resp['id_traco']}.json")).read_text(encoding="utf-8"))
                consultados = list(dict.fromkeys(a["icao"] for a in resp["avaliacoes"]))
                origem = origem_recusa(traco, resp["veredito"])
                esperados = caso.get("icaos_esperados", [])
                linha = {
                    "prompt": v, "id": caso["id"], "tipo": caso["tipo"], "texto": caso["texto"],
                    "esperados": " ".join(esperados), "consultados": " ".join(consultados),
                    "classe_icao": classificar_icaos(consultados, esperados) if caso["tipo"] == "normal" else None,
                    "veredito": resp["veredito"], "origem_recusa": origem,
                    "falsa_recusa": eh_falsa_recusa(caso, resp, origem),
                    "bloqueio": (resp["bloqueio"] or {}).get("regra"), "origem_explicacao": resp["origem_explicacao"],
                    "tokens": tokens_do_traco(traco), "duracao_ms": resp["duracao_ms"], "id_traco": resp["id_traco"],
                    "explicacao": resp["explicacao"], "_resposta": resp,
                }
                linhas.append(linha)
                print(f"  {v} {caso['id']}: {resp['veredito']:<6} consultou [{linha['consultados']}] "
                      f"{linha['classe_icao'] or linha['origem_recusa'] or ''} ({time.perf_counter() - t0:.0f} s)",
                      flush=True)
    finally:
        prompts.PROMPT_SISTEMA, prompts.VERSAO_PROMPT = original
    return linhas


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--so-harness", action="store_true", help="só REQ-V-01 (sem Ollama)")
    p.add_argument("--prompts", default="v1,v3", help="versões do prompt a comparar (padrão: v1,v3)")
    p.add_argument("--sem-juiz", action="store_true")
    a = p.parse_args()

    RESULTADOS.mkdir(parents=True, exist_ok=True)
    casos = json.loads(CASOS.read_text(encoding="utf-8"))
    h = avaliar_harness(ler_rotulagem())
    _gravar_csv(RESULTADOS / "harness.csv", h)
    print(f"Harness × gabarito: {sum(l['acerto_harness'] for l in h)}/{len(h)}; "
          f"API: {sum(l['acerto_api'] for l in h)}/{len(h)}", flush=True)

    agente_linhas, juiz_linhas = [], []
    ollama = ClienteOllama()
    if not a.so_harness:
        versoes = [v.strip() for v in a.prompts.split(",") if v.strip()]
        agente_linhas = rodar_agente(casos, versoes, ollama, RESULTADOS / "traces")
        if not a.sem_juiz:
            juiz = ClienteOllama(temperatura=0)
            alvo = [l for l in agente_linhas if l["prompt"] == versoes[-1] and l["tipo"] == "normal"
                    and l["origem_explicacao"] == "modelo"]
            for l in alvo:
                notas, bruto = julgar(juiz, l["_resposta"])
                juiz_linhas.append({"prompt": l["prompt"], "id": l["id"], "veredito": l["veredito"],
                                    **{k: (notas or {}).get(k) for k in CRITERIOS},
                                    "justificativa": (notas or {}).get("justificativa", ""),
                                    "explicacao": l["explicacao"], "resposta_juiz": bruto})
                print(f"  juiz {l['id']}: {[(notas or {}).get(k) for k in CRITERIOS]}", flush=True)
        _gravar_csv(RESULTADOS / "agente.csv", [{k: v for k, v in l.items() if k != "_resposta"} for l in agente_linhas])
        _gravar_csv(RESULTADOS / "juiz.csv", juiz_linhas)

    r = resumir(h, agente_linhas, juiz_linhas)
    meta = {"gerado_em": datetime.now(UTC).strftime("%Y-%m-%d %H:%MZ"), "modelo": ollama.modelo,
            "mundo": casos["mundo"], "relogio": casos["relogio"]}
    nome = "resumo_harness.md" if a.so_harness else "resumo.md"
    (RESULTADOS / nome).write_text(resumo_markdown(r, h, agente_linhas, meta), encoding="utf-8")
    figs = figuras(r, RESULTADOS)
    print(f"Resultados em {RESULTADOS.relative_to(RAIZ)}: {nome}, " + ", ".join(f.name for f in figs), flush=True)
    return 0


if __name__ == "__main__":
    os.environ.setdefault("OLLAMA_URL", "http://localhost:11434")
    sys.exit(main())
