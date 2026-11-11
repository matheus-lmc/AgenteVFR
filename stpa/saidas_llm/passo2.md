<!-- Saída do llama3.1:8b, SEM EDIÇÃO. Passo 2 — Estrutura de controle. 47 s, 1492 tokens de entrada, 476 de saída. -->

**Lista dos componentes em ordem hierárquica**

1. Piloto (usuário)
2. Interface Web
3. Agente
4. Harness (código determinístico)
5. API meteorológica pública (aviationweather.gov)

**Tabela de ações de controle e realimentações**

| De | Para | Tipo | Descrição |
| --- | --- | --- | --- |
| Piloto | Agente | Ação de Controle | Enviar pergunta ao Agente |
| Agente | Harness | Ação de Controle | Chamar ferramentas para obter dados meteorológicos |
| Agente | Interface Web | Ação de Controle | Enviar veredito e explicação ao Interface Web |
| Agente | Harness | Realimentação | Receber dados meteorológicos do Harness |
| Interface Web | Piloto | Realimentação | Mostrar veredito e explicação ao Piloto |
| Harness | Agente | Realimentação | Enviar dados meteorológicos ao Agente |
| API meteorológica pública | Harness | Realimentação | Enviar METAR e TAF ao Harness |

**Tabela de modelo de processo de cada controlador**

| Controlador | Modelo de Processo |
| --- | --- |
| Piloto | Receber pergunta, enviar pergunta ao Agente, receber veredito e explicação do Agente, tomar decisão de voo |
| Agente | Receber pergunta do Piloto, chamar ferramentas para obter dados meteorológicos, receber dados meteorológicos do Harness, calcular veredito e explicação, enviar veredito e explicação ao Interface Web |
| Interface Web | Receber veredito e explicação do Agente, mostrar veredito e explicação ao Piloto |
| Harness | Receber chamada de ferramentas do Agente, obter dados meteorológicos, calcular veredito e explicação, enviar dados meteorológicos ao Agente |
| API meteorológica pública | Receber chamada de dados do Harness, enviar METAR e TAF ao Harness |

Observação: O modelo de processo de cada controlador é uma descrição simplificada das ações e responsabilidades de cada componente.
