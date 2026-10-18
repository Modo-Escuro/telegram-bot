# Decisões para execução do plano

[Plano](plano-conversacional.md) · [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5) · [StRS preservada](baseline/stakeholder-requirements-specification.md).

Registro inicial: propostas não são decisões aceitas. Responsáveis abaixo são papéis sugeridos; ninguém foi atribuído a uma issue sem indicação da equipe. Registrar autor humano/data/evidência quando cada decisão for fechada.

| ID | Estado | Pergunta / proposta | Responsabilidade sugerida | Bloqueia |
| --- | --- | --- | --- | --- |
| DA01 | Adiada | Taxonomia e janela de perfil por histórico; fora da primeira compra | Produto | FUT-01 |
| DA02 | Pendente | Pesos, dados ausentes, economia/rapidez: prioridade ponderada ou ordenação estrita? | Produto + domínio | RANK-03 |
| DA03 | Pendente | Canal, fonte, abrangência e validade da confirmação rastreável do restaurante | Produto + integração | Liberação de informação alimentar desconhecida |
| DA04 | Pendente | Rateio determinístico de frete/taxa/desconto, arredondamento e conciliação dos tetos | Produto + domínio | Validação de orçamento individual/coletivo |
| DA05 | Parcial | Organizador único privado já implementado; direitos sobre dados dos participantes ainda precisam ser definidos | Produto | DATA-01 e autorização de grupo |
| DA06 | Pendente | Proposta de uma loja/endereço/pagamento e uma compra ativa; cobertura parcial sempre visível | Produto + domínio | Composição e escopo da demo |
| DA07 | Pendente | Retenção, correção, expurgo e dados enviados ao modelo; sem memória entre compras por padrão proposto | Produto + backend | DATA-01, AI-01 e operação |
| DA08 | Pendente | Valores-alvo de latência, custo e qualidade; corpus e critérios de aprovação do modelo | Qualidade + produto | AI-01 e QA-01 |
| DA09 | Pendente por operação | Ferramentas/inputs/outputs/escopos observados; não confundir tools/list com execução | Integração | INT-01, CART-01 e BUY-02 |
| DA10 | Pendente | Estado final do evento: sacola, pedido, pagamento e ambiente autorizado | Produto + mentoria | Critério final do épico |
| TEC-01 | Proposta | Um worker/processo com armazenamento transacional durável; múltiplos processos exigem coordenação apropriada | Backend | DATA-01/RUN-01 |
| TEC-02 | Pendente | Modelo/provedor e tratamento de dados, após avaliação sintética | Backend + produto | AI-02 |
| TEC-03 | Proposta | Contrato versionado de aceitação/consulta de eventos e ações opacas | API + bot | API-01 |

## Comportamento enquanto decisões faltarem

- Não inventar evidência alimentar; manter bloqueio da pessoa afetada.
- Não declarar orçamento individual validado sem rateio definido.
- Não ativar memória permanente, multiusuário ou múltiplos restaurantes implicitamente.
- Não enviar pedido sem contrato externo e revisão humana válida.
- Pode desenvolver contrato, testes e protótipos isolados, marcando hipóteses e bloqueios.

## Modelo de registro

Decisão / estado / alternativa escolhida / alternativas descartadas / justificativa / responsável humano / data / evidência / requisitos e tarefas afetados / estratégia de reversão.

Alterar prioridade do backlog não altera a StRS. Se requisitos forem revisados formalmente, sincronizar seus artefatos pelos procedimentos do projeto e preservar a versão anterior.
