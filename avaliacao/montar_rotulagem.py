"""Monta a planilha de rotulagem manual (CLAUDE.md, Avaliação, item 2) a partir de avaliacao/dados/coleta.csv.

Escolhe ~40 METARs variados (casos de borda + mistura de categorias da API + vários aeródromos), embaralha a ordem
e gera avaliacao/dados/rotulagem.xlsx, com a coluna "Veredito do grupo" em branco para o grupo preencher.

O fltCat da API vai junto só como referência (critério americano: VFR/MVFR/IFR/LIFR). O gabarito é o
veredito do grupo, nunca o da API nem o do harness.

Não sobrescreve uma planilha existente (pode já ter rótulos); use --forcar para gerar de novo.

Uso:
    python avaliacao/montar_rotulagem.py [--forcar]
"""

from __future__ import annotations

import argparse
import csv
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation

BASE = Path(__file__).resolve().parent
COLETA = BASE / "dados" / "coleta.csv"
SAIDA = BASE / "dados" / "rotulagem.xlsx"
SEMENTE = 251
TOTAL = 40
VEREDITOS = ("VMC", "IMC", "INVALIDO")

# Casos de borda que a regra precisa acertar: (padrão no METAR bruto, quantos pegar)
BORDAS = [
    (r"\b(BKN|OVC)015\b", 3),  # teto exatamente no mínimo
    (r" 5000 ", 2),            # visibilidade exatamente no mínimo
    (r"CAVOK", 2),
    (r"////", 1),              # campo ilegível
    (r" AUTO ", 2),
    (r"^SPECI", 3),
    (r" COR ", 1),
]
# Alvo por categoria da API (contando as bordas): garante IMC suficiente na amostra
ALVO = {"IFR+": 12, "MVFR": 13, "VFR": 15}


def grupo(cat: str) -> str:
    return "IFR+" if cat in ("IFR", "LIFR") else ("MVFR" if cat == "MVFR" else "VFR")


def escolher(linhas: list[dict]) -> list[dict]:
    rnd = random.Random(SEMENTE)
    escolhidos: list[dict] = []
    usados: set[str] = set()

    for padrao, n in BORDAS:
        cands = [l for l in linhas if re.search(padrao, l["metar_bruto"]) and l["metar_bruto"] not in usados]
        rnd.shuffle(cands)
        for l in cands[:n]:
            escolhidos.append(l)
            usados.add(l["metar_bruto"])

    falta = {g: ALVO[g] - sum(1 for l in escolhidos if grupo(l["fltCat_api_so_referencia"]) == g) for g in ALVO}
    for g, n in falta.items():
        por_icao: dict[str, list[dict]] = defaultdict(list)
        for l in linhas:
            if grupo(l["fltCat_api_so_referencia"]) == g and l["metar_bruto"] not in usados:
                por_icao[l["icao"]].append(l)
        for lista in por_icao.values():
            rnd.shuffle(lista)
        icaos = sorted(por_icao)
        rnd.shuffle(icaos)
        while n > 0 and any(por_icao.values()):  # um por aeródromo por volta: espalha a amostra
            for icao in icaos:
                if n > 0 and por_icao[icao]:
                    l = por_icao[icao].pop()
                    escolhidos.append(l)
                    usados.add(l["metar_bruto"])
                    n -= 1

    rnd.shuffle(escolhidos)  # ordem misturada: não agrupar por categoria
    return escolhidos[:TOTAL]


FONTE = Font(name="Arial", size=11)
NEGRITO = Font(name="Arial", size=11, bold=True)
MONO = Font(name="Courier New", size=11)
PREENCHER = PatternFill("solid", fgColor="FFFF00")
CABECALHO = PatternFill("solid", fgColor="D9E1F2")
LINHA = Border(bottom=Side(style="thin", color="BFBFBF"))


def planilha(casos: list[dict]) -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "Rotulagem"
    colunas = [("n", 5), ("ICAO", 8), ("Observação (UTC)", 19), ("METAR bruto", 78),
               ("Categoria API (EUA, só referência)", 18), ("Veredito do grupo", 18), ("Nota (opcional)", 36)]
    for j, (nome, largura) in enumerate(colunas, start=1):
        c = ws.cell(row=1, column=j, value=nome)
        c.font, c.fill = NEGRITO, CABECALHO
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[c.column_letter].width = largura
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = "A2"

    for i, caso in enumerate(casos, start=2):
        valores = [caso["n"], caso["icao"], caso["obs_utc"].replace("T", " ").replace(":00Z", "Z"),
                   caso["metar_bruto"], caso["fltCat_api"], None, None]
        for j, v in enumerate(valores, start=1):
            c = ws.cell(row=i, column=j, value=v)
            c.font = MONO if j == 4 else FONTE
            c.alignment = Alignment(wrap_text=(j == 4), vertical="center")
            c.border = LINHA
        ws.cell(row=i, column=6).fill = PREENCHER
        ws.cell(row=i, column=7).fill = PREENCHER

    ultima = len(casos) + 1
    dv = DataValidation(type="list", formula1=f'"{",".join(VEREDITOS)}"', allow_blank=True,
                        showErrorMessage=True, errorTitle="Veredito", error="Use VMC, IMC ou INVALIDO.")
    ws.add_data_validation(dv)
    dv.add(f"F2:F{ultima}")

    leg = wb.create_sheet("Instruções")
    leg.column_dimensions["A"].width = 26
    leg.column_dimensions["B"].width = 100
    linhas = [
        ("O que preencher", "Só as células amarelas da aba Rotulagem: coluna F (Veredito do grupo) e, se quiser, G (Nota)."),
        ("Valores da coluna F", "VMC, IMC ou INVALIDO (lista suspensa)."),
        ("Regra (ICA 100-1, 3.1.1)", "VMC se teto ≥ 1500 ft E visibilidade ≥ 5000 m; senão IMC. "
                                     "Teto = camada BKN, OVC ou VV mais baixa (FEW/SCT não são teto). CAVOK = VMC. "
                                     "9999 = 10 km ou mais."),
        ("INVALIDO", "Dado ilegível ou faltando para decidir (por exemplo //// no lugar de visibilidade ou nuvens)."),
        ("Categoria da API", "Critério americano (VFR/MVFR/IFR/LIFR), diferente do nosso. Só referência: não é gabarito."),
        ("Não usar", "O veredito do sistema (harness). O gabarito tem de vir do grupo."),
        ("", ""),
        ("Exemplo de linha preenchida", ""),
    ]
    for i, (a, b) in enumerate(linhas, start=1):
        leg.cell(row=i, column=1, value=a).font = NEGRITO
        c = leg.cell(row=i, column=2, value=b)
        c.font, c.alignment = FONTE, Alignment(wrap_text=True, vertical="top")
    exemplo = [("METAR bruto", "METAR SBRJ 101200Z 20006KT 9999 BKN015 24/19 Q1016"),
               ("Veredito do grupo", "VMC"),
               ("Nota", "teto exatamente 1500 ft (limite inclusivo); vis 10 km")]
    for k, (a, b) in enumerate(exemplo, start=len(linhas) + 1):
        leg.cell(row=k, column=1, value=a).font = FONTE
        c = leg.cell(row=k, column=2, value=b)
        c.font = MONO if a == "METAR bruto" else FONTE
        if a != "METAR bruto":
            c.fill = PREENCHER
    return wb


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--forcar", action="store_true", help="sobrescreve a planilha existente (perde os rótulos)")
    a = p.parse_args()
    if SAIDA.exists() and not a.forcar:
        print(f"{SAIDA.relative_to(BASE.parent)} já existe (pode ter rótulos). Use --forcar para gerar de novo.")
        return 1

    with COLETA.open(encoding="utf-8") as f:
        linhas = [l for l in csv.DictReader(f) if l["metar_bruto"].strip()]
    casos = [{"n": i, "icao": l["icao"], "obs_utc": l["obs_utc"], "metar_bruto": l["metar_bruto"],
              "fltCat_api": l["fltCat_api_so_referencia"]} for i, l in enumerate(escolher(linhas), start=1)]
    planilha(casos).save(SAIDA)

    cont = defaultdict(int)
    for c in casos:
        cont[c["fltCat_api"]] += 1
    print(f"{len(casos)} casos ({dict(cont)}) -> {SAIDA.relative_to(BASE.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
