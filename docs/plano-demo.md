# Plano da demo e próximos incrementos

**Atualização de planejamento — 18/10/2026:** a decomposição executável, prioridades, dependências e critérios estão no [plano conversacional](plano-conversacional.md) e no [backlog](backlog-conversacional.md). A sequência abaixo é o contexto do incremento anterior; o plano novo inclui revisão da branchBruna e reaproveitamento condicionado da F7, sem alterar a evidência histórica de login.
**Incremento BOT-02:** o código desta branch acrescenta acompanhamento por edição da mensagem de login, cancelamento e desconexão. O relato abaixo conserva o estado observado anteriormente; não comprova deploy deste incremento. Comportamento e limites novos em [login iFood](login-ifood.md#acompanhamento-bot-02).

[Índice](README.md) · [Estado atual](estado-atual.md) · [Regras](regras-preservadas.md)

Objetivo: organizar compra em grupo, alterar orçamento ou itens preservando restrições individuais, revisar a sacola e enviar somente após aprovação humana válida no ambiente autorizado do evento.

## Entregas concluídas e limites

| Entrega | Evidência e alcance |
| --- | --- |
| Canal Telegram privado | Implementado, testes simulados e respostas online confirmadas pelo usuário |
| Worker Railway e SQLite | Bot online; volume `/data`, transferência inicial com integridade conferida |
| Cliente HTTP de login | Contrato revisado para backend `686300d`; sem OAuth duplicado no bot |
| Login com botão humano | Ensaio real concluído; status autenticado confirmou sessão operacional |

Expiração, refresh, reconexão, indisponibilidade e desconexão não foram todos ensaiados online. As rotas de cancelamento/desconexão existem no backend, mas não têm comandos no bot. Participantes, agente de compra, sacola e pedido continuam pendentes.

## Ordem de execução proposta

1. **Persistir vínculos da API.** Preservar arquivos existentes antes de adicionar volume e mudar `IFOOD_LINKS_DIR`; ensaiar reinício controlado, consulta e nova verificação da mesma conexão. Não perder a conta já conectada por uma migração sem cópia.
2. **Fechar o contrato de conversa e grupo.** Definir eventos, estado e respostas entre Telegram e API. O contrato do login já existe; conversa, sacola e aprovação não têm rotas acordadas. Não presumir `/chat` ou `/approve`.
3. **Definir o recorte de grupo.** Decidir explicitamente rateio, conciliação entre limites individuais e coletivo, papéis e quantidade de restaurantes. São decisões abertas da StRS, não escolhas aprovadas por este plano.
4. **Implementar participantes, orçamento e restrições por pessoa.** Coleta no Telegram, persistência no backend e bloqueios determinísticos antes do ranking. O modelo não afrouxa restrição obrigatória por conta própria.
5. **Ensaiar leitura e recomendação.** Validar `listAddresses` → `searchOffers` → `getItem` e sua apresentação no bot, sem dados privados nas evidências. `OFFERS_EVALUATE` liberada não comprova essa execução. Preço de listagem não é total confirmado de pedido.
6. **Integrar sacola e revisão.** Confirmar contratos externos, `getItem` antes de adicionar e listagens de entrega/pagamento/cupom antes de selecionar. `setVoucher` é mutação. Incluir custos suportados em centavos e distinguir estimativa de cotação confirmada.
7. **Aprovar e enviar.** Vincular aprovação ao responsável, conta/link, versão, itens, total e validade. Toda mudança invalida a aprovação. Timeout remoto exige resultado desconhecido e reconciliação antes de reenvio.
8. **Ensaiar a demo completa.** Mudança de orçamento, incompatibilidade alimentar, dado ausente, botão antigo, clique repetido e timeout. Confirmar resultado por fonte confiável; não declarar pedido real a partir de texto do agente.

A próxima entrega recomendada é a persistência da API, seguida do contrato de conversa. Nenhuma das etapas futuras é funcionalidade concluída. A aprovação do cadastro OAuth não aprova uma compra.

## Dados necessários no contrato futuro

- Evento: identificador de deduplicação, origem Telegram validada, sessão, texto ou ação.
- Resposta: mensagem, opções elegíveis, participantes atendidos/bloqueados, estado, versão, custos em centavos, validade e ações permitidas.
- Aprovação: referência opaca à revisão, organizador autenticado e registro verificável do clique; nunca autorização gerada pelo modelo.
- Resultado: não enviado, aguardando aprovação, enviando, confirmado, falhou ou resultado desconhecido; regras explícitas de recuperação.

A deduplicação atual dos updates não substitui idempotência no provedor. Intenções distintas com o mesmo valor continuam legítimas.

## Preservação

A [StRS v0.2](baseline/stakeholder-requirements-specification.md) permanece em validação. Preservar IDs, requisitos e decisões abertas. [Proveniência e hashes](baseline/proveniencia.json) identificam o baseline; não reescrevê-lo para refletir o deploy atual. O protótipo original e seus arquivos não rastreados permanecem preservados.
