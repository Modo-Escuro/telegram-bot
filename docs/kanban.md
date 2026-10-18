# Kanban — Compra com Contexto

[Épico e quadro compartilhado](https://github.com/Modo-Escuro/telegram-bot/issues/6) · [Plano](plano-conversacional.md) · [Descrições das tarefas](backlog-conversacional.md).

Conferência inicial em **18/10/2026**: 22 tarefas abertas, sem responsáveis atribuídos. Status de início não foi presumido com base apenas na existência de código em branch. Este quadro é Markdown editável, com links para issues nos dois repositórios. Não há sincronização automática nem movimentação de cartões por arrastar.

## Quadro

| Backlog (1) | Aguardando dependências (17) | Pronto (4) | Em andamento (0) | Em revisão (0) | Concluído (0) |
| --- | --- | --- | --- | --- | --- |
| [**FUT-01**](https://github.com/Modo-Escuro/telegram-bot/issues/5) · P2<br>Evoluções futuras<br>Dep.: QA-01 | [**INT-01**](https://github.com/Modo-Escuro/api-backend/issues/7) · P0<br>Contratos e auditoria F7<br>Dep.: DEC-01<br><br>[**RANK-02**](https://github.com/Modo-Escuro/api-backend/issues/9) · P1<br>Preferências e configuração<br>Dep.: RANK-01<br><br>[**DOM-01**](https://github.com/Modo-Escuro/api-backend/issues/10) · P0<br>Centavos e limites<br>Dep.: DEC-01<br><br>[**RANK-03**](https://github.com/Modo-Escuro/api-backend/issues/11) · P1<br>Ranking e contrato<br>Dep.: DEC-01, DOM-01, RANK-02<br><br>[**DATA-01**](https://github.com/Modo-Escuro/api-backend/issues/13) · P1<br>Estado por pessoa<br>Dep.: DEC-01, OPS-01, API-01<br><br>[**RUN-01**](https://github.com/Modo-Escuro/api-backend/issues/14) · P1<br>Turnos recuperáveis<br>Dep.: OPS-01, API-01, DATA-01<br><br>[**AI-01**](https://github.com/Modo-Escuro/api-backend/issues/15) · P1<br>Escolha do modelo<br>Dep.: DEC-01, API-01<br><br>[**AI-02**](https://github.com/Modo-Escuro/api-backend/issues/16) · P1<br>Agente conversacional<br>Dep.: AI-01, RUN-01, DATA-01<br><br>[**GRP-01**](https://github.com/Modo-Escuro/api-backend/issues/17) · P1<br>Propostas coletivas<br>Dep.: DATA-01, DOM-01, RANK-03<br><br>[**CART-01**](https://github.com/Modo-Escuro/api-backend/issues/18) · P1<br>Carrinho durável<br>Dep.: INT-01, OPS-01, RUN-01, GRP-01<br><br>[**BUY-01**](https://github.com/Modo-Escuro/api-backend/issues/19) · P0<br>Aprovação humana<br>Dep.: CART-01, API-01<br><br>[**BUY-02**](https://github.com/Modo-Escuro/api-backend/issues/20) · P0<br>Envio e reconciliação<br>Dep.: INT-01, BUY-01<br><br>[**OPS-02**](https://github.com/Modo-Escuro/api-backend/issues/21) · P1<br>Operação e liberação<br>Dep.: RUN-01, AI-02, CART-01<br><br>[**BOT-01**](https://github.com/Modo-Escuro/telegram-bot/issues/1) · P1<br>Texto livre sem espera<br>Dep.: API-01, RUN-01<br><br>[**BOT-02**](https://github.com/Modo-Escuro/telegram-bot/issues/2) · P1<br>Retorno do login<br>Dep.: API-01<br><br>[**BOT-03**](https://github.com/Modo-Escuro/telegram-bot/issues/3) · P1<br>Revisão e botões<br>Dep.: BOT-01, GRP-01, CART-01, BUY-01<br><br>[**QA-01**](https://github.com/Modo-Escuro/telegram-bot/issues/4) · P1<br>Ensaio e demonstração<br>Dep.: BOT-02, BOT-03, AI-02, BUY-02, OPS-02 | [**DEC-01**](https://github.com/Modo-Escuro/api-backend/issues/5) · P0<br>Decisões de produto<br><br>[**OPS-01**](https://github.com/Modo-Escuro/api-backend/issues/6) · P0<br>Persistência da API<br><br>[**RANK-01**](https://github.com/Modo-Escuro/api-backend/issues/8) · P0<br>Preferência sem bloqueio<br><br>[**API-01**](https://github.com/Modo-Escuro/api-backend/issues/12) · P0<br>Contrato de conversa | — | — | — |

As 22 tarefas aparecem uma vez. O épico não conta como tarefa. PRs de documentação [bot #7](https://github.com/Modo-Escuro/telegram-bot/pull/7) e [API #22](https://github.com/Modo-Escuro/api-backend/pull/22) são entregas documentais separadas; sua revisão não significa que a implementação esteja em andamento.

## Primeiro ciclo sugerido

| Ordem sugerida | Tarefa | Resultado esperado para liberar próximas etapas |
| --- | --- | --- |
| 1 | [OPS-01](https://github.com/Modo-Escuro/api-backend/issues/6) | Preservar vínculos antes do próximo redeploy e validar recuperação |
| 2 | [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5) | Decidir recorte, rateio, evidência alimentar e fronteira da demo |
| 3 | [API-01](https://github.com/Modo-Escuro/api-backend/issues/12) | Acordar eventos, estados e ações entre API e bot |
| 4 | [RANK-01](https://github.com/Modo-Escuro/api-backend/issues/8) | Corrigir preferência opcional que bloqueia candidato |

Essas quatro tarefas não têm predecessoras no grafo e podem ser distribuídas conforme a capacidade da equipe. A ordem acima é uma sugestão de foco, sem assumir responsável ou prazo.

## Como movimentar

| Coluna | Entrada / saída |
| --- | --- |
| Backlog | Evoluções fora do ciclo atual. P2/FUT-01 permanece aqui até decisão de priorização. |
| Aguardando dependências | Tarefa necessária, mas ainda sem predecessoras concluídas ou decisão/contrato obrigatório. Registrar bloqueio e próxima ação na issue. |
| Pronto | Dependências concluídas, escopo compreendido e critérios de aceite executáveis. |
| Em andamento | Pessoa assume a tarefa e registra plano de execução na issue. Uma branch antiga sozinha não comprova início desta tarefa. |
| Em revisão | PR e evidências disponíveis, checks relevantes executados e critérios conferidos. Pendência material volta ao andamento ou às dependências. |
| Concluído | Issue fechada com evidência dos critérios e limitações registradas. Documentação/testes simulados não comprovam operação real. |

Ao iniciar uma tarefa, registrar responsável, data e ligação para branch/PR. Recomenda-se uma tarefa ativa por pessoa e limite inicial de duas em desenvolvimento e duas em revisão; ajustar explicitamente à capacidade real da equipe.

Ao concluir, rever todas as dependentes: só mover para Pronto quando todas as predecessoras necessárias estiverem concluídas. P0 é urgência/gate para a ação afetada; não permite pular dependências. BUY-01/BUY-02 continuam aguardando a sacola apesar de serem P0.

## Manutenção compartilhada

1. Atualizar o estado e as evidências na issue.
2. Mover o link do cartão entre colunas no épico; manter uma única ocorrência por tarefa.
3. Se a documentação for atualizada, refletir o mesmo retrato neste arquivo e registrar a data.
4. Não marcar conclusão automaticamente a partir de um merge que só altera documentação.
5. Se houver impedimento externo, registrar motivo e condição de desbloqueio; não mover a tarefa para concluída.
6. Não atribuir pessoas ou prazos sem acordo da equipe.

O quadro no épico é o ponto operacional de atualização; este arquivo documenta o retrato inicial e as regras. As issues são a fonte dos detalhes de execução.

## Configuração equivalente no GitHub Projects

Se a equipe desejar cartões arrastáveis, criar manualmente um Project de organização com layout Board, título **Compra com Contexto — Entrega**, Status com as seis colunas acima e campos Priority (P0/P1/P2), Marco (M0–M4/Posterior), Repository e Assignees. Adicionar as 22 issues existentes pelo backlog; não recriar tasks. Configurar a vista por Status e manter as dependências nas descrições. Não configurar automação que conclua implementação ao integrar os PRs documentais.

Esta publicação não cria um Project nativo nem instala integrações.
