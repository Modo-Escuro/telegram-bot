# Kanban — retrato conferido em 18/10/2026

> Quadro histórico, não sincronizado com GitHub nesta revisão. “Atual” no corpo refere-se a 18/10; não usar essas contagens para afirmar o estado presente. Implementação local e prioridade corrente em [plano](plano-conversacional.md) e [assistente](assistente-conversacional.md).

[Backlog com as 23 tarefas](backlog-conversacional.md) · [Plano](plano-conversacional.md) · [Remoto/local](estado-remoto-local.md) · [Épico](https://github.com/Modo-Escuro/telegram-bot/issues/6).

O quadro inicial de 22 tarefas todas abertas ficou desatualizado. O retrato atual tem **15 fechadas e 8 abertas**, após adicionar INT-02 e integrar RUN-01 #41; OPS-02 #38 foi mergeado, mas sua issue continua aberta. Este arquivo não sincroniza automaticamente; as issues continuam fonte do andamento.

| Grupo | Tarefas | Evidência/limite |
| --- | --- | --- |
| Fechadas no GitHub (15) | API DEC-01, OPS-01, INT-01, RANK-01/02/03, DOM-01, API-01, DATA-01, RUN-01, AI-01/02, GRP-01; bot BOT-01/02 | Código/documentos integrados conforme o alcance; INT-01 só auditoria/metadados. Não significa todos os ensaios online concluídos |
| Abertas necessárias (7) | API INT-02, CART-01, BUY-01, BUY-02, OPS-02; bot BOT-03, QA-01 | PR OPS-02 #38 mergeado, issue ainda aberta; código CART-01 auditado apenas local; outputs/callbacks/ensaio pendentes |
| Posterior (1) | FUT-01 | Não bloqueia o épico; acesso por senha já integrado não deve ser listado como futuro |

Não inferir responsável, coluna “em andamento” ou aprovação só pela existência de branch. Publicar PR não equivale a merge. Para classificar pronto/revisão/concluído, conferir dependências, checks e evidência do comportamento afetado.

Prioridades imediatas: INT-02 e integração CART-01; apresentação BOT-03 pode avançar sem aguardar aprovação/envio futuros. Zero escrita sem confirmação humana específica; zero envio/pagamento neste incremento. Não mover tarefa bloqueada por evidência externa para concluída.

Atualizar este retrato com data e SHAs; preservar o [quadro inicial no histórico](https://github.com/Modo-Escuro/telegram-bot/blob/9314c72e1324a36da09c014e74f98a470dde6306/docs/kanban.md). Não há Project nativo criado por esta revisão.
