# Cliente de conversa v1.0 — incremento parcial da BOT-01

[Índice](README.md) · [BOT-01](https://github.com/Modo-Escuro/telegram-bot/issues/1)

## Estado e alcance

**Atualização BOT-01:** [outbox, worker e texto livre opt-in](bot-01-fila-duravel.md) implementados nesta continuação. As rotas RUN-01/DATA-01 existem na API `08709c7` e são exercitadas por HTTP em loopback com processador sintético. Os schemas fixados abaixo permanecem iguais. O texto seguinte documenta o recorte original do cliente; suas pendências de outbox/polling são substituídas pelo novo guia. IA real, BOT-03/aprovação e ativação operacional permanecem separadas.

Implementado em `conversation.py` e `conversation_contract.py`, com transporte HTTP injetável e testes offline. O cliente usa o contrato da [API-01 em `6ce3d99`](https://github.com/Modo-Escuro/api-backend/blob/6ce3d99863253f3c3c93495621afa33ee92e361d/docs/conversation-api-v1.md). A API-01 está concluída como especificação e conformidade; suas rotas ainda dependem da [RUN-01](https://github.com/Modo-Escuro/api-backend/issues/14).

Este incremento não conecta texto livre ao processamento real, não inicia polling adicional, não chama modelo/MCP e não envia compra. O fluxo de login permanece independente. O fechamento da BOT-01 exige os trabalhos pendentes abaixo e uma integração real validada.

## Interface do cliente

`ConversationClient(config, bot_id, timeout=15)` recebe `BackendConfig` existente e o ID numérico do bot obtido de configuração/transporte confiável. O backend deverá cadastrar o bot associado à credencial conforme API-01. Nenhuma nova variável Railway foi criada neste incremento. Origem HTTPS em produção; HTTP restrito a loopback para testes. Timeout configurável de até 60 segundos por chamada, sem retry automático.

| Método | Comportamento |
| --- | --- |
| `prepare_text(update, expected_version)` | Valida remetente e conversa privada; deriva evento/origem do update autenticado |
| `prepare_action(update, expected_version, action=..., action_ref=...)` | Prepara callback de seleção/edição/revisão; não aceita aprovação de compra |
| `prepare_cancel(update, expected_version, operation_id)` | Prepara cancelamento do processamento local com evento próprio |
| `serialize()` no comando / `restore(bytes, schema)` no cliente | Conserva corpo exato para futura persistência e replay; não recalcula versão nem origem |
| `send(command)` | POST de evento ou cancelamento; retorna `Operation` ou `Cancellation` |
| `get_operation(operation_id, event_id=...)` | Consulta a operação esperada sem repetir o evento |
| `get_snapshot()` | Consulta versão, fase e documento atual da conversa |

O transporte acrescenta Bearer, `X-Telegram-User-Id` e `X-Telegram-Chat-Id` ao prefixo `/api/bot/v1/conversations/{conversationId}`. Não aceita origem/organizador arbitrários no corpo nem URL de operação fornecida pelo servidor. Redirects são bloqueados para impedir encaminhamento de credenciais.

`Operation` expõe status, versões, completude, intervalo de consulta e indicador terminal. `SUCCEEDED` com completude parcial não significa compra concluída; `RESULT_UNKNOWN` permanece distinto e terminal para o processamento local. `Cancellation` não confirma cancelamento remoto: o contrato exige `remoteCancellation=NOT_REQUESTED`. O cliente não expõe o endpoint de aprovação de compra, reservado a BUY-01/02.

Documentos são armazenados como bytes imutáveis e omitidos de `repr`; `to_dict()` devolve uma cópia. A cópia integral é exclusiva do adaptador: pode conter referências humanas e dados privados e não deve ser passada ao modelo, log ou mensagem Telegram. A futura projeção do contexto do modelo deve usar uma lista explícita de campos permitidos, conforme API-01.

## Recuperação e fronteiras

1. Validar o update privado do organizador recebido pelo transporte autenticado. Para callbacks, BOT-03 deve resolver a referência a partir do teclado persistido; o texto livre/modelo não escolhe referências.
2. Preparar o comando uma única vez. A futura outbox deve persistir seus bytes e schema antes do primeiro envio e antes de avançar o cursor.
3. Enviar. 202 significa aceitação persistida pela API, não conclusão. Preservar a associação com `operation_id` e consultar respeitando `poll_after_ms` e prazo/limites de RUN-01.
4. Em timeout de POST, `ConversationError.uncertain=True` indica ausência de confirmação. Recuperar o mesmo comando por `restore` e reenviá-lo explicitamente apenas para recuperar o aceite idempotente da API. Nunca reconstruir sua versão/chave, nem interpretar isto como autorização para repetir escrita remota.
5. `EVENT_CONFLICT` exige corrigir a inconsistência; `STALE_VERSION` exige consultar o snapshot. Não alterar o comando já enviado para reutilizar sua chave. A API é a autoridade que rejeita reutilização de chave com conteúdo divergente.

`ConversationError` só contém código, recuperação fixa, indicador de incerteza e mensagem local. Corpo remoto não é exibido; erros HTTP precisam corresponder à tabela normativa de código/status/recuperação. Envelopes legados conhecidos do middleware de autenticação são aceitos separadamente. JSON inválido, excessivo, com chaves duplicadas, números não finitos, campos/enums/versão desconhecidos ou resposta de outro evento/conversa falha de forma fechada.

Além dos schemas, o consumidor verifica versões/proveniência, prazo da operação, estados/completude, soma exata dos custos confirmados, intervalo monetário, evidência de confirmação e validade/cobertura das referências humanas. Isso valida o documento recebido; não substitui restrições por pessoa, recotação, autorização humana nem reconciliação na API.

## Reprodução

Python 3.12, em ambiente virtual (no POSIX, substituir `Scripts/python.exe` por `bin/python`):

```text
.venv/Scripts/python.exe -m pip install -r requirements.lock
.venv/Scripts/python.exe -m pip install --no-deps -e .
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Os nove schemas e os 51 exemplos sintéticos são cópias exatas da API no commit fixado, verificadas por SHA-256 em `contracts-provenance.json`. Não editar essas cópias isoladamente para acomodar uma divergência: revisar o contrato upstream, fixar a nova referência, atualizar hashes e validar produtores/consumidores. Os exemplos incluem schemas futuros de aprovação e contexto, mas copiá-los não torna seus fluxos disponíveis no cliente.

CI e Docker instalam `requirements.lock`, alinhado às versões usadas na conformidade Python da API-01. Os schemas acompanham o pacote instalado; não há busca de schema pela rede em execução. Testes usam somente dados sintéticos, transporte simulado e um servidor HTTP em loopback; não comprovam persistência, rotas implantadas, modelo nem operações iFood.

Validação local em Windows/Python 3.12 em 18/10/2026: **64 testes passaram**, incluindo os 51 exemplos oficiais como subcasos e o bloqueio real de redirect em loopback. Ruff e formatação passaram; wheel foi construído/instalado, os nove schemas foram carregados do pacote, `pip check` e ajuda da CLI passaram. Os quatro hashes do baseline histórico foram preservados. A CI continua configurada para Windows e Ubuntu; seu resultado deve ser conferido na PR. Nenhuma instância real do bot foi iniciada.

## Para concluir a BOT-01

- Outbox durável: comando, associação da operação, andamento e recuperação após reinício, gravados antes do avanço do cursor.
- Processamento em segundo plano sem bloquear comandos/status; ordenação por conversa, indicação de processamento e limites de consulta.
- Encaminhamento de texto privado e apresentação segura dos blocos/erros, sem promover texto de modelo a confirmação de pedido.
- Associação de callbacks a teclado/versão e fluxo humano dedicado, em coordenação com BOT-03 e BUY-01/02.
- Integração e cenários de timeout/replay/versão antiga contra RUN-01 disponível. Não encerrar a issue apenas por estes testes offline.
