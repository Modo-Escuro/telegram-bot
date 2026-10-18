# Plano da demo

[Estado remoto/local](estado-remoto-local.md) · [Plano integrado](plano-conversacional.md) · [Backlog](backlog-conversacional.md).

1. Ensaiar código remoto de conversa: configuração explícita do modelo/API e flag do bot, vínculo quando necessário e preservação de restrições/orçamento após correção. Um merge não comprova ensaio.
2. Apresentar grupo/propostas no Telegram pela BOT-03, com cobertura por pessoa e preço/estimativa da API.
3. Integrar CART-01 local e validar saídas na INT-02 antes de expor preparação real. Exigir callback PREPARE_CART específico; falta de evidência alimentar bloqueia. Explicitar custos desconhecidos e não enviar pedido/pagamento.
4. Ensaiar carrinho no ambiente autorizado após revisão humana específica. Preservar intenção e bloquear resultado desconhecido, mesmo após reinício/reconexão.
5. Registrar o que cada marco comprova. O fechamento externo do briefing permanece pendente em BUY-01/BUY-02/QA-01; uma sacola simulada ou carrinho preparado não comprovam pedido/pagamento.

Não alterar produção nem iniciar segundo polling para validar. Cancelamento local não desfaz uma mutação remota. Login, senha e retomada de contexto nunca confirmam automaticamente o carrinho.

O ensaio online de login está preservado em [estado-atual](estado-atual.md). Ele não foi repetido nem ampliado por esta revisão documental.
