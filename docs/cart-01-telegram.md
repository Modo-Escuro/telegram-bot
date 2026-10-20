# CART-01 — Revisão e confirmação no Telegram

**Continuação local de 18/10:** [conclusão offline integrada](cart-01-conclusao-offline.md) completa identificação de conta/loja/endereço, nomes das opções e remoções e apresentação dos custos finais. Os limites e testes abaixo conservam o histórico do draft original; não são o resultado da nova continuação nem evidência externa.

Origem: `main@d239edd43d072198367fd2fda3846fa29774ba65` e API [#46](https://github.com/Modo-Escuro/api-backend/pull/46). **Guia conferido na árvore local em 20/10:** revisão, callback e apresentação final existem em `cart.py`, `cart_client.py` e `cart_view.py`. `TELEGRAM_CART_ENABLED=false` é padrão e exige conversa quando ativado. API coordenada usa v5 e CART-01 com gate próprio; F7 foi retirada. Não houve nova consulta de PR/deploy/configuração online nesta atualização.

## Comportamento implementado

- **Revisar carrinho** consulta o backend em worker separado, sem escrever no MCP. Apresenta composição desejada, quantidades, preços observados em centavos, destinatários/restrições, orçamento coletivo e custos anteriores quando conhecidos. O total posterior continua desconhecido.
- **Preparar este carrinho** é um callback independente do modelo e da aprovação do login. Valida organizador, bot, conversa privada, mensagem original, vínculo, versão e prazo de cinco minutos. Backend revalida a revisão e consome a referência junto da intenção persistente PREPARE_CART. Pedido/pagamento permanecem bloqueados.
- **Conferir carrinho** recupera o estado técnico por `GET cart-writes/requests/:requestId` e, em SUCCEEDED/FAILED, consulta `GET cart-writes/current` para apresentar composição/custos atuais. Falha da consulta não repete confirmação nem muda o estado técnico reconhecido. Não é aprovação de compra.

Referência de confirmação fica só na RAM; botão contém outro identificador aleatório, sem referência da API. SQLite armazena apenas escopo, requestId, hash do callback, fase e instante. Não guarda composição, nomes, restrições, referência ou texto da revisão. Alteração de conversa invalida o botão; reinício descarta referências em RAM.

O marcador PENDING é gravado antes de agendar a confirmação. POST é enviado uma única vez; timeout/erro de protocolo após envio consulta o mesmo requestId por GET. Resultado desconhecido, inclusive GET 404 após resposta perdida, permanece bloqueado. Reinício não retoma POST. Erros remotos não são exibidos nem registrados com seu corpo. Sessões por senha preservam bancos, escopos e credenciais separados e um único polling.

## Limites desta entrega

Este é um incremento de CART-01/BOT-03. Revisão completa e apresentação de composição/custos observados já existem localmente. O assistente da API seleciona propostas numeradas por texto fixo, mas não emite os antigos botões guiados; o fio completo dessa nova sacola ao canal de revisão ainda exige verificação. Seleção de entrega/pagamento e envio final não são entregues aqui. Só PREPARE_CART pode sincronizar itens após confirmação e gate de evidência.

Opções sem rótulos humanos, remoções não identificadas e revisão acima de 3500 bytes UTF-8 bloqueiam o botão; não truncar para obter confirmação. A continuação implementou rótulos de conta mascarada/loja/endereço, opções/remoções e custos finais; seus campos ainda são validados em cada revisão. IDs técnicos não substituem descrição suficiente. Implementação local não confirma output iFood nem dá GO de ativação.

Sem outputs autenticados revisados de `createCart/getCart` e mutações, o gate INT-02 da API impede operação. Lista de ferramentas, scopes e testes sintéticos não comprovam iFood. Sem reconciliação remota confiável, RESULT_UNKNOWN não é liberado por uma leitura semelhante ao esperado.

## Registro histórico da validação original

`python -m unittest discover -s tests -v`: **209 aprovados, 7 ignorados, 216 no total**. Ruff check/format dos arquivos alterados e `git diff --check` aprovados. Os 18 testes CART-01 incluem confirmação uma vez, roteamento fora do modelo, origem/replay, expiração, mudança de versão, timeout/reinício, ausência de dados pessoais no SQLite, custos/orçamento visíveis e protocolo malformado sem encerrar polling. Transportes/MCP/modelo são falsos; não houve polling ou escrita real. A integração HTTP completa bot→CART-01 ainda requer ensaio próprio; os pins históricos RUN-01 foram preservados e seus 7 testes exigem checkout fixado.

Auditoria independente autorizada pelo usuário inspecionou o diff e executou regressores/probes, sem editar fontes. Parecer limitado a draft com flags OFF, sem bloqueadores nesse recorte. Não é GO de ativação ou conclusão de BOT-03/INT-02/QA-01.
