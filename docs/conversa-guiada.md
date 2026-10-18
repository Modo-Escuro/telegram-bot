# Conversa guiada — incremento local de 18/10/2026

Continuação local dos PRs API #49 e bot #20, em `codex/conversation-guidance`. Não implantada.

As respostas exibem Escolher opção N, Mudar busca e Ver outras quando a API oferece essas ações. Também aceitam texto: “a segunda”, “mais barato” e “troca por pizza”. A API preserva a busca durante a coleta e decide as opções; o bot não interpreta catálogo ou restrições. Revisar carrinho aparece com sacola atual e `TELEGRAM_CART_ENABLED=true`, abrindo a revisão já existente. Preparação exige outro callback humano específico PREPARE_CART.

O teclado de navegação continua separado dessas opções. Nas respostas longas, os botões ficam apenas na última parte. Preços observados, entrega desconhecida e pessoas sem atendimento verificado permanecem explícitos. Esvaziar sacola preserva participantes, restrições e orçamento e não altera o carrinho remoto.

As referências expiram em cinco minutos e ficam vinculadas à versão da conversa. O SQLite local guarda apenas hash de referência, escopo, mensagem, bot, tipo, versão e prazo; não guarda snapshot ou texto do catálogo. Callback exige remetente/chat autorizados e mensagem original do bot. A fila não troca a versão de uma ação antiga pela atual. Recuperação conserva eventId e origem CALLBACK.

## Validação offline

Suíte completa: **257 testes aprovados**, incluindo a integração HTTP deste incremento, CART-01 e APIs históricas fixadas. API correspondente: **1.091 aprovados e 2 ignorados**; typecheck, lint e build aprovados. Esses resultados são locais, não CI ou ensaio em produção.

`test_conversation_buttons.py` cobre reinício, duplicação, expiração, outro remetente/chat/bot/mensagem, origem malformada, versão antiga, entrega em partes e distinção entre revisão e preparação. `test_guidance_integration.py`, com `GUIDANCE_API_ROOT` apontando para a API deste incremento, percorre texto → propostas → clique duplicado → sacola → esvaziamento com grupo preservado, via HTTP e SQLite reais e OAuth/MCP/modelo sintéticos.

Os testes históricos RUN-01 e continuidade mantêm commits e fixtures originais. `CART_API_ROOT` testa a integração de revisão existente. Nenhum teste usa polling Telegram, modelo pago ou escrita iFood real.

## Grupos por conta e login

O cadastro separado por conta iFood ainda não foi implementado. A documentação MCP fornecida confirma que `userId` é oculto pelo gateway; nome/e-mail mascarados e o `linkId` de cada login não identificam a mesma conta de forma estável. O discovery público anuncia `userinfo`, mas a obtenção de uma identidade estável por esse caminho ainda precisa ser validada no backend.

Depois dessa validação: separar grupo da compra, fixar a conta de origem nas mensagens pendentes e testar A → B → A também após reinício. Não migrar o grupo legado para uma conta inferida. Recomenda-se Entrar no iFood / Sair da conta iFood, com Cancelar login durante a tentativa e Sair da demo separado; os rótulos atuais continuam neste incremento.

## Implantação posterior

Implantar a API compatível antes do bot; a API usa schema SQLite v4. Preservar todo o diretório de estado do bot, incluindo banco de acesso, SQLite legado e `users/<hash>/bot.sqlite3`, filas, referências CART-01 e arquivos WAL/SHM. Cópia consistente exige parar o serviço antes de copiar. Rollback por flags: desligar `TELEGRAM_CART_ENABLED` e `TELEGRAM_CONVERSATION_ENABLED` juntos, preservar dados e usar binário compatível na API. Não executar polling concorrente.
