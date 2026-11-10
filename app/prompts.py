"""Prompt de sistema e esquemas das ferramentas (Prompt Engineering).

Especificação: specs/03-agente/requisitos.md (REQ-A-12) e design.md, seção 4.
Mudou o texto? Crie PROMPT_SISTEMA_V2, aponte PROMPT_SISTEMA para ele e troque VERSAO_PROMPT
(o traço registra a versão usada em cada execução).
"""

VERSAO_PROMPT = "v1"

PROMPT_SISTEMA_V1 = """\
Você é um assistente de briefing meteorológico VFR para aeródromos brasileiros, usado em um projeto acadêmico.

Como trabalhar:
1. Identifique os aeródromos citados na pergunta e converta cada um para o código ICAO de 4 letras.
2. Chame buscar_metar para CADA aeródromo antes de responder. Não responda sem consultar.
3. O resultado traz o campo "veredito" (VMC, IMC ou RECUSA), calculado por um módulo de regras.
   Use esse veredito exatamente como veio. Nunca recalcule nem contradiga.
4. Se o veredito for RECUSA, diga apenas o motivo informado.
5. Na explicação, cite o teto (teto_ft), a visibilidade (vis_m) e o METAR (metar_bruto) que vieram da
   ferramenta. Não invente nenhum dado que não esteja no resultado.
6. buscar_taf é só informativo: o TAF não muda o veredito.

Responda em português do Brasil, em no máximo 4 frases. Termine lembrando que a consulta não substitui o
briefing oficial (REDEMET/AIS) nem a decisão do piloto em comando.
"""

PROMPT_SISTEMA = PROMPT_SISTEMA_V1

LEMBRETE_FERRAMENTA = "Antes de responder, consulte buscar_metar para cada aeródromo citado na pergunta."

AVISO = "Ferramenta acadêmica. Não substitui o briefing meteorológico oficial."

_PARAMETRO_ICAO = {
    "type": "object",
    "properties": {
        "icao": {
            "type": "string",
            "description": "Código ICAO de 4 letras do aeródromo brasileiro (ex.: o código de Guarulhos).",
        }
    },
    "required": ["icao"],
}

FERRAMENTAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "buscar_metar",
            "description": "Busca o METAR atual do aeródromo e devolve o veredito VMC/IMC/RECUSA calculado "
                           "por regras, com teto, visibilidade e o METAR bruto.",
            "parameters": _PARAMETRO_ICAO,
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_taf",
            "description": "Busca o TAF (previsão) do aeródromo. Informativo: não muda o veredito.",
            "parameters": _PARAMETRO_ICAO,
        },
    },
]
