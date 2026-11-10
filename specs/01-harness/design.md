# 01 — Harness: design

**Estado:** aprovado em 10/11/2026 · **Requisitos:** [requisitos.md](requisitos.md) (aprovado)

## 1. Princípios

- **Só biblioteca padrão** (`re`, `datetime`, `dataclasses`, `enum`, `unicodedata`). Sem pydantic, httpx ou
  Ollama neste módulo: o harness não tem como chamar o modelo nem a rede (REQ-H-11).
- **Funções puras**: toda entrada vem por parâmetro, inclusive `agora`. Nada de estado global mutável.
- **Erros de programação ≠ recusa**: `agora` sem fuso horário gera `ValueError` (bug de quem chamou);
  dado meteorológico ruim gera `RECUSA` (comportamento esperado).

## 2. Arquivos

```
app/__init__.py
app/harness.py          # único módulo de produção desta etapa
tests/test_harness.py
pyproject.toml          # só [tool.pytest.ini_options] pythonpath = ["."]
```

## 3. API pública

```python
# --- Constantes (REQ-H-10) — ICA 100-1, item 3.1.1 [pendência: conferir texto vigente]
TETO_MIN_FT = 1500
VIS_MIN_M = 5000
IDADE_MAX_MIN = 60
TOLERANCIA_FUTURO_MIN = 5
PREFIXOS_BR = ("SB", "SD", "SI", "SJ", "SN", "SS", "SW")

class Veredito(str, Enum):
    VMC = "VMC"
    IMC = "IMC"
    RECUSA = "RECUSA"

@dataclass(frozen=True)
class Resumo:                      # REQ-H-12 — os campos SÃO as chaves; nada além disso
    icao: str | None
    tipo: str | None               # "METAR" | "SPECI"
    horario_utc: str | None        # ISO 8601, ex.: "2026-11-10T12:00:00Z"
    idade_min: int | None
    vis_m: int | None
    teto_ft: int | None            # None = sem teto
    camadas: list[str]             # ex.: ["FEW030", "SCT100"]; [] se não houver
    veredito: str                  # "VMC" | "IMC" | "RECUSA"
    motivo: str                    # texto legível em português
    metar_bruto: str
    def para_dict(self) -> dict: ...

@dataclass(frozen=True)
class Resultado:
    veredito: Veredito
    codigo_recusa: str | None      # ex.: "dado_desatualizado"; None se VMC/IMC
    resumo: Resumo

@dataclass(frozen=True)
class RecusaPergunta:              # REQ-H-13
    categoria: str                 # "pedido_ifr" | "pressao_operacional" | ...
    termo: str                     # termo que disparou
    motivo: str

@dataclass(frozen=True)
class Verificacao:                 # REQ-H-14/15
    texto_final: str               # o que vai para a interface
    origem: str                    # "modelo" | "texto_modelo"
    bloqueada: bool                # True só quando houve contradição ou texto vazio
    regra: str | None              # ex.: "imc_com_afirmacao_favoravel"
    trecho: str | None             # trecho da explicação que disparou

def avaliar_metar(metar_bruto: str, icao_solicitado: str, agora: datetime) -> Resultado
def prefiltrar_pergunta(pergunta: str) -> RecusaPergunta | None
def verificar_explicacao(explicacao: str, resumo: Resumo) -> Verificacao
def texto_modelo(resumo: Resumo) -> str
```

## 4. `avaliar_metar` — algoritmo

### 4.1 Normalização
`strip()`, remover `=` final, `upper()`, `split()` (resolve espaços repetidos e quebras de linha).
`metar_bruto` no resumo = texto original sem espaços nas pontas.

### 4.2 Cabeçalho (posicional) e ordem das checagens

| # | Passo | Recusa |
|---|---|---|
| 1 | token 0 ∈ {METAR, SPECI} → tipo; senão tipo = METAR e não consome token. `COR` opcional. | — |
| 2 | próximo token casa `^[A-Z]{4}$` → ICAO | `formato_invalido` |
| 3 | ICAO começa com prefixo brasileiro | `fora_do_escopo` |
| 4 | ICAO == `icao_solicitado.upper()` | `icao_divergente` |
| 5 | próximo token casa `^(\d{2})(\d{2})(\d{2})Z$`, HH ≤ 23, MM ≤ 59, dia existe no mês deduzido | `formato_invalido` |
| 6 | próximo token == `NIL` | `sem_dado` |
| 7 | observação − agora > 5 min | `horario_futuro` |
| 8 | agora − observação > 60 min | `dado_desatualizado` |
| 9 | `AUTO` opcional; decodificar o corpo (4.3) | `visibilidade_indisponivel`, `teto_indisponivel`, `nuvens_indisponiveis` |
| 10 | regra VMC/IMC (4.4) | — |

> A ordem desta tabela é a do REQ-H-02 revisado em 10/11/2026: ICAO (passo 2) e horário (passo 5) são
> checados separadamente para que `METAR KJFK ...` dê `fora_do_escopo` mesmo com horário inválido.

**Mês deduzido (REQ-H-06):** se `DD > agora.day`, mês anterior (janeiro → dezembro do ano anterior); senão,
mês de `agora`. `datetime(...)` lançando `ValueError` (ex.: dia 31 em mês de 30) → `formato_invalido`.

**Idade:** comparação feita com `timedelta` exato (60 min e 1 s já recusa). `idade_min` no resumo =
minutos inteiros (piso), com mínimo 0 (horário até 5 min no futuro aparece como 0).

### 4.3 Corpo
Tokens após o cabeçalho, até o primeiro de `RMK`, `BECMG`, `TEMPO`, `NOSIG` (REQ-H-07). Cada token é
classificado pela primeira regra que casar; os demais são ignorados.

| Grupo | Padrão | Uso |
|---|---|---|
| CAVOK | `CAVOK` | vis = 10000, sem teto |
| Visibilidade predominante | `^(\d{4})(NDV)?$` — **primeira** ocorrência | vis_m (`9999` → 10000) |
| Visibilidade mínima (D1) | `^\d{4}(N\|NE\|E\|SE\|S\|SW\|W\|NW)$` | ignorada |
| Visibilidade indisponível | `^////$` | marca vis indisponível |
| Nuvem | `^(FEW\|SCT\|BKN\|OVC\|///)(\d{3}\|///)(CB\|TCU\|///)?$` | camadas |
| Visibilidade vertical | `^VV(\d{3}\|///)$` | camadas (conta como teto) |
| Sem nuvem significativa | `NSC`, `NCD`, `SKC`, `CLR` | sem teto |

Por que o padrão de visibilidade não confunde outros grupos: vento termina em `KT`/`MPS`, temperatura tem `/`,
pressão começa com `Q`, RVR com `R`. O primeiro grupo de 4 dígitos puros do corpo é sempre a visibilidade.

**Validação (passo 9, nesta ordem):**
1. sem `CAVOK` e (sem visibilidade ou vis `////`) → `visibilidade_indisponivel`;
2. alguma camada BKN/OVC/VV com altura `///`, ou cobertura `///` → `teto_indisponivel` (D2);
3. nenhuma camada, sem `CAVOK` e sem `NSC/NCD/SKC/CLR` → `nuvens_indisponiveis` (D3).

**Teto** = `min(altura × 100)` das camadas BKN, OVC e VV; `None` se não houver.

### 4.4 Regra e motivo
```python
vmc = (teto_ft is None or teto_ft >= TETO_MIN_FT) and vis_m >= VIS_MIN_M
```
Formato do `motivo`:
- VMC: `"Teto 2100 ft (mínimo 1500 ft) e visibilidade 10000 m (mínimo 5000 m): dentro dos mínimos VFR."`
  (sem teto: `"Sem teto"`).
- IMC: lista só o que falhou — `"Teto 800 ft abaixo do mínimo de 1500 ft; visibilidade 4000 m abaixo do
  mínimo de 5000 m."`
- RECUSA: texto fixo por código (tabela 4.5).

### 4.5 Códigos de recusa

| Código | Motivo exibido |
|---|---|
| `formato_invalido` | Boletim em formato não reconhecido. |
| `fora_do_escopo` | Aeródromo fora do Brasil (prefixo ICAO não brasileiro). O sistema só atende aeródromos brasileiros. |
| `icao_divergente` | O boletim recebido é de outra estação (`X`), não da solicitada (`Y`). |
| `sem_dado` | Boletim NIL: estação sem observação disponível. |
| `horario_futuro` | Horário do boletim no futuro em relação ao relógio do sistema. |
| `dado_desatualizado` | Boletim com `N` min (máximo 60 min). |
| `visibilidade_indisponivel` | Visibilidade não informada no boletim. |
| `teto_indisponivel` | Altura ou cobertura de nuvens não informada (`///`). |
| `nuvens_indisponiveis` | Boletim sem informação de nuvens. |

No resumo de uma recusa, os campos já decodificados até o ponto da recusa são preenchidos; os outros ficam `null`.

## 5. `prefiltrar_pergunta`

- Normalização: `unicodedata.normalize("NFKD")`, remover acentos (categoria `Mn`), minúsculas.
- Termos num único dicionário `TERMOS_FORA_DE_ESCOPO: dict[str, list[str]]` (categoria → regex com `\b`),
  avaliado na ordem `manipulacao_regra`, `pressao_operacional`, `pedido_ifr`, `previsao_alem_taf`.
  Retorna a primeira categoria que casar.
- Regex com `\b` evita falso positivo de `IFR` dentro de outra palavra; `VFR` não casa com `\bifr\b`.
- Exemplos de padrões: `\bifr\b`, `\binstrumentos?\b`, `\bmesmo assim\b`, `\bassim mesmo\b`,
  `\bmesmo com\b`, `\bda um jeito\b`, `\bignor(e|a|ar|ando)\b`, `\bdesconsider\w*`,
  `\besquec\w* (a|as) regras?\b`, `\bfinj\w*`, `\bsem o harness\b`, `\bsemana que vem\b`,
  `\bproxima semana\b`, `\bdepois de amanha\b`, `\bdaqui a (\d+|dois|tres|quatro|cinco) dias\b`,
  `\bproxim[oa]s (\d+|dois|tres|quatro|cinco|seis|sete) dias\b`, `\bmes que vem\b`.
  (*"próximos N dias" acrescentado no portão 3 para cobrir a pergunta da demo — "melhor dia pra Miami nos
  próximos 5 dias".*)

## 6. `verificar_explicacao`

1. Veredito `RECUSA` → `Verificacao(texto_modelo(resumo), "texto_modelo", bloqueada=False, regra=None)`;
   a explicação é descartada (REQ-H-15). Não conta como bloqueio na avaliação.
2. Explicação vazia ou só espaços → bloqueada, regra `explicacao_vazia`.
3. Normaliza como no pré-filtro e procura expressões de duas listas:
   - `FAVORAVEL`: `da (para|pra) voar (visual|vfr)`, `condic(ao|oes) vmc`,
     `(em|esta|estao|e|sao) vmc`, `vfr liberado`, `pode voar (vfr|visual)`, `e possivel voar (vfr|visual)`,
     `favorave(l|is) (ao|para o) voo visual`;
   - `DESFAVORAVEL`: `condic(ao|oes) imc`, `(em|esta|estao|e|sao) imc`, `abaixo dos minimos`,
     `voo visual nao (e )?recomendado`.
   (*`são/estão/é` acrescentados no portão 3: "as condições são VMC" não casava.*)
4. **Polaridade**: cada ocorrência vale +1 (favorável) ou −1 (desfavorável). Se alguma das 3 palavras antes
   dela for `nao`, `nem`, `nunca` ou `jamais`, o sinal inverte. Assim "não é possível voar VFR" vira −1
   sem precisar de entrada própria na lista.
5. Contradição: veredito `IMC` e alguma ocorrência +1 → regra `imc_com_afirmacao_favoravel`;
   veredito `VMC` e alguma ocorrência −1 → regra `vmc_com_afirmacao_desfavoravel`.
   `trecho` = texto original da primeira ocorrência que disparou.
6. Bloqueada → `texto_final = texto_modelo(resumo)`, `origem = "texto_modelo"`.
   Aceita → `texto_final = explicacao`, `origem = "modelo"`.

**Falso bloqueio é aceitável** (direção segura): ex.: veredito IMC e o texto "para condições VMC seria
preciso teto de 1500 ft" é bloqueado e substituído pelo texto-modelo. Vai para a avaliação como métrica.

## 7. `texto_modelo`

```
VMC / IMC:  "{veredito} em {icao} — {motivo} Observação das {HH:MM}Z ({idade_min} min). METAR: {metar_bruto}"
RECUSA:     "Sem veredito para {icao ou 'o aeródromo'}: {motivo} Consulte o briefing oficial (REDEMET/AIS)."
```

## 8. Plano de testes

Agora fixo: `AGORA = datetime(2026, 11, 10, 12, 30, tzinfo=UTC)`. Helper `metar(texto, minutos_atras)`
troca o grupo `DDHHMMZ` do texto pelo horário `AGORA − minutos_atras`, para cumprir "horário relativo ao
agora do teste".

| Requisito | Testes previstos |
|---|---|
| — (aceite) | 10 casos obrigatórios do CLAUDE.md, parametrizados |
| H-01 | com/sem `=`; quebras de linha; sem tipo assume METAR; `COR`; ICAO ausente → `formato_invalido`; horário malformado → `formato_invalido` |
| H-02 | KJFK com resto inválido → `fora_do_escopo`; estrangeiro + desatualizado → `fora_do_escopo`; NIL + desatualizado → `sem_dado` |
| H-03 | cada um dos 7 prefixos aceito; `SA..`, `SC..`, `KJFK` recusados |
| H-04 | METAR de SBGR pedido como SBSP → `icao_divergente`; ICAO solicitado em minúsculas aceito |
| H-05 | `NIL` → `sem_dado` |
| H-06 | 60 min aceito; 61 min recusado; virada de mês (agora dia 1, boletim dia 31); virada de ano; dia inexistente → `formato_invalido`; 5 min no futuro aceito; 6 min recusado; `agora` sem fuso → `ValueError` |
| H-07 | `TEMPO ... BKN008` depois de um corpo VMC continua VMC; idem `BECMG` e `RMK`; `AUTO` aceito |
| H-08 | `9999` → 10000; `9999NDV`; `4000 1500NE` usa 4000; `////` → recusa; sem visibilidade → recusa |
| H-09 | BKN/OVC/VV; menor camada vence; `BKN030CB`; FEW/SCT ignorados; NSC/NCD/SKC/CLR; `BKN///` → recusa; `//////` → recusa; sem nuvens → recusa |
| H-10 | limites: teto 1400/1500 ft, vis 4900/5000 m; motivo cita o que falhou |
| H-11 | mesmo input → mesmo resultado; harness não importa httpx/ollama (checagem de imports) |
| H-12 | chaves exatas do `para_dict()`, em VMC, IMC e recusa; `teto_ft` null sem teto |
| H-13 | 1 exemplo por categoria; maiúsculas e acentos; "VFR" não dispara `pedido_ifr`; pergunta normal → `None` |
| H-14 | IMC + "dá para voar visual" bloqueia; IMC + "não dá para voar visual" passa; VMC + "abaixo dos mínimos" bloqueia; VMC + "não está abaixo dos mínimos" passa; VMC + "não é possível voar VFR" bloqueia; vazio bloqueia |
| H-15 | bloqueio devolve texto-modelo com veredito e METAR; registro tem regra e trecho; RECUSA descarta a explicação sem marcar bloqueio |

Estimativa: ~60 testes (contando parametrizações).
