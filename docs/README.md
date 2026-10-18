[Ailo: apresentação, digitação e voz](ailo-voz.md): integração de áudio opt-in e limites de ativação.

**Atualização de UX em 18/10/2026:** navegação por botões e retorno do login sem confirmação duplicada, conforme pedido do usuário. Ver [conversa por botões](conversa-por-botoes.md). Instruções antigas com comandos permanecem como histórico/compatibilidade.

# Documentação do bot Compra com Contexto

Esta revisão altera somente documentação. A implementação CART-01 local, suas rotas e resultados de testes não fazem parte das mains remotas conferidas.

[Estado remoto/local](estado-remoto-local.md): versões conferidas, código integrado e CART-01 ainda local. [Decisões vigentes](decisoes-conversacionais.md): carrinho real confirmado já aprovado no escopo, com outputs/ativação pendentes; envio/pagamento proibidos.

[Acesso compartilhado com senha](acesso-senha.md): entrada de qualquer usuário na conversa privada,
isolamento por conta e implantação coordenada com a API. A senha não habilita compras.

[Kanban e regras de andamento](kanban.md): tarefas prontas, dependências e acompanhamento no épico.

O desenvolvimento da conversa passa pelo [plano integrado](plano-conversacional.md), [backlog com issues e prioridades](backlog-conversacional.md), [decisões abertas](decisoes-conversacionais.md) e [contrato proposto](contrato-conversa-proposto.md). O [épico #6](https://github.com/Modo-Escuro/telegram-bot/issues/6) acompanha API e bot. Documentação e tarefas publicadas não significam implementação concluída.
[Incremento BOT-02](validacao-bot02.md): acompanhamento do login, cancelamento, desconexão e validação offline. Deploy e ensaio online são evidências separadas.
[Continuação BOT-01](bot-01-fila-duravel.md): texto livre opt-in, fila persistente e worker separado; testes HTTP contra RUN-01/DATA-01 com processador sintético. Não habilita IA em produção.
[Continuação BOT-02](bot-02-retomada-contexto.md): consulta do grupo após login operacional, com rechecagem do vínculo e sem repetir ações.
[Habilitação e ensaio BOT-02](ensaio-bot02-operacional.md): configuração persistente, limites de consumo, teste da montagem atual e roteiro humano; separa ativação de evidência operacional.

## Por onde começar

1. [Estado atual](estado-atual.md): implementação, ensaio real, evidência sanitizada e limites.
2. [Arquitetura](arquitetura.md): responsabilidades dos módulos, transporte e persistência.
3. [Login iFood](login-ifood.md): comandos, botão humano, estados e recuperação.
4. [Operação na Railway](deploy-railway.md): serviços, variáveis, deploy e transferência do estado.
5. [Execução local](executar-bot.md): configuração, diagnóstico e prevenção de polling simultâneo.
6. [Plano da demo](plano-demo.md): próximos incrementos e critérios de conclusão.
7. [Regras preservadas](regras-preservadas.md): requisitos, restrições e decisões ainda abertas.

## Como interpretar o status

- **Implementado:** comportamento localizado no código deste repositório ou no backend identificado.
- **Verificado online:** observação real com origem e versão de referência registradas em [estado atual](estado-atual.md).
- **Informado pelo usuário:** etapa humana relatada, como aprovação do cadastro OAuth e uso do Telegram.
- **Planejado:** requisito ou proposta ainda sem entrega demonstrada.

Operações anunciadas ou permitidas não provam sua execução. Uma sessão operacional não autoriza compra. Não registrar tokens, URLs OAuth, códigos, identidade ou dados da conta como evidência.

## Baseline e contratos

O [cliente de conversa v1.0](cliente-conversa.md) está integrado à outbox e ao polling opt-in da BOT-01, mergeada na PR #10. A CI valida rotas RUN-01/DATA-01 com processador sintético; isso não comprova conversa com IA no bot online.

A [StRS v0.2](baseline/stakeholder-requirements-specification.md) continua em validação. Os IDs e as decisões abertas são preservados. [Proveniência e hashes](baseline/proveniencia.json) identificam as cópias históricas, incluindo o snapshot OpenCode que não estava versionado no repositório original. Não editar essas cópias para atualizar status operacional.

O [contrato bot→API](https://github.com/Modo-Escuro/api-backend/blob/f3b8b5561acc0c0ae5e9efe12b52acc2f29bf218/docs/bot-api.md) identifica a API remota conferida. Os commits/pins históricos dos testes do consumidor são preservados e não significam que a CI ensaiou esta main atual. Não presumir que rotas propostas ou ferramentas externas descritas estejam disponíveis ou implementadas no bot.
