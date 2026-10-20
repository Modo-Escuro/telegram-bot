# Backlog e dependências — 18/10/2026

> Retrato histórico de issues, sem consulta nova ao GitHub em 20/10. Memória seletiva e áudio opt-in já têm código local; o intérprete estruturado foi retirado da API. Isso não altera retroativamente as colunas/contagens de 18/10. Para implementação/próximo marco, usar [assistente](assistente-conversacional.md) e [plano local](plano-conversacional.md#situação-local-vigente--20102026).

[Plano](plano-conversacional.md) · [Remoto/local](estado-remoto-local.md) · [Kanban](kanban.md) · [Épico](https://github.com/Modo-Escuro/telegram-bot/issues/6).

Retrato das issues consultadas após os merges API #38/#41/#42: 23 tarefas (15 fechadas, 8 abertas); épico não entra na contagem. Fechamento de issue descreve seu alcance, não prova ensaio real. A INT-01 fechou auditoria/metadados; INT-02 continua outputs/reconciliação. Nenhum responsável ou prazo é inferido.

P0 bloqueia a ação afetada; P1 é necessário ao fluxo completo; P2 é posterior. P0 não permite pular dependências. Pedido/pagamento continuam proibidos neste incremento.

| Task | Repositório/issue | Prioridade | Estado remoto | Alcance e dependência restante |
| --- | --- | --- | --- | --- |
| [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5) | api #5 | P0 | Fechada | Decisão vigente sincronizada; documentação não habilita operação |
| [OPS-01](https://github.com/Modo-Escuro/api-backend/issues/6) | api #6 | P0 | Fechada | Persistência integrada; operação/volume precisam de evidência própria |
| [INT-01](https://github.com/Modo-Escuro/api-backend/issues/7) | api #7 | P0 | Fechada | Auditoria/metadados; outputs pendentes em INT-02 |
| [RANK-01](https://github.com/Modo-Escuro/api-backend/issues/8) | api #8 | P0 | Fechada | Preferências e viabilidade |
| [RANK-02](https://github.com/Modo-Escuro/api-backend/issues/9) | api #9 | P1 | Fechada | Configuração/texto coerentes |
| [DOM-01](https://github.com/Modo-Escuro/api-backend/issues/10) | api #10 | P0 | Fechada | Centavos/limites/rateio |
| [RANK-03](https://github.com/Modo-Escuro/api-backend/issues/11) | api #11 | P1 | Fechada | Ranking e contrato |
| [API-01](https://github.com/Modo-Escuro/api-backend/issues/12) | api #12 | P0 | Fechada | Contrato v1 implementado; proposta v0 histórica |
| [DATA-01](https://github.com/Modo-Escuro/api-backend/issues/13) | api #13 | P1 | Fechada | Domínio por pessoa e exclusão |
| [RUN-01](https://github.com/Modo-Escuro/api-backend/issues/14) | api #14 | P1 | Fechada | Infraestrutura e testes #41 integrados |
| [AI-01](https://github.com/Modo-Escuro/api-backend/issues/15) | api #15 | P1 | Fechada | Gemini e montagem #35/#36 integrados; opt-in |
| [AI-02](https://github.com/Modo-Escuro/api-backend/issues/16) | api #16 | P1 | Fechada | Agente estruturado integrado |
| [GRP-01](https://github.com/Modo-Escuro/api-backend/issues/17) | api #17 | P1 | Fechada | Propostas por pessoa integradas |
| [CART-01](https://github.com/Modo-Escuro/api-backend/issues/18) | api #18 | P1 | Aberta | Código novo local; integração/INT-02 e callback pendentes |
| [BUY-01](https://github.com/Modo-Escuro/api-backend/issues/19) | api #19 | P0 | Aberta | Aprovação futura de pedido; distinta de PREPARE_CART |
| [BUY-02](https://github.com/Modo-Escuro/api-backend/issues/20) | api #20 | P0 | Aberta | Envio futuro/reconciliação; proibido neste incremento |
| [OPS-02](https://github.com/Modo-Escuro/api-backend/issues/21) | api #21 | P1 | Aberta | PR #38 mergeado; issue aberta por alcance parcial e ensaios operacionais pendentes |
| [INT-02](https://github.com/Modo-Escuro/api-backend/issues/40) | api #40 | P0 | Aberta | Gate externo de outputs por operação; não concluído por tools/list |
| [BOT-01](https://github.com/Modo-Escuro/telegram-bot/issues/1) | bot #1 | P1 | Fechada | Cliente/outbox/polling opt-in integrados |
| [BOT-02](https://github.com/Modo-Escuro/telegram-bot/issues/2) | bot #2 | P1 | Fechada | Login e retomada integrados; ensaio separado |
| [BOT-03](https://github.com/Modo-Escuro/telegram-bot/issues/3) | bot #3 | P1 | Aberta | Apresentação pode avançar; callback carrinho depende CART-01; pedido depende BUY-01/02 |
| [QA-01](https://github.com/Modo-Escuro/telegram-bot/issues/4) | bot #4 | P1 | Aberta | Validar por marcos; fechamento do briefing ainda pendente |
| [FUT-01](https://github.com/Modo-Escuro/telegram-bot/issues/5) | bot #5 | P2 | Aberta | Memória/áudio/múltiplas lojas posteriores; acesso por senha já integrado |

## Dependências que liberam ações

- CART-01 pode avançar com DATA-01/GRP-01/DOM-01/RUN-01 integradas; não precisa esperar AI-01. Sua ativação exige INT-02 e confirmação humana específica, sem bypass do legado.
- BOT-03 apresentação usa grupo/propostas já disponíveis; callback de preparação depende do contrato CART-01 integrado. A futura aprovação de pedido depende de BUY-01/BUY-02 e de novo escopo autorizado.
- BUY-02 depende de BUY-01 e contrato real de envio/status/reconciliação, não apenas de INT-01 fechada. INT-02 registra lacunas por domínio sem executar envio/pagamento.
- QA-01 começa com conversa/apresentação e evolui por marcos; o aceite de fechamento final depende do evento e das futuras entregas de pedido.

Ao concluir, registrar commit/PR e evidência por critério. Preservar IDs RN/RS/CA/DA e a StRS em validação. Não alterar fixtures/pins ou apagar histórico para obter status verde. Estado de branch local não move automaticamente uma task remota para concluída.
