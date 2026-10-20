**Guia atual conferido em 20/10/2026:** login conclui no navegador; menu e memória em [assistente](assistente-conversacional.md). Comandos antigos são aliases, não um segundo consentimento obrigatório. Observação online de 17/10 é histórica.

# Login iFood pelo Telegram

[Índice](README.md) · [Estado verificado](estado-atual.md) · [Arquitetura](arquitetura.md)

## Status e configuração

O fluxo de 17/10 foi concluído pelo usuário na Railway e confirmado como CONNECTED/operacional; a [evidência](estado-atual.md) não é inspeção do serviço atual. O código local posterior conclui vínculo no callback, sem segundo clique. Nenhum login aprova compra.

Origem histórica do cliente: `20e46fd`/`686300d`; o [pin do contrato](https://github.com/Modo-Escuro/api-backend/blob/686300d1a10c12bb6c3bd899e40fbd3a68c648f5/docs/bot-api.md) é preservado. No checkout coordenado, o contrato corrente está em `api-backend/docs/bot-api.md` e `docs/login-retorno-natural.md`; não extrapolar rotas/garantias de versões antigas.

| No bot | Correspondência na API |
| --- | --- |
| `BACKEND_BASE_URL` | Mesma origem pública HTTPS de `PUBLIC_BASE_URL` |
| `BACKEND_API_TOKEN` | Mesmo segredo de `BOT_API_TOKEN` |
| `TELEGRAM_ALLOWED_USER_ID` | Organizador permitido em `ALLOWED_ORGANIZER_IDS` |

Credenciais iFood, PKCE, callback e tokens pertencem à API. [Railway](deploy-railway.md) e [execução local](executar-bot.md) contêm os procedimentos de configuração. `.env` não é carregado automaticamente pelo bot. Configuração parcial de `BACKEND_*` impede iniciar o polling.

## Passo a passo do organizador

1. Em **Menu → Conta iFood**, toque em **Entrar no iFood** (alias `/conectar`). O bot mostra o link de autorização. Nova tentativa invalida a pendente anterior.
2. Abra o link e conclua a autorização no **mesmo navegador**, mantendo o cookie da tentativa. Com callback HTTPS público, o computador ou celular pode ser usado. Com callback localhost, use o computador em que o backend está rodando.
3. A página do callback informa **Conta conectada** e orienta voltar ao Telegram. O backend valida state/PKCE/cookie/prazo e instala o vínculo; não é necessário segundo clique no fluxo normal.
4. O bot acompanha status por GET e atualiza a mensagem. Se houver tentativa antiga ou falha de instalação recuperável em AWAITING_CONFIRMATION, o botão manual **Confirmar conexão** continua disponível; confira a conta mascarada antes desse clique. `/confirmar` apenas recupera a apresentação, não confirma sozinho.
5. Se necessário use **Verificar conexão** ou `/verificar`. `/ifood` consulta o estado conhecido sem nova operação iFood. CONNECTED isolado não basta: acesso depende de sessão operacional/permissões.
6. Com conversa habilitada e vínculo operacional, o bot agenda contexto/endereço por consulta, sem repetir texto/modelo ou proposta/aprovação antiga. O assistente atual usa memória separada: consulta de GROUP não é reconstrução automática de todos os perfis. Confirme o endereço, mesmo que único, antes de buscar ofertas.

Não enviar senha iFood, token, código OAuth ou URL de retorno no Telegram. A senha de acesso à demo tem fluxo próprio e não substitui OAuth. O vínculo da conta e a confirmação de preparação/pedido são finalidades diferentes.

## Estados e recuperação

| Estado | Comportamento do usuário |
| --- | --- |
| `DISCONNECTED` | Iniciar com `/conectar` |
| `AWAITING_AUTHORIZATION` | Concluir no navegador e voltar à mensagem do login; `/confirmar` é alternativa |
| `AWAITING_CONFIRMATION` | Conferir a conta na mensagem atualizada e tocar no botão; `/confirmar` recupera a apresentação |
| `CONNECTED` sem sessão operacional/operações | Enviar `/verificar`; pode faltar verificação ou permissão |
| `CONNECTED` operacional | Operações permitidas disponíveis conforme opt-ins; não significa carrinho/pedido autorizado |
| `RECONNECT_REQUIRED` | Gerar nova tentativa com `/conectar` |
| `UNAVAILABLE` | Indisponibilidade não é logout; tentar `/verificar` depois |

A tentativa de autorização vale dez minutos. A instalação é automática no callback normal; o prazo adicional de confirmação pertence ao caminho manual compatível, quando aplicável. Tentativa expirada exige novo login. Botão antigo não confirma outra tentativa.

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

O bot preserva cursor, ações e acompanhamento no diretório de estado configurado: organizador, attemptId, messageId, fase, prazos e próxima consulta. A tabela de login não guarda texto, URL OAuth, confirmationId ou identidade mascarada. A outbox de conversa tem retenção própria de comandos pendentes. Antes de redeploy, conferir/preservar volumes e vínculos atuais; o registro antigo de API sem volume não prova o estado de hoje. Tentativas OAuth ficam em RAM mesmo com volume.

`linkId` já é revalidado nas revisões CART-01; a outbox também conserva `sessionRef` capturado para mensagens. Não há identidade estável entre relogins: uma pendência da conta anterior não deve ser enviada sob referência nova. A preparação exige callback próprio; aprovação/envio de pedido não estão implementados.

## Acompanhamento BOT-02

Há no máximo uma tentativa acompanhada por bot/organizador. Durante o acompanhamento, o long polling Telegram espera até 3 segundos; a consulta de status é espaçada em pelo menos 5 segundos e tem timeout de 5 segundos. Continua no mesmo processo: chamadas manuais de login e rede ainda podem atrasar eventos; a fila assíncrona da conversa pertence à BOT-01.

O prazo vem de attempt.expiresAt, com limite local total de 20 minutos. A transição para confirmação pode estender o prazo de autorização conforme a API. Se um backend antigo omitir o campo, usa-se limite local conservador. Reinício retoma a tentativa salva se ainda válida. Mudança de organizador descarta o acompanhamento anterior.

O botão é atualizado por editMessageText na mensagem cujo ID foi confirmado pelo Telegram. Edição repetida mira a mesma mensagem, sem criar notificações novas. Rate limit respeita retry_after; mensagem apagada, erro permanente ou prazo encerrado terminam o acompanhamento e mantêm /confirmar e /ifood como alternativas. Falha ao confirmar entrega de sendMessage pode repetir texto no replay; não repete a mutação de login.

Botões de cancelar/desconectar incluem referência à tentativa/vínculo e são comparados ao status atual antes da mutação. A API atual não recebe uma condição de versão nesses endpoints: a checagem protege botões obsoletos no worker único, mas não constitui CAS entre clientes externos concorrentes.

Após o clique, a resposta mostra o estado atual e encerra o acompanhamento quando não há tentativa. A [continuação BOT-02](bot-02-retomada-contexto.md) agenda consulta informativa do grupo se a sessão for operacional e o worker de conversa estiver habilitado. Revalidação de carrinho/aprovação após mudança de linkId permanece nas tarefas BOT-03/BUY-01 e no backend; ausência desses botões não comprova sua invalidação futura.

Código/testes não comprovam deploy ou ensaio online. Roteiro atual após implantação autorizada: Entrar no iFood → navegador → conclusão sem segundo clique → status atualizado → verificar se necessário → endereço confirmado. Ensaiar caminho manual apenas quando aplicável, cancelamento de reconexão e desconexão com tentativa pendente, preservando os efeitos distintos. Não preencher resultados por inferência.
