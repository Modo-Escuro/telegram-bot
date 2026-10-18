# Conversa guiada — incremento local de 18/10/2026

Continuação local dos PRs API #49 e bot #20, em `codex/conversation-guidance`. Não implantada.

As respostas exibem Escolher opção N, Mudar busca e Ver outras quando a API oferece essas ações. Também aceitam texto: “a segunda”, “mais barato” e “troca por pizza”. A API preserva a busca durante a coleta e decide as opções; o bot não interpreta catálogo ou restrições. Revisar carrinho aparece com sacola atual e `TELEGRAM_CART_ENABLED=true`, abrindo a revisão já existente. Preparação exige outro callback humano específico PREPARE_CART.

O teclado persistente contém apenas Menu; a navegação aparece em botões junto da mensagem. Nas respostas longas, os botões ficam apenas na última parte. Preços observados, entrega desconhecida e pessoas sem atendimento verificado permanecem explícitos. Esvaziar sacola preserva participantes, restrições e orçamento e não altera o carrinho remoto.

As referências expiram em cinco minutos e ficam vinculadas à versão da conversa. O SQLite local guarda apenas hash de referência, escopo, mensagem, bot, tipo, versão e prazo; não guarda snapshot ou texto do catálogo. Callback exige remetente/chat autorizados e mensagem original do bot. A fila não troca a versão de uma ação antiga pela atual. Recuperação conserva eventId e origem CALLBACK.

## Conta, grupo e login

A API correspondente implementa cadastro por conta atrás de `CONVERSATION_ACCOUNT_GROUPS_ENABLED`, desligado por padrão até validar UserInfo real. A fila captura a sessão no recebimento e mantém a referência em consulta, envio e recuperação, inclusive após reinício. Uma mensagem aceita em A não é transferida a B. Limpar/remover perfil usam versão e sessão da pergunta, com prazo de cinco minutos; confirmações antigas não são atualizadas para a versão atual.

Conta iFood apresenta Entrar no iFood, Cancelar login ou Sair da conta iFood conforme o estado. Sair da demo continua separado. Cancelamento/logout incluem a referência atual para impedir que um botão antigo altere outro login.

“Não”, “não tenho” e o botão “Não tenho restrições” encerram a pergunta de restrições desconhecidas, inclusive em conversa presa na confirmação anterior. A API preserva alergias já declaradas. O teclado fixo fica restrito a Menu; os demais controles aparecem nas mensagens, incluindo Remover pessoa e Limpar perfil dos PRs #23/#24.

## Validação e implantação

As respostas curtas omitem a narração “Ana entrou na compra”, seguindo direto para a pergunta pendente. Confirmações alimentares, recusas e alertas continuam visíveis. A abertura, a escolha individual/grupo e a espera da operação não anunciam que a resposta chegará automaticamente; o indicador de digitação e a entrega final continuam ativos. Mensagens de progresso já enviadas por versões antigas continuam recuperáveis após atualização ou reinício.

Testes offline cobrem envio, replay, versão, expiração, isolamento de sessão, callbacks e limpeza. `test_guidance_integration.py` com `GUIDANCE_API_ROOT` aponta para esta API e percorre texto → opções → clique → carrinho → limpeza, usando HTTP e SQLite reais e serviços externos falsos. As integrações históricas mantêm seus commits fixados. Resultados finais estão no PR; não comprovam deploy ou identidade real iFood.

Publicar a API compatível antes do bot. API usa schema v5; preservar integralmente o diretório de estado do bot com o serviço parado, incluindo acesso, usuários, filas e WAL/SHM. Desligar `TELEGRAM_CART_ENABLED` junto de `TELEGRAM_CONVERSATION_ENABLED` em rollback e manter binário API compatível com o banco. Não executar polling concorrente.

Ainda falta ampliar a resolução de pedido individual com grupo salvo e a correspondência entre comida solicitada e resultados do catálogo. Esta entrega não comprova que todo o fluxo das imagens esteja resolvido.
