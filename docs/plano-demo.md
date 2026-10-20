# Plano da demo

[Estado remoto/local](estado-remoto-local.md) · [Plano integrado](plano-conversacional.md) · [Backlog](backlog-conversacional.md).

1. Conferir a árvore coordenada: assistente, banco API v6, flags, volume e vínculo. Revisão local/merge não comprovam operação online.
2. Validar intenção natural, memória SELF/destinatários, sessão da conta, cartão numerado e escolha digitada da sacola. O bot não emite automaticamente ações guiadas antigas para os cartões TEXT atuais.
3. Integrar/verificar o fio dessa sacola às revisões CART-01 e validar saídas INT-02 antes de expor preparação real. Callback PREPARE_CART específico; falta de evidência alimentar bloqueia. Custos desconhecidos explícitos, sem envio/pagamento.
4. Ensaiar carrinho no ambiente autorizado após revisão humana específica. Preservar intenção e bloquear resultado desconhecido, mesmo após reinício/reconexão.
5. Registrar o que cada marco comprova. O fechamento externo do briefing permanece pendente em BUY-01/BUY-02/QA-01; carrinho preparado não comprova pedido/pagamento, e composição apenas local não comprova preparação real.

Não alterar produção nem iniciar segundo polling para validar. Cancelamento local não desfaz uma mutação remota. Login, senha e retomada de contexto nunca confirmam automaticamente o carrinho.

O ensaio online de login está preservado em [estado-atual](estado-atual.md). Ele não foi repetido nem ampliado por esta revisão documental.
