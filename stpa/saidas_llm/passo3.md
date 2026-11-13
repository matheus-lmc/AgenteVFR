<!-- Saída do llama3.1:8b, SEM EDIÇÃO. Passo 3 — Ações de controle inseguras (UCAs). 86 s, 2145 tokens de entrada, 790 de saída. -->

**Tabela de Ações de Controle Inseguras (UCAs)**

| ID | Ação de Controle | Categoria | Descrição da UCA | Perigos |
| --- | --- | --- | --- | --- |
| UCA1 | CA1 (Piloto -> Agente) | a | Não fornecer pergunta ao Agente | H1, H2 |
| UCA2 | CA2 (Agente -> Harness) | b | Fornecer pergunta ao Agente que causa perigo (ex: pergunta com palavras de planejamento IFR) | H1, H2 |
| UCA3 | CA3 (Agente -> Interface Web) | c | Fornecer veredito e explicação ao Interface Web antes de calcular veredito e explicação | H3, H4 |
| UCA4 | CA4 (Agente -> Harness) | d | Parar de chamar ferramentas do Agente antes de obter dados meteorológicos | H5, H6 |
| UCA5 | CA5 (Harness -> Agente) | a | Não fornecer dados meteorológicos ao Agente | H7, H8 |
| UCA6 | CA6 (Harness -> Agente) | b | Fornecer dados meteorológicos ao Agente que causam perigo (ex: METAR com mais de 60 min) | H7, H8 |
| UCA7 | CA7 (Agente -> Interface Web) | c | Enviar veredito e explicação ao Interface Web antes de calcular veredito e explicação | H3, H4 |
| UCA8 | CA8 (Agente -> Interface Web) | d | Parar de enviar veredito e explicação ao Interface Web antes de calcular veredito e explicação | H5, H6 |
| UCA9 | CA9 (Interface Web -> Piloto) | a | Não fornecer veredito e explicação ao Piloto | H1, H2 |
| UCA10 | CA10 (Interface Web -> Piloto) | b | Fornecer veredito e explicação ao Piloto que causa perigo (ex: veredito IMC e texto "dá pra voar visual") | H1, H2 |
| UCA11 | CA11 (API meteorológica pública -> Harness) | a | Não fornecer METAR e TAF ao Harness | H7, H8 |
| UCA12 | CA12 (API meteorológica pública -> Harness) | b | Fornecer METAR e TAF ao Harness que causam perigo (ex: METAR com mais de 60 min) | H7, H8 |
| UCA13 | CA13 (Harness -> Agente) | c | Enviar dados meteorológicos ao Agente antes de calcular veredito e explicação | H5, H6 |
| UCA14 | CA14 (Harness -> Agente) | d | Parar de enviar dados meteorológicos ao Agente antes de calcular veredito e explicação | H7, H8 |
| UCA15 | CA15 (Agente -> Interface Web) | c | Enviar veredito e explicação ao Interface Web antes de calcular veredito e explicação | H3, H4 |
| UCA16 | CA16 (Agente -> Interface Web) | d | Parar de enviar veredito e explicação ao Interface Web antes de calcular veredito e explicação | H5, H6 |

Observação: As UCAs são identificadas considerando as ações de controle e as categorias de insegurança. As UCAs são listadas em ordem crescente de número.
