"""Coleta METARs reais de aeródromos brasileiros para a avaliação (CLAUDE.md, Avaliação, item 1).

Uma requisição por rodada para todos os aeródromos (respeita o limite de 100 req/min da API).
Salva o JSON bruto de cada rodada em avaliacao/dados/brutos/ e acrescenta uma linha por boletim novo em
avaliacao/dados/coleta.csv. O gabarito NÃO sai daqui: o grupo rotula à mão (casos.json); o campo fltCat da API
é guardado só como referência e não pode ser usado como rótulo.

Uso:
    python avaliacao/coletar_metars.py --uma-vez
    python avaliacao/coletar_metars.py --historico-horas 48
    python avaliacao/coletar_metars.py --intervalo-min 30 --ate 2026-11-11T13:00:00Z
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

AERODROMOS = [
    "SBGR", "SBSP", "SBKP", "SBMT", "SBSJ", "SBRJ", "SBGL", "SBCT", "SBPA", "SBFL", "SBJV", "SBLO", "SBNF",
    "SBBR", "SBGO", "SBCF", "SBVT", "SBSV", "SBRF", "SBFZ", "SBBE", "SBEG", "SBCG", "SBUL",
]
URL = "https://aviationweather.gov/api/data/metar"
USER_AGENT = "AgenteVFR/0.1 (projeto academico TE251)"
DADOS = Path(__file__).resolve().parent / "dados"
CSV = DADOS / "coleta.csv"
COLUNAS = ["coletado_em", "icao", "obs_utc", "metar_bruto", "fltCat_api_so_referencia"]


def agora() -> datetime:
    return datetime.now(timezone.utc)


def ja_coletados() -> set[tuple[str, str]]:
    if not CSV.exists():
        return set()
    with CSV.open(encoding="utf-8") as f:
        return {(l["icao"], l["metar_bruto"]) for l in csv.DictReader(f)}


def rodada(http: httpx.Client, horas: int | None = None) -> str:
    momento = agora()
    try:
        params = {"ids": ",".join(AERODROMOS), "format": "json", **({"hours": horas} if horas else {})}
        r = http.get(URL, params=params,
                     headers={"User-Agent": USER_AGENT}, timeout=60)
        r.raise_for_status()
        dados = r.json() if r.status_code == 200 else []
    except (httpx.HTTPError, ValueError) as e:
        return f"{momento:%H:%MZ} falha: {type(e).__name__}: {e}"

    (DADOS / "brutos").mkdir(parents=True, exist_ok=True)
    (DADOS / "brutos" / f"metars_{momento:%Y%m%dT%H%MZ}.json").write_text(
        json.dumps(dados, ensure_ascii=False), encoding="utf-8")

    vistos = ja_coletados()
    novos = 0
    novo_arquivo = not CSV.exists()
    with CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS)
        if novo_arquivo:
            w.writeheader()
        for d in dados:
            chave = (d.get("icaoId"), d.get("rawOb"))
            if not all(chave) or chave in vistos:
                continue
            obs = datetime.fromtimestamp(d["obsTime"], timezone.utc) if d.get("obsTime") else None
            w.writerow({"coletado_em": f"{momento:%Y-%m-%dT%H:%M:%SZ}", "icao": chave[0],
                        "obs_utc": f"{obs:%Y-%m-%dT%H:%M:%SZ}" if obs else "", "metar_bruto": chave[1],
                        "fltCat_api_so_referencia": d.get("fltCat", "")})
            vistos.add(chave)
            novos += 1
    nao_vfr = sum(1 for d in dados if d.get("fltCat") not in (None, "VFR"))
    return f"{momento:%H:%MZ} ok: {len(dados)} boletins, {novos} novos, {nao_vfr} não-VFR pela API (só referência)"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--uma-vez", action="store_true")
    p.add_argument("--intervalo-min", type=float, default=30)
    p.add_argument("--ate", help="ISO UTC, ex.: 2026-11-11T13:00:00Z")
    p.add_argument("--historico-horas", type=int, help="uma rodada com os boletins das últimas N horas")
    a = p.parse_args()
    fim = datetime.fromisoformat(a.ate.replace("Z", "+00:00")) if a.ate else None
    with httpx.Client() as http:
        while True:
            print(rodada(http, a.historico_horas), flush=True)
            if a.uma_vez or a.historico_horas or (fim and agora() >= fim):
                return 0
            time.sleep(a.intervalo_min * 60)


if __name__ == "__main__":
    sys.exit(main())
