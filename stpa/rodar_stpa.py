"""STPA assistido pelo Llama (specs/07-stpa/plano.md).

Manda ao llama3.1:8b do Compose quatro prompts em sequência (uma conversa só: cada passo vê as respostas
anteriores) e grava cada resposta SEM EDIÇÃO em stpa/saidas_llm/passo<N>.md. Os prompts exatos vão para
stpa/prompts_stpa.md. A revisão do grupo fica em stpa/stpa.md, nunca aqui.

O Llama NÃO recebe a lista de perigos que o grupo já tinha (H1–H10), para dar para comparar.

Uso:
    python stpa/rodar_stpa.py            # precisa do Ollama em OLLAMA_URL (padrão http://localhost:11434)
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BASE = Path(__file__).resolve().parent
SAIDAS = BASE / "saidas_llm"
URL = os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")
MODELO = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OPCOES = {"temperature": 0.1, "seed": 42, "num_thread": int(os.environ.get("OLLAMA_NUM_THREAD", 4)),
          "num_ctx": 8192}  # 8k: o passo 4 leva as respostas dos passos 1–3 na janela

SISTEMA = """\
Você é um analista de segurança de sistemas que aplica o método STPA (System-Theoretic Process Analysis, de Nancy
Leveson). Responda em português do Brasil, em tabelas markdown, de forma objetiva. Analise só o sistema descrito;
não invente componentes que não existem.

DESCRIÇÃO DO SISTEMA — AgenteVFR (protótipo acadêmico)

Propósito: ajudar um piloto a saber se as condições meteorológicas de um aeródromo brasileiro permitem voo visual
(VFR). Perguntas típicas: "dá pra ir VFR de Guarulhos pra Congonhas agora?" e "qual a melhor janela para voar VFR
em Curitiba nas próximas horas?". Não substitui o briefing meteorológico oficial nem a decisão do piloto em comando.

Componentes:
1. Piloto (usuário): escreve a pergunta em linguagem natural e decide se voa.
2. Interface web: mostra o veredito (VMC verde, IMC vermelho, RECUSA cinza) com o motivo, a explicação, a lista de
   aeródromos consultados (código ICAO e nome da estação), o METAR bruto e um traço técnico da execução. Tem um
   aviso fixo de que não substitui o briefing oficial.
3. Agente: modelo de linguagem llama3.1:8b rodando local, com chamada de ferramentas. Ele decide: interpretar a
   pergunta, mapear nomes de aeródromos para códigos ICAO, quais ferramentas chamar e em que ordem
   (buscar_metar, avaliar_janela), e redigir a explicação para o piloto. Recebe de volta só um resumo compacto
   (ICAO, horário, idade, visibilidade, teto, camadas, veredito, motivo, METAR bruto, nome da estação).
   Limite de 5 chamadas de ferramenta por pergunta.
4. Harness (código determinístico, o modelo não consegue alterar):
   - pré-filtro da pergunta por palavras: recusa planejamento IFR, "mesmo assim", pedidos para ignorar a regra e
     previsão além da validade do TAF;
   - decodifica o METAR bruto e calcula o veredito: VMC se teto (camada BKN, OVC ou VV mais baixa) >= 1500 ft E
     visibilidade >= 5000 m; senão IMC;
   - recusa: METAR com mais de 60 min, METAR ausente/NIL/ilegível (////), código ICAO inexistente, aeródromo fora
     do Brasil (prefixos ICAO SB, SD, SI, SJ, SN, SS, SW);
   - verificador de contradição por regras de palavras: se a explicação do modelo contradiz o veredito (ex.:
     veredito IMC e texto "dá para voar visual"), ou cita aeródromo não consultado, a explicação é bloqueada e
     trocada por um texto gerado em código; o bloqueio é registrado;
   - decodifica o TAF e calcula VMC/IMC por hora dentro da validade (TEMPO e PROB30/40 contam como pior caso) para
     indicar a melhor janela; isso é previsão, mostrada separada do veredito de agora;
   - o veredito exibido vem sempre do código, nunca do texto do modelo.
5. API meteorológica pública (aviationweather.gov): fornece METAR e TAF; o sistema guarda cache de 5 min.
"""

PASSOS = [
    ("Passo 1 — Perdas e perigos",
     "Passo 1 do STPA. Identifique as PERDAS (L1, L2, ...) inaceitáveis para os envolvidos e os PERIGOS no nível "
     "do sistema (H1, H2, ...). Perigo = estado ou condição do sistema que, junto com condições do ambiente, leva "
     "a uma perda. Cada perigo deve indicar a(s) perda(s) a que leva. No máximo 4 perdas e 8 perigos. "
     "Formato: uma tabela de perdas (id, perda) e uma tabela de perigos (id, perigo, perdas)."),
    ("Passo 2 — Estrutura de controle",
     "Passo 2 do STPA. Modele a ESTRUTURA DE CONTROLE hierárquica do sistema: quem são os controladores e os "
     "processos controlados, as AÇÕES DE CONTROLE (de cima para baixo) e as REALIMENTAÇÕES (de baixo para cima), e "
     "o que cada controlador precisa saber (modelo de processo). Formato: (a) lista dos componentes em ordem "
     "hierárquica; (b) tabela com colunas: de, para, tipo (ação de controle ou realimentação), descrição; "
     "(c) tabela com o modelo de processo de cada controlador. Numere as ações de controle como CA1, CA2, ..."),
    ("Passo 3 — Ações de controle inseguras (UCAs)",
     "Passo 3 do STPA. Para as ações de controle do passo 2, identifique as AÇÕES DE CONTROLE INSEGURAS (UCA) nas "
     "quatro categorias: (a) não fornecida causa perigo; (b) fornecida causa perigo; (c) fornecida cedo, tarde ou "
     "fora de ordem; (d) parada cedo demais ou aplicada por tempo demais. Pule combinações que não fazem sentido. "
     "No máximo 16 UCAs. Formato: tabela com colunas: id (UCA1, ...), ação de controle (CAn), categoria (a/b/c/d), "
     "descrição da UCA (contexto em que é insegura), perigos (Hn)."),
    ("Passo 4 — Cenários causais",
     "Passo 4 do STPA. Para cada UCA do passo 3, escreva um CENÁRIO CAUSAL: por que essa ação insegura poderia "
     "acontecer (falha ou limitação do controlador, modelo de processo errado, realimentação ausente ou errada, "
     "dado errado vindo da API, interação entre componentes). Depois diga qual mecanismo do sistema descrito "
     "mitiga o cenário, ou escreva 'não mitigado' se nenhum mitiga. Formato: tabela com colunas: id (CS1, ...), "
     "UCA, cenário causal, mecanismo que mitiga, mitigado? (sim / parcial / não)."),
]


def conversar(mensagens: list[dict]) -> dict:
    corpo = {"model": MODELO, "messages": mensagens, "stream": False, "options": OPCOES}
    r = httpx.post(f"{URL}/api/chat", json=corpo, timeout=1800)
    r.raise_for_status()
    return r.json()


def main() -> int:
    SAIDAS.mkdir(parents=True, exist_ok=True)
    mensagens = [{"role": "system", "content": SISTEMA}]
    execucao = {"inicio": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "modelo": MODELO,
                "opcoes": OPCOES, "passos": []}

    prompts_md = ["# Prompts do STPA (enviados ao Llama exatamente assim)", "",
                  f"Gerado por `stpa/rodar_stpa.py`. Modelo `{MODELO}`, opções `{json.dumps(OPCOES)}`. "
                  "Uma conversa só: cada passo recebe as respostas dos anteriores.", "",
                  "## Mensagem de sistema", "", "```text", SISTEMA.rstrip(), "```", ""]
    for i, (titulo, pedido) in enumerate(PASSOS, start=1):
        prompts_md += [f"## {titulo}", "", "```text", pedido, "```", ""]
    (BASE / "prompts_stpa.md").write_text("\n".join(prompts_md), encoding="utf-8")

    for i, (titulo, pedido) in enumerate(PASSOS, start=1):
        mensagens.append({"role": "user", "content": pedido})
        t0 = time.perf_counter()
        dados = conversar(mensagens)
        texto = dados["message"].get("content") or ""
        mensagens.append({"role": "assistant", "content": texto})
        duracao = round(time.perf_counter() - t0)
        (SAIDAS / f"passo{i}.md").write_text(
            f"<!-- Saída do {MODELO}, SEM EDIÇÃO. {titulo}. {duracao} s, "
            f"{dados.get('prompt_eval_count')} tokens de entrada, {dados.get('eval_count')} de saída. -->\n\n"
            + texto + "\n", encoding="utf-8")
        execucao["passos"].append({"passo": i, "titulo": titulo, "duracao_s": duracao,
                                   "prompt_eval_count": dados.get("prompt_eval_count"),
                                   "eval_count": dados.get("eval_count")})
        print(f"{titulo}: {duracao} s, {dados.get('prompt_eval_count')} + {dados.get('eval_count')} tokens",
              flush=True)

    (SAIDAS / "execucao.json").write_text(json.dumps(execucao, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
