# Decisões vigentes e pendências

Revisão de 18/10/2026. [Remoto/local](estado-remoto-local.md) · [DEC-01 revisada da API](https://github.com/Modo-Escuro/api-backend/blob/codex/revisao-escopo-cart01/docs/decisoes-conversacionais.md) · [CART-01 #18](https://github.com/Modo-Escuro/api-backend/issues/18).

A equipe aprovou carrinho real somente após confirmação humana PREPARE_CART, distinta de pedido. Envio/pagamento e alteração de produção continuam fora deste incremento. A árvore local atual contém assistente e CART-01 opt-in; isso não comprova merge/deploy/outputs. Referências remotas acima são do retrato de 18/10, não consulta atual.

| Tema | Estado vigente |
| --- | --- |
| Papéis/DA05 | Um organizador por compra; acesso por senha com conversas/vínculos/filas isolados já integrado; participantes declarados pelo organizador |
| Rateio/DA04 | Política determinística D3/DOM-01 em centavos; tetos coletivos/individuais simultâneos; custo desconhecido não valida orçamento completo |
| Escopo/DA06 | Uma compra ativa, loja e endereço por organizador; sem pagamento/envio neste incremento |
| Evidência/DA03 | Obrigatória insuficiente bloqueia o item para a pessoa; não inventar contato com restaurante |
| Dados/DA07 | DATA-01/exclusão D7 integradas; preservação de desconhecido e operação/backup exigem cuidado próprio |
| Modelo/TEC-02 | Gemini no assistente único da API local; roteador/planejador com limites compartilhados e opt-ins; ensaio online separado |
| Contrato/TEC-03 | API-01 v1 implementada; v0 proposta preservada como histórico; pins de testes não foram alterados |
| Contratos externos/DA09 | INT-01 fechada pela auditoria/metadados; INT-02 #40 mantém outputs e reconciliação pendentes |
| Fronteira final/DA10 | Carrinho real confirmado é escopo aprovado; não comprova pedido/pagamento nem encerra o fechamento exigido pelo briefing |
| Metas/DA08 | D10 distingue recomendação, segurança/rateio, ensaio de carrinho e efeitos externos; não usar p95 de inferência como ponta a ponta |
| Perfil/DA01 | Memória seletiva por vínculo/pessoa/finalidade implementada localmente; novo fato exige declaração verificável. Não há continuidade entre relogins por identidade iFood estável nem importação automática de perfil comportamental |
| Sessão do evento | Capturar/conservar sessionRef em outbox/replay; não transferir mensagem de uma conta para outra. Sem extensão há compatibilidade sem associação por evento |

O [registro inicial](https://github.com/Modo-Escuro/telegram-bot/blob/9314c72e1324a36da09c014e74f98a470dde6306/docs/decisoes-conversacionais.md) preserva as perguntas/alternativas anteriores. A StRS em baseline continua em validação; não atualizar seu conteúdo/hashes para refletir status operacional.
