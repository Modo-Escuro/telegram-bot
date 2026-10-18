# Login iFood pelo Telegram

[Índice](README.md) · [Estado verificado](estado-atual.md) · [Arquitetura](arquitetura.md)

## Status e configuração

O fluxo foi concluído pelo usuário na Railway e confirmado por consulta autenticada: vínculo `CONNECTED`, sessão operacional e verificação `OK`. Isso não aprova compra. A evidência sanitizada está em [estado atual](estado-atual.md).

O contrato do cliente foi implementado contra `20e46fd` e revisado para `686300d`. Use o [contrato bot→API dessa versão](https://github.com/Modo-Escuro/api-backend/blob/686300d1a10c12bb6c3bd899e40fbd3a68c648f5/docs/bot-api.md); não inventar rotas ou schemas de compra.

| No bot | Correspondência na API |
| --- | --- |
| `BACKEND_BASE_URL` | Mesma origem pública HTTPS de `PUBLIC_BASE_URL` |
| `BACKEND_API_TOKEN` | Mesmo segredo de `BOT_API_TOKEN` |
| `TELEGRAM_ALLOWED_USER_ID` | Organizador permitido em `ALLOWED_ORGANIZER_IDS` |

Credenciais iFood, PKCE, callback e tokens pertencem à API. [Railway](deploy-railway.md) e [execução local](executar-bot.md) contêm os procedimentos de configuração. `.env` não é carregado automaticamente pelo bot. Configuração parcial de `BACKEND_*` impede iniciar o polling.

## Passo a passo do organizador

1. Envie **`/conectar`**. O bot mostra **Abrir login do iFood**. Um novo `/conectar` cria outra tentativa e invalida a anterior.
2. Abra o link e conclua a autorização no **mesmo navegador**, mantendo o cookie da tentativa. Com callback HTTPS público, o computador ou celular pode ser usado. Com callback localhost, use o computador em que o backend está rodando.
3. Quando a página informar que a autorização foi recebida, volte à **mensagem do login no Telegram**. O bot consulta o status e edita essa mensagem para mostrar **Confirmar conexão**. Não é uma nova notificação push. Se a mensagem foi removida ou o acompanhamento terminou, envie `/confirmar` ou `/ifood`.
4. Confira a conta mascarada apresentada e toque em **Confirmar conexão** somente se reconhecê-la. Quando a identidade não puder ser verificada, o bot informa isso explicitamente. `/confirmar` sem clique não confirma.
5. Envie **`/verificar`** para solicitar a verificação da sessão. `/ifood` consulta o estado salvo sem nova operação iFood. Vínculo `CONNECTED` isolado não basta: sessão operacional e operações permitidas são exigidas.

Não enviar senha, token, código OAuth, URL de retorno ou código digitado no Telegram. Esta confirmação vincula a conta ao organizador; a aprovação de um pedido futuro será outro evento humano.

## Estados e recuperação

| Estado | Comportamento do usuário |
| --- | --- |
| `DISCONNECTED` | Iniciar com `/conectar` |
| `AWAITING_AUTHORIZATION` | Concluir no navegador e voltar à mensagem do login; `/confirmar` é alternativa |
| `AWAITING_CONFIRMATION` | Conferir a conta na mensagem atualizada e tocar no botão; `/confirmar` recupera a apresentação |
| `CONNECTED` sem sessão operacional/operações | Enviar `/verificar`; pode faltar verificação ou permissão |
| `CONNECTED` operacional | Vínculo pronto para as operações permitidas; conversa de compras continua pendente |
| `RECONNECT_REQUIRED` | Gerar nova tentativa com `/conectar` |
| `UNAVAILABLE` | Indisponibilidade não é logout; tentar `/verificar` depois |

A tentativa de autorização vale dez minutos; após o callback há mais dez minutos para confirmação, conforme o contrato revisado. Tentativa expirada requer novo `/conectar`. Botão antigo não confirma nova tentativa.

Se não houver botão após o login, envie `/confirmar` ou `/ifood`; não envie código. Se a página indicar divergência de navegador, use o mesmo navegador do início. Falha de rede não comprova logout nem sucesso; diante de resultado desconhecido, consultar `/ifood` antes de nova ação consciente. `/cancelar` ou **Cancelar tentativa** cancela somente a tentativa pendente e preserva o vínculo confirmado. `/desconectar` ou **Desconectar vínculo** remove somente o vínculo local; não solicita revogação no provedor nem cancela uma tentativa pendente. Para ambos os efeitos, use as duas ações conscientemente.

## Garantias e limites implementados

- Somente conversa privada do organizador chega ao cliente HTTP; ID recebido do Telegram é validado pelo adaptador e conferido pela API.
- HTTPS obrigatório fora de loopback. O cliente rejeita redirects; o link precisa ser da origem configurada, caminho `/auth/ifood/start`, tentativa correspondente e parâmetros esperados.
- Timeout de 50 segundos nos comandos; as consultas automáticas de status usam 5 segundos. Sem retry HTTP automático de mutações. Erros não expõem corpo remoto, código, credencial ou URL em logs.
- Antes de conexão, verificação, confirmação, cancelamento ou desconexão, registrar `update_id` no SQLite. Replay consulta o estado; não repete a mutação. Uma interrupção entre registro e chamada não comprova execução.
- Ao clicar, o bot consulta o estado atual e compara `confirmationId`. O backend também controla validade e uso único. `ALREADY_CONFIRMED` apenas consulta o estado.
- O bot tenta remover o teclado após o uso. Se o envio falhar, a proteção do backend continua sendo necessária; não se promete entrega única de texto no Telegram.
- Não guardar URL de login, `confirmationId`, código ou identidade da conta no SQLite. Tokens OAuth nunca passam pelo adaptador.

## Persistência e próximos passos

O bot preserva cursor, ações e metadados do acompanhamento no volume `/data`: organizador, attemptId, messageId, fase, prazos e próxima consulta. A tabela é criada de forma aditiva, sem remover cursor/ações. Nenhum texto, URL OAuth, confirmationId ou identidade mascarada é guardado nessa tabela. Os vínculos da API ainda estão em armazenamento sem volume; antes de redeploy do backend, preservar os arquivos existentes e concluir uma migração verificada. Tentativas pendentes ficam em memória mesmo com volume: não redeployar a API durante o login.

`linkId` deverá vincular futuras sacolas e aprovações. Mudança da conta/vínculo invalidará revisões anteriores. Essa regra ainda é requisito: sacola e aprovação de compra não existem neste bot.

## Acompanhamento BOT-02

Há no máximo uma tentativa acompanhada por bot/organizador. Durante o acompanhamento, o long polling Telegram espera até 3 segundos; a consulta de status é espaçada em pelo menos 5 segundos e tem timeout de 5 segundos. Continua no mesmo processo: chamadas manuais de login e rede ainda podem atrasar eventos; a fila assíncrona da conversa pertence à BOT-01.

O prazo vem de attempt.expiresAt, com limite local total de 20 minutos. A transição para confirmação pode estender o prazo de autorização conforme a API. Se um backend antigo omitir o campo, usa-se limite local conservador. Reinício retoma a tentativa salva se ainda válida. Mudança de organizador descarta o acompanhamento anterior.

O botão é atualizado por editMessageText na mensagem cujo ID foi confirmado pelo Telegram. Edição repetida mira a mesma mensagem, sem criar notificações novas. Rate limit respeita retry_after; mensagem apagada, erro permanente ou prazo encerrado terminam o acompanhamento e mantêm /confirmar e /ifood como alternativas. Falha ao confirmar entrega de sendMessage pode repetir texto no replay; não repete a mutação de login.

Botões de cancelar/desconectar incluem referência à tentativa/vínculo e são comparados ao status atual antes da mutação. A API atual não recebe uma condição de versão nesses endpoints: a checagem protege botões obsoletos no worker único, mas não constitui CAS entre clientes externos concorrentes.

Após o clique, a resposta mostra o estado atual e encerra o acompanhamento quando não há tentativa. Não há contexto de compra para retomar nesta versão. Revalidação de sacola/aprovação após mudança de linkId permanece nas tarefas de conversa e compra; nenhum botão antigo pode aprovar compra porque essas ações não existem no bot.

Código e testes deste incremento não comprovam deploy nem ensaio online. O snapshot anterior permanece histórico. Validar manualmente depois do merge/deploy: /conectar, navegador, mensagem atualizada, clique e /verificar; cancelar reconexão preservando o vínculo; desconectar com tentativa pendente preservando a tentativa.
