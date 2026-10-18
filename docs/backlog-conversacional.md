# Backlog de desenvolvimento e dependências

[Plano integrado](plano-conversacional.md) · [Épico](https://github.com/Modo-Escuro/telegram-bot/issues/6).

Todas as tarefas abaixo foram criadas no GitHub e estavam abertas nesta publicação. O status vivo está nas issues; esta tabela registra escopo, prioridade e dependências. Cada issue contém problema, escopo, critérios de aceite, validação, fora de escopo e rastreabilidade. Sem atribuição nominal ou prazo inventado.

## Prioridades

- **P0:** bloqueio de integridade, contrato ou habilitação; resolver antes da ação afetada. BUY-01/02 são P0 antes de qualquer envio, mas têm predecessoras.
- **P1:** implementação necessária à jornada principal; não é opcional para concluir a demo completa.
- **P2:** evolução posterior, sem bloquear o épico.

Os códigos P0/P1/P2 estão no título e corpo das issues; os marcos M0–M4 são agrupamentos lógicos, não milestones do GitHub criados automaticamente.

## Tarefas

| ID / issue | Repositório | Prioridade | Marco | Entrega | Depende de |
| --- | --- | --- | --- | --- | --- |
| [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5) | api-backend | P0 | M0 | Fechar decisões de grupo, rateio, evidência alimentar e fronteira da demo | — |
| [OPS-01](https://github.com/Modo-Escuro/api-backend/issues/6) | api-backend | P0 | M0 | Migrar vínculos para armazenamento persistente com recuperação verificada | — |
| [INT-01](https://github.com/Modo-Escuro/api-backend/issues/7) | api-backend | P0 | M0 | Auditar F7 e validar contratos reais de carrinho, envio e reconciliação | [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5) |
| [RANK-01](https://github.com/Modo-Escuro/api-backend/issues/8) | api-backend | P0 | M0 | Impedir que preferências opcionais bloqueiem configurações válidas | — |
| [RANK-02](https://github.com/Modo-Escuro/api-backend/issues/9) | api-backend | P1 | M1 | Corrigir preferências textuais e pontuar somente a configuração avaliada | [RANK-01](https://github.com/Modo-Escuro/api-backend/issues/8) |
| [DOM-01](https://github.com/Modo-Escuro/api-backend/issues/10) | api-backend | P0 | M1 | Aplicar centavos inteiros e validar limites obrigatórios antes do ranking | [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5) |
| [RANK-03](https://github.com/Modo-Escuro/api-backend/issues/11) | api-backend | P1 | M1 | Alinhar economia, rapidez e evidência ao ranking e versionar sua resposta | [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5), [DOM-01](https://github.com/Modo-Escuro/api-backend/issues/10), [RANK-02](https://github.com/Modo-Escuro/api-backend/issues/9) |
| [API-01](https://github.com/Modo-Escuro/api-backend/issues/12) | api-backend | P0 | M0 | Especificar e validar o contrato versionado de conversa, eventos e ações | — |
| [DATA-01](https://github.com/Modo-Escuro/api-backend/issues/13) | api-backend | P1 | M1 | Persistir compra, participantes, restrições e evidências com versionamento | [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5), [OPS-01](https://github.com/Modo-Escuro/api-backend/issues/6), [API-01](https://github.com/Modo-Escuro/api-backend/issues/12) |
| [RUN-01](https://github.com/Modo-Escuro/api-backend/issues/14) | api-backend | P1 | M1 | Implementar processamento durável de turnos e recuperação após falhas | [OPS-01](https://github.com/Modo-Escuro/api-backend/issues/6), [API-01](https://github.com/Modo-Escuro/api-backend/issues/12), [DATA-01](https://github.com/Modo-Escuro/api-backend/issues/13) |
| [AI-01](https://github.com/Modo-Escuro/api-backend/issues/15) | api-backend | P1 | M1 | Selecionar modelo por avaliação de conversa, custo, latência e dados | [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5), [API-01](https://github.com/Modo-Escuro/api-backend/issues/12) |
| [AI-02](https://github.com/Modo-Escuro/api-backend/issues/16) | api-backend | P1 | M2 | Implementar agente conversacional com ações estruturadas e ferramentas controladas | [AI-01](https://github.com/Modo-Escuro/api-backend/issues/15), [RUN-01](https://github.com/Modo-Escuro/api-backend/issues/14), [DATA-01](https://github.com/Modo-Escuro/api-backend/issues/13) |
| [GRP-01](https://github.com/Modo-Escuro/api-backend/issues/17) | api-backend | P1 | M2 | Compor propostas coletivas com cobertura por pessoa e custo agregado | [DATA-01](https://github.com/Modo-Escuro/api-backend/issues/13), [DOM-01](https://github.com/Modo-Escuro/api-backend/issues/10), [RANK-03](https://github.com/Modo-Escuro/api-backend/issues/11) |
| [CART-01](https://github.com/Modo-Escuro/api-backend/issues/18) | api-backend | P1 | M3 | Integrar F7 com elegibilidade por pessoa e estado durável de carrinho | [INT-01](https://github.com/Modo-Escuro/api-backend/issues/7), [OPS-01](https://github.com/Modo-Escuro/api-backend/issues/6), [RUN-01](https://github.com/Modo-Escuro/api-backend/issues/14), [GRP-01](https://github.com/Modo-Escuro/api-backend/issues/17) |
| [BUY-01](https://github.com/Modo-Escuro/api-backend/issues/19) | api-backend | P0 | M3 | Vincular aprovação humana à revisão atual e consumir autorização atomicamente | [CART-01](https://github.com/Modo-Escuro/api-backend/issues/18), [API-01](https://github.com/Modo-Escuro/api-backend/issues/12) |
| [BUY-02](https://github.com/Modo-Escuro/api-backend/issues/20) | api-backend | P0 | M3 | Implementar envio idempotente e reconciliação de resultado desconhecido | [INT-01](https://github.com/Modo-Escuro/api-backend/issues/7), [BUY-01](https://github.com/Modo-Escuro/api-backend/issues/19) |
| [OPS-02](https://github.com/Modo-Escuro/api-backend/issues/21) | api-backend | P1 | M3 | Instrumentar operação, limites, retenção e liberação gradual | [RUN-01](https://github.com/Modo-Escuro/api-backend/issues/14), [AI-02](https://github.com/Modo-Escuro/api-backend/issues/16), [CART-01](https://github.com/Modo-Escuro/api-backend/issues/18) |
| [BOT-01](https://github.com/Modo-Escuro/telegram-bot/issues/1) | telegram-bot | P1 | M2 | Receber texto livre e acompanhar turnos sem bloquear o polling | [API-01](https://github.com/Modo-Escuro/api-backend/issues/12), [RUN-01](https://github.com/Modo-Escuro/api-backend/issues/14) |
| [BOT-02](https://github.com/Modo-Escuro/telegram-bot/issues/2) | telegram-bot | P1 | M2 | Retomar login no Telegram e oferecer cancelamento e desconexão claros | [API-01](https://github.com/Modo-Escuro/api-backend/issues/12) |
| [BOT-03](https://github.com/Modo-Escuro/telegram-bot/issues/3) | telegram-bot | P1 | M3 | Apresentar grupo, propostas, revisão e aprovação humana por botões | [BOT-01](https://github.com/Modo-Escuro/telegram-bot/issues/1), [GRP-01](https://github.com/Modo-Escuro/api-backend/issues/17), [CART-01](https://github.com/Modo-Escuro/api-backend/issues/18), [BUY-01](https://github.com/Modo-Escuro/api-backend/issues/19) |
| [QA-01](https://github.com/Modo-Escuro/telegram-bot/issues/4) | telegram-bot | P1 | M4 | Validar jornada integrada, falhas e demonstração com evidência sanitizada | [BOT-02](https://github.com/Modo-Escuro/telegram-bot/issues/2), [BOT-03](https://github.com/Modo-Escuro/telegram-bot/issues/3), [AI-02](https://github.com/Modo-Escuro/api-backend/issues/16), [BUY-02](https://github.com/Modo-Escuro/api-backend/issues/20), [OPS-02](https://github.com/Modo-Escuro/api-backend/issues/21) |
| [FUT-01](https://github.com/Modo-Escuro/telegram-bot/issues/5) | telegram-bot | P2 | Posterior | Avaliar memória entre compras, áudio, novos canais e múltiplos restaurantes | [QA-01](https://github.com/Modo-Escuro/telegram-bot/issues/4) |

## Sequência operacional

1. Iniciar [OPS-01](https://github.com/Modo-Escuro/api-backend/issues/6), [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5), [API-01](https://github.com/Modo-Escuro/api-backend/issues/12) e [RANK-01](https://github.com/Modo-Escuro/api-backend/issues/8).
2. Investigar F7/contratos em [INT-01](https://github.com/Modo-Escuro/api-backend/issues/7) assim que definidos ambiente e fronteira; não esperar a conversa.
3. Avançar domínio/estado/eventos e escolha do modelo conforme as dependências; protótipos isolados podem usar mocks identificados.
4. Integrar [BOT-01](https://github.com/Modo-Escuro/telegram-bot/issues/1), [AI-02](https://github.com/Modo-Escuro/api-backend/issues/16) e [GRP-01](https://github.com/Modo-Escuro/api-backend/issues/17) para a primeira conversa útil, preservando estado.
5. Liberar sacola apenas com contratos, elegibilidade e persistência. Liberar envio somente após [BUY-01](https://github.com/Modo-Escuro/api-backend/issues/19) e [BUY-02](https://github.com/Modo-Escuro/api-backend/issues/20).
6. Concluir [QA-01](https://github.com/Modo-Escuro/telegram-bot/issues/4) com evidência e estado final do evento; [FUT-01](https://github.com/Modo-Escuro/telegram-bot/issues/5) é posterior.

## Regras para desenvolvimento e encerramento

- Branch/PR de implementação referencia a issue e o commit base. Não alterar a main de produção antes de preservar vínculos.
- Fechar com evidência dos critérios e checks relevantes; mencionar explicitamente o que foi só simulado.
- Não fechar tarefa bloqueada por contrato externo como “concluída”; registrar lacuna e próximo passo.
- Gate de segurança é obrigatório mesmo que implementação comece antes com stub.
- Manter commits da branchBruna e F7 identificados; resolver conflitos entre ranking, carrinho e auth com testes de integração.
- Preservar issues api-backend#1–#3 fechadas como histórico; bugs herdados novos têm tarefas próprias.
- Alteração de dependência ou política exige atualizar issue e este plano; não reescrever snapshots históricos.

## Rastreabilidade resumida

| Necessidade | Tarefas principais |
| --- | --- |
| RN01–RN03: restrições e dados insuficientes | [RANK-01](https://github.com/Modo-Escuro/api-backend/issues/8), [DOM-01](https://github.com/Modo-Escuro/api-backend/issues/10), [DATA-01](https://github.com/Modo-Escuro/api-backend/issues/13), [GRP-01](https://github.com/Modo-Escuro/api-backend/issues/17) |
| RN04, RS17: custos e limites | [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5), [DOM-01](https://github.com/Modo-Escuro/api-backend/issues/10), [RANK-03](https://github.com/Modo-Escuro/api-backend/issues/11), [GRP-01](https://github.com/Modo-Escuro/api-backend/issues/17), [CART-01](https://github.com/Modo-Escuro/api-backend/issues/18) |
| RN05, RS07, RS26: propostas e explicações | [RANK-02](https://github.com/Modo-Escuro/api-backend/issues/9), [RANK-03](https://github.com/Modo-Escuro/api-backend/issues/11), [GRP-01](https://github.com/Modo-Escuro/api-backend/issues/17), [BOT-03](https://github.com/Modo-Escuro/telegram-bot/issues/3) |
| RN06, RS20: mudança e revisão | [DATA-01](https://github.com/Modo-Escuro/api-backend/issues/13), [RUN-01](https://github.com/Modo-Escuro/api-backend/issues/14), [BUY-01](https://github.com/Modo-Escuro/api-backend/issues/19), [BOT-03](https://github.com/Modo-Escuro/telegram-bot/issues/3) |
| RN07, RS15–RS19: cobertura individual | [DEC-01](https://github.com/Modo-Escuro/api-backend/issues/5), [GRP-01](https://github.com/Modo-Escuro/api-backend/issues/17) |
| RS22: dados externos e autoridade da IA | [API-01](https://github.com/Modo-Escuro/api-backend/issues/12), [AI-02](https://github.com/Modo-Escuro/api-backend/issues/16), [BUY-01](https://github.com/Modo-Escuro/api-backend/issues/19) |
| RS23/RS25/RS27: operação, rastreio e desconhecido | [OPS-01](https://github.com/Modo-Escuro/api-backend/issues/6), [RUN-01](https://github.com/Modo-Escuro/api-backend/issues/14), [BUY-02](https://github.com/Modo-Escuro/api-backend/issues/20), [OPS-02](https://github.com/Modo-Escuro/api-backend/issues/21), [QA-01](https://github.com/Modo-Escuro/telegram-bot/issues/4) |
| RS01/RS02: perfil histórico, escopo adiado | [FUT-01](https://github.com/Modo-Escuro/telegram-bot/issues/5) |
