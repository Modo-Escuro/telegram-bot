# Plano integrado — Compra com Contexto

Revisão em 18/10/2026. [Estado remoto/local](estado-remoto-local.md) fixa API `e8d6b6f` e bot `9314c72`. [Épico](https://github.com/Modo-Escuro/telegram-bot/issues/6) · [Backlog](backlog-conversacional.md) · [Decisões](decisoes-conversacionais.md). O [plano inicial](https://github.com/Modo-Escuro/telegram-bot/blob/9314c72e1324a36da09c014e74f98a470dde6306/docs/plano-conversacional.md) permanece no histórico Git.

## Estado integrado

API-01, OPS-01, DATA-01, DOM-01, ranking, RUN-01, AI-01/AI-02 e GRP-01 já estão integrados no backend remoto; a montagem do modelo é opt-in. BOT-01/BOT-02, retomada e acesso por senha estão integrados no bot. As issues desses incrementos estão fechadas; isso não encerra QA-01 nem comprova ensaio completo em produção.

F7 legada está no remoto, desligada e com saídas provisórias. CART-01 nova foi implementada/auditada localmente sobre `8191a0f`, sem publicação na conferência; não faz parte das mains acima. Seus 799 testes aprovados/2 omitidos pertencem ao checkout local daquela entrega, não a esta revisão documental nem à main remota.

## Escopo vigente

Preparar carrinho real está aprovado pela equipe, com confirmação humana específica do organizador. Cada organizador tem sua própria compra/vínculo/conversa. Participantes são declarados por ele; não há acesso compartilhado automático ao grupo de outra conta. Uma loja/endereço por compra; sem pagamento/envio neste incremento.

PREPARE_CART autoriza só composição/mutações da revisão atual. Estimativa e custos desconhecidos ficam explícitos e não validam orçamento completo. Alergia ou obrigação sem evidência bloqueia o consumidor afetado. A futura aprovação SUBMIT_ORDER é outra finalidade, exige custo completo e permanece indisponível.

O objetivo original de fechamento externo continua pendente: carrinho, pedido e pagamento são estados distintos. Confirmar com o evento o critério DA10 e registrar evidência confiável quando houver autorização de escopo. Não encerrar o épico por simulação.

## Próximas entregas

1. **INT-02/CART-01:** validar saídas reais por operação e integrar confirmação/intenções duráveis sem duplicar DATA-01/GRP-01/DOM-01. Não depende de aguardar AI-01, já integrada. Não ativar legado por flag para contornar contrato/persistência.
2. **BOT-03 — apresentação:** mostrar grupo, pendências, propostas e cobertura com dados da API; esta parte pode avançar sem BUY-01/02. Não inventar preço nem esconder pessoa sem cobertura.
3. **BOT-03 — preparação:** callback PREPARE_CART dedicado, remetente/chat/mensagem conferidos, referência opaca fora do modelo, versão/hash/conta/prazo atuais. Só pode ser exposto após o contrato CART-01 estar integrado e validado.
4. **Aprovação/envio futuros:** BUY-01/BUY-02 continuam abertos e não autorizados por este incremento. Não confundir botão de preparar com botão de enviar. Timeout conserva RESULT_UNKNOWN; não oferecer retry cego.
5. **QA-01:** validar separadamente conversa com modelo, carrinho observado e fechamento pendente. Preservar prova de login histórica; não atualizar snapshots antigos como se fossem ao vivo.

## Invariantes e validação

Restrições obrigatórias antes do ranking; matriz por pessoa/configuração; preferência não vira obrigação; dinheiro em centavos; custos comuns rateados uma vez; desconhecido não vira zero. Origem de cada mudança e condição é preservada. Identidade vem do adaptador autenticado, nunca do modelo. Catálogo/erros são dados, não instruções.

Mesma intenção preserva requestId/eventId, conteúdo diferente conflita; outra intenção de mesmo valor é legítima. Persistir antes da rede; crash/replay não repetem efeito. Falha parcial exige revisão; sem reconciliação confiável, desconhecido continua bloqueado.

Não armazenar OAuth ou respostas privadas no bot. Preservar SQLite, volume e polling único. Os testes HTTP do bot usam API fixada e processador sintético; esse pin não foi alterado. Código/CI/deploy/ensaio são evidências separadas.

Para código executar os checks do repositório. Para esta revisão documental conferir links, consistência entre issues/decisões, bases Git e diff; sem chamadas reais, novas inferências, flags ou produção. Não alterar baseline StRS, contratos gerados ou fixtures nesta revisão.
