# Recuperação automática de respostas Telegram

Correção preparada sobre `main@6adb78d`. Código e testes locais não comprovam publicação ou recuperação das filas online.

## Problema observado

Uma resposta antiga marcada `DELIVERY_UNKNOWN` permanecia na cabeça da outbox e impedia mensagens seguintes. A API podia já ter concluído a operação. Mensagens de progresso enviadas com `ReplyKeyboardMarkup` não permitem edição; a versão atual já usa markup editável, mas preservava os registros antigos bloqueados.

## Comportamento

- A outbox oferece uma recuperação automática por registro TEXT com operação conhecida e pelo menos a primeira parte de mensagem já entregue. O contador persiste em SQLite e não é zerado pelo reinício.
- O worker consulta a mesma operação e o snapshot atual por GET. Não reenvia evento, não repete chamada ao modelo e não executa ação de carrinho.
- Uma recusa explícita de edição (`message can't be edited` ou `message to edit not found`) remove somente a referência daquela parte. No tick seguinte, o worker consulta o estado atual e envia uma substituta editável. A resposta antiga pode continuar visível.
- Erro `message is not modified` conserva a recuperação pelo ID original. Outros HTTP 400 não são tratados como autorização para substituir mensagens.
- Após confirmação local de entrega, a próxima mensagem da fila é processada normalmente, sem `/retomar`.

A migração adiciona somente `delivery_recoveries INTEGER NOT NULL DEFAULT 0`; não apaga SQLite, cursor, fila ou vínculos. Publicar o binário compatível é suficiente para o worker reconhecer os registros legados elegíveis, sem executar comandos por usuário.

## Limites

Timeout de um envio novo sem ID conhecido continua incerto. Crash durante envio de uma parte pode causar repetição visual ao recuperar uma resposta com partes anteriores conhecidas. A recuperação automática é limitada a uma por registro; falha persistente continua disponível para diagnóstico e recuperação manual. POST desconhecido, resultado externo desconhecido e callbacks de aprovação não são liberados automaticamente por esta mudança.

## Verificação offline

`python -m unittest discover -s tests -v`, com dependências de `requirements.lock` e pacote instalado sem dependências. Os testes em `test_continuity_addresses.py` simulam a recusa real de edição, fila legada após reinício, avanço da próxima mensagem, limite persistido e classificação de erros tanto HTTP quanto JSON. Não usar token real nem iniciar outro polling para executar testes.
