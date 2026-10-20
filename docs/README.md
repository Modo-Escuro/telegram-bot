# Documentação do Ailo — bot Telegram

**Reconciliação de 20/10.** [Assistente](assistente-conversacional.md) documenta intenção, progresso, sessão e memória. API [#58](https://github.com/Modo-Escuro/api-backend/pull/58) sobre f6ef20e usa v6 e assistente único. O teste HTTP foi executado localmente e seu novo job CI fixa o SHA publicado 148b595082823288fbb713d1a6e341e32dfbffc7. Envio/pagamento seguem indisponíveis; CI/deploy/online são evidências separadas.

[Ailo: apresentação, digitação e voz](ailo-voz.md): integração de áudio opt-in e limites de ativação.

Menu atual: teclado persistente só Menu; menu inline Conta iFood, Endereços iFood, Remover pessoa, Limpar tudo, Meus dados, Ajuda/Sair e revisão quando CART-01 habilitada. Login normal conclui no navegador sem outro clique. Comandos/teclados antigos são compatibilidade, não a UX principal.

## Guias vigentes

[Cliente v1 e extensões](cliente-conversa.md): outbox, conta/sessão, memória, progresso e endereços; contratos base fixados preservados. Não existe identidade estável iFood verificada entre relogins.

[Conclusão offline CART-01](cart-01-conclusao-offline.md): confirmação de endereço integrada à revisão completa, apresentação de composição/custos finais e ensaios HTTP locais, sem ativação real.

[Continuidade automática e endereços](continuidade-enderecos.md): correção da mensagem presa, retomada após OAuth e escolha humana do endereço; publicação/CI não comprovam ativação.

A árvore local contém o [canal CART-01](cart-01-telegram.md), com revisão completa, confirmação e consulta de custos. A nova seleção digitada da sacola na API não comprova o fio completo até esse canal; integração/outputs externos ainda requerem verificação. Código local não comprova merge/ativação/ensaio real.

[Estado remoto/local](estado-remoto-local.md): versões conferidas, código integrado e CART-01 em desenvolvimento publicado. [Decisões vigentes](decisoes-conversacionais.md): carrinho real confirmado já aprovado no escopo, com outputs/ativação pendentes; envio/pagamento proibidos.

[Acesso compartilhado com senha](acesso-senha.md): entrada de qualquer usuário na conversa privada,
isolamento por conta e implantação coordenada com a API. A senha não habilita compras.

[Kanban e regras de andamento](kanban.md): tarefas prontas, dependências e acompanhamento no épico.

O desenvolvimento segue o [plano local](plano-conversacional.md) e as [decisões vigentes](decisoes-conversacionais.md). [Backlog](backlog-conversacional.md), [kanban](kanban.md) e [proposta v0](contrato-conversa-proposto.md) preservam histórico; não são consulta de issues atuais. O [épico #6](https://github.com/Modo-Escuro/telegram-bot/issues/6) é referência do planejamento, sem atualização automática por esta documentação.
[Incremento BOT-02](validacao-bot02.md): acompanhamento do login, cancelamento, desconexão e validação offline. Deploy e ensaio online são evidências separadas.
[Continuação BOT-01](bot-01-fila-duravel.md): texto livre opt-in, fila persistente e worker separado; testes HTTP contra RUN-01/DATA-01 com processador sintético. Não habilita IA em produção.
[Continuação BOT-02](bot-02-retomada-contexto.md): consulta do grupo após login operacional, com rechecagem do vínculo e sem repetir ações.
[Habilitação e ensaio BOT-02](ensaio-bot02-operacional.md): configuração persistente, limites de consumo, teste da montagem atual e roteiro humano; separa ativação de evidência operacional.

## Por onde começar

1. [Assistente](assistente-conversacional.md): implementação corrente; [remoto/local](estado-remoto-local.md) e [evidência online histórica](estado-atual.md) separam seus alcances.
2. [Arquitetura](arquitetura.md): responsabilidades dos módulos, transporte e persistência.
3. [Login iFood](login-ifood.md): conclusão no navegador, menu, estados e recuperação manual compatível.
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

## Registros históricos

- [Conversa por botões](conversa-por-botoes.md), [síntese](ux-sintese.md) e [conversa guiada](conversa-guiada.md) registram evolução do menu/intérprete anterior; não são configuração da experiência atual.
- [Validação BOT-02](validacao-bot02.md), [ensaio de habilitação](ensaio-bot02-operacional.md), [conclusão CART-01](cart-01-conclusao-offline.md) e resultados dos incrementos BOT-01/endereços preservam versões/contagens de origem. Nenhum resultado foi promovido a execução nova.
- Baseline StRS, JSONs de evidência, pins/hashes de contratos e fixtures são fontes preservadas. Esta atualização altera texto documental, não essas evidências, flags ou serviços.
