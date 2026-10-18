# CART-01 — Revisão e confirmação no Telegram

Incremento de código sobre `main@d239edd43d072198367fd2fda3846fa29774ba65` (#16 já mergeado), dependente da API [#46](https://github.com/Modo-Escuro/api-backend/pull/46). Publicação em PR não significa integração na main, deploy ou execução real. `TELEGRAM_CART_ENABLED=false` é o padrão; exige conversa habilitada quando ativado. Nenhuma configuração da Railway foi alterada.

## Comportamento implementado

- **Revisar carrinho** consulta o backend em worker separado, sem escrever no MCP. Apresenta composição desejada, quantidades, preços observados em centavos, destinatários/restrições, orçamento coletivo e custos anteriores quando conhecidos. O total posterior continua desconhecido.
- **Preparar este carrinho** é um callback independente do modelo e da aprovação do login. Valida organizador, bot, conversa privada, mensagem original, vínculo, versão e prazo de cinco minutos. Backend revalida a revisão e consome a referência junto da intenção persistente PREPARE_CART. Pedido/pagamento permanecem bloqueados.
- **Conferir carrinho** consulta apenas `GET cart-writes/requests/:requestId`. Recupera o estado técnico da preparação; ainda não apresenta a composição/custos finais do carrinho. Não é aprovação de compra.

Referência de confirmação fica só na RAM; botão contém outro identificador aleatório, sem referência da API. SQLite armazena apenas escopo, requestId, hash do callback, fase e instante. Não guarda composição, nomes, restrições, referência ou texto da revisão. Alteração de conversa invalida o botão; reinício descarta referências em RAM.

O marcador PENDING é gravado antes de agendar a confirmação. POST é enviado uma única vez; timeout/erro de protocolo após envio consulta o mesmo requestId por GET. Resultado desconhecido, inclusive GET 404 após resposta perdida, permanece bloqueado. Reinício não retoma POST. Erros remotos não são exibidos nem registrados com seu corpo. Sessões por senha preservam bancos, escopos e credenciais separados e um único polling.

## Limites desta entrega

Este é um incremento de CART-01/BOT-03. Escolher/corrigir propostas por botões, revisão final de composição/custos, seleção de entrega e experiência completa da BOT-03 continuam pendentes. O texto conversacional ainda chama a composição local de sacola simulada; só o caminho separado PREPARE_CART pode sincronizar itens após confirmação.

Opções sem rótulos humanos, remoções de itens sem identificação e revisão que exceda uma mensagem de 3500 bytes bloqueiam o botão. Não truncar conteúdo para obter aprovação. A identificação legível de loja/endereço/conta na revisão precisa ser completada antes da ativação; o backend vincula IDs, mas IDs técnicos não substituem uma revisão humana suficiente. Não ativar esta interface enquanto essa lacuna permanecer.

Sem outputs autenticados revisados de `createCart/getCart` e mutações, o gate INT-02 da API impede operação. Lista de ferramentas, scopes e testes sintéticos não comprovam iFood. Sem reconciliação remota confiável, RESULT_UNKNOWN não é liberado por uma leitura semelhante ao esperado.

## Validação offline

`python -m unittest discover -s tests -v`: **209 aprovados, 7 ignorados, 216 no total**. Ruff check/format dos arquivos alterados e `git diff --check` aprovados. Os 18 testes CART-01 incluem confirmação uma vez, roteamento fora do modelo, origem/replay, expiração, mudança de versão, timeout/reinício, ausência de dados pessoais no SQLite, custos/orçamento visíveis e protocolo malformado sem encerrar polling. Transportes/MCP/modelo são falsos; não houve polling ou escrita real. A integração HTTP completa bot→CART-01 ainda requer ensaio próprio; os pins históricos RUN-01 foram preservados e seus 7 testes exigem checkout fixado.

Auditoria independente autorizada pelo usuário inspecionou o diff e executou regressores/probes, sem editar fontes. Parecer limitado a draft com flags OFF, sem bloqueadores nesse recorte. Não é GO de ativação ou conclusão de BOT-03/INT-02/QA-01.
