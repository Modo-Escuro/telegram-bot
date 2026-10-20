# Cliente de conversa v1.0 — contrato base e extensões atuais

[Índice](README.md) · [BOT-01](https://github.com/Modo-Escuro/telegram-bot/issues/1)

## Estado e alcance

**Conferência local de 20/10:** outbox/worker, texto livre, captura de sessão, progresso, memória e endereços estão implementados. Schemas base/pins abaixo são preservados; extensões são validadas explicitamente pelo cliente e não reescrevem cópias históricas. Guia corrente: [assistente](assistente-conversacional.md). Modelo/outputs reais e ativação continuam evidências separadas.

Implementado em `conversation.py` e `conversation_contract.py`, com transporte injetável e testes offline. Os schemas base vieram da [API-01 em `6ce3d99`](https://github.com/Modo-Escuro/api-backend/blob/6ce3d99863253f3c3c93495621afa33ee92e361d/docs/conversation-api-v1.md). As rotas RUN-01 existem na API coordenada atual; sua disponibilidade exige runtime e, para eventos novos, processador configurado.

Texto livre já é ligado à API pelo worker opt-in, sem segundo polling Telegram. Modelo/MCP continuam exclusivamente na API; o bot não envia pedidos. Login e preparação CART-01 são canais separados.

## Interface do cliente

`ConversationClient(config, bot_id, timeout=15)` recebe `BackendConfig` existente e o ID numérico do bot obtido de configuração/transporte confiável. O backend deverá cadastrar o bot associado à credencial conforme API-01. Nenhuma nova variável Railway foi criada neste incremento. Origem HTTPS em produção; HTTP restrito a loopback para testes. Timeout configurável de até 60 segundos por chamada, sem retry automático.

| Método | Comportamento |
| --- | --- |
| `prepare_text(update, expected_version)` | Valida remetente e conversa privada; deriva evento/origem do update autenticado |
| `prepare_action(update, expected_version, action=..., action_ref=...)` | Prepara callback de seleção/edição/revisão; não aceita aprovação de compra |
| `prepare_cancel(update, expected_version, operation_id)` | Prepara cancelamento do processamento local com evento próprio |
| `serialize()` no comando / `restore(bytes, schema)` no cliente | Conserva corpo exato na outbox/replay; não recalcula versão nem origem |
| `send(command, session_ref=...)` | POST de evento/cancelamento com sessão capturada quando suportada; retorna `Operation`/`Cancellation` |
| `get_operation(operation_id, event_id=..., session_ref=...)` | Consulta operação esperada sem repetir evento ou substituir sessão |
| `get_snapshot(session_ref=...)` | Versão/fase/documento da sessão; API pode devolver documento neutro se não houver associação |
| `account_context()` | Retorna sessionRef ou None; 404/disabled sinalizam extensão ausente |
| `get_progress(operation_id, event_id=..., session_ref=...)` | Prévia opcional até 600 caracteres, null/None quando ausente/finalizada |
| `memory_directory()` | Revision/diretório sem fatos; cliente filtra RECIPIENT para remoção e tem fallback legado se extensão desabilitada |
| `get_addresses()` / `select_address(choice_ref)` | Consulta e seleção humana por referência opaca; não cadastra endereço |

O transporte acrescenta Bearer, `X-Telegram-User-Id` e `X-Telegram-Chat-Id` ao prefixo `/api/bot/v1/conversations/{conversationId}`. Não aceita origem/organizador arbitrários no corpo nem URL de operação fornecida pelo servidor. Redirects são bloqueados para impedir encaminhamento de credenciais.

Com sessão capturada acrescenta `X-Conversation-Session`; o valor persistido acompanha replay, cancelamento, snapshot e consulta de operação/progresso. LINK_CHANGED não autoriza trocar a referência pela conta nova. Ausência da extensão mantém compatibilidade sem associação por evento. Memória/endereço possuem validação própria; nenhum desses mecanismos autoriza compra ou prova identidade estável entre relogins.

`Operation` expõe status, versões, completude, intervalo de consulta e indicador terminal. `SUCCEEDED` com completude parcial não significa compra concluída; `RESULT_UNKNOWN` permanece distinto e terminal para o processamento local. `Cancellation` não confirma cancelamento remoto: o contrato exige `remoteCancellation=NOT_REQUESTED`. O cliente não expõe o endpoint de aprovação de compra, reservado a BUY-01/02.

Documentos são armazenados como bytes imutáveis e omitidos de `repr`; `to_dict()` devolve uma cópia. A cópia integral é exclusiva do adaptador: pode conter referências humanas e dados privados e não deve ser passada ao modelo, log ou mensagem Telegram. A futura projeção do contexto do modelo deve usar uma lista explícita de campos permitidos, conforme API-01.

## Recuperação e fronteiras

1. Validar o update privado do organizador recebido pelo transporte autenticado. Para callbacks, BOT-03 deve resolver a referência a partir do teclado persistido; o texto livre/modelo não escolhe referências.
2. Capturar sessão para o evento e preparar o comando uma única vez. A outbox persiste seus bytes/schema antes do primeiro POST; não recaptura outra conta para replay. Cursor/recebimento seguem o fluxo BOT-01.
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

CI do contrato atual: o job separado `integration-assistant` usa API [#58](https://github.com/Modo-Escuro/api-backend/pull/58), SHA fixo `148b595082823288fbb713d1a6e341e32dfbffc7`, em Windows/Ubuntu, Python 3.12 e Node 22.13. A fixture só inicia servidor em loopback com modelos/OAuth/MCP/gate sintéticos; não carrega .env. Jobs RUN-01/endereços conservam seus pins de origem. Executar localmente o caso novo com ASSISTANT_API_ROOT para checkout exclusivo desse SHA; um skip por ausência da variável não conta como aprovação.

Validação local em Windows/Python 3.12 em 18/10/2026: **64 testes passaram**, incluindo os 51 exemplos oficiais como subcasos e o bloqueio real de redirect em loopback. Ruff e formatação passaram; wheel foi construído/instalado, os nove schemas foram carregados do pacote, `pip check` e ajuda da CLI passaram. Os quatro hashes do baseline histórico foram preservados. A CI continua configurada para Windows e Ubuntu; seu resultado deve ser conferido na PR. Nenhuma instância real do bot foi iniciada.

## Registro de escopo do cliente original

As pendências de outbox, worker e texto livre da entrega original foram implementadas pela [BOT-01](bot-01-fila-duravel.md). Preparação tem canal [CART-01](cart-01-telegram.md) separado. Ações guiadas antigas não equivalem aos cartões TEXT atuais; a integração completa da nova sacola às revisões ainda precisa de verificação. Envio/pagamento permanecem fora deste cliente.
