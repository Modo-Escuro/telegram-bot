# BOT-02 — implementação e validação

**Registro histórico da primeira etapa**, já incorporada à `main` pelas PRs #8/#10. A continuação e seus testes estão em [retomada de contexto](bot-02-retomada-contexto.md); as pendências descritas abaixo representam aquele incremento, não o estado de desenvolvimento atual.

Issue: [telegram-bot#2](https://github.com/Modo-Escuro/telegram-bot/issues/2). Base: `main@e280807`. Branch: `codex/bot-02-retorno-login`. Validação local em 18/10/2026, Python 3.12/Windows.

## Resultado

Depois de `/conectar`, a mensagem que contém o link passa a ser acompanhada. Quando GET status retorna a autorização, o bot edita essa mesma mensagem com a conta mascarada e o botão humano. Não confirma automaticamente nem gera nova notificação push. `/confirmar` e `/ifood` recuperam a apresentação quando o acompanhamento não pode continuar.

Cancelamento e desconexão usam as rotas já implementadas em `api-backend@686300d`: POST `/api/bot/ifood/cancel` e DELETE `/api/bot/ifood/link`. A primeira cancela a tentativa e preserva o vínculo; a segunda remove o vínculo local e preserva uma tentativa pendente, sem alegar revogação no provedor. Botões com referência antiga são rejeitados após consulta do estado atual.

## Persistência e recuperação

Migração aditiva cria uma tabela singleton de acompanhamento no SQLite existente. Conserva cursor e ações; teste com esquema anterior verifica os registros e integridade. A tabela guarda somente organizador, attemptId, messageId, fase, início, validade e próxima consulta. Não guarda confirmationId, URL, texto, identidade, token ou código OAuth.

O bot consulta status a cada pelo menos 5 segundos; long polling usa 3 segundos enquanto há tentativa acompanhada, e GET automático tem timeout de 5 segundos. O total de acompanhamento é limitado a 20 minutos, respeitando `attempt.expiresAt` e sua transição de autorização para confirmação.

Reinício retoma a tentativa salva, sem novo connect. Mesma fase não reedita a mensagem; falha transitória tenta editar o mesmo ID e respeita retry_after. Erro permanente, mensagem apagada ou prazo encerrado interrompem o acompanhamento, mantendo o caminho manual. Uma resposta perdida de envio Telegram ainda pode repetir texto no replay; o registro prévio de update_id impede repetir a mutação correspondente.

## Verificações executadas

| Verificação | Resultado |
| --- | --- |
| `python -m unittest discover -s tests -q` | 69 testes passaram: 39 anteriores e 30 novos |
| `python -m ruff check --no-cache .` | passou |
| `python -m ruff format --check --no-cache src tests` | 11 arquivos formatados |
| `python -m telegram_bot --help` | passou; sem diagnóstico remoto ou polling |
| `git diff --check` | passou |

Testes usam Telegram, backend e relógio falsos. Cobrem atualização do botão sem confirmar, restart antes/depois da edição, repetição de fase, expiração e transição tardia, limite total, troca de tentativa/organizador, mensagem apagada, rate limit, falha de envio, comandos e callbacks autorizados/obsoletos, replay após timeout, semântica dos endpoints, schema de prazo, privacidade e migração do banco.

O teste de migração inicialmente revelou uma conexão de fixture aberta no Windows; corrigido o fechamento e repetida a suíte, com todos os 69 testes passando. Isso não era uma falha da migração de produção.

## Alcance e pendências

- Nenhum login, polling, alteração de banco online ou deploy foi executado nesta validação.
- O acompanhamento continua no loop único; chamadas manuais e rede ainda podem atrasar eventos. Fila assíncrona de conversa é BOT-01.
- Não existe contexto de compra a retomar nem carrinho/aprovação neste adaptador. Retomar a conversa e invalidar ações de compra após mudança de linkId dependem das tarefas de conversa/compra. Não marcar esse critério futuro como validado.
- A API não possui parâmetro condicional de attemptId/linkId para cancelamento/desconexão. A rechecagem do bot evita uso de botões obsoletos no worker único, mas não garante CAS diante de outro cliente externo que troque a conta simultaneamente.
- API-01 continua dependência para a retomada futura do contexto. O acompanhamento e os comandos deste incremento usam somente o contrato existente.

## Ensaio humano após merge/deploy

1. `/conectar`, abrir navegador e autorizar; voltar à mensagem do login e observar o botão atualizado.
2. Conferir identidade, clicar e consultar `/verificar`; login não aprova compra.
3. Iniciar reconexão e usar `/cancelar`; conferir que o vínculo anterior permanece.
4. Com tentativa pendente, usar `/desconectar`; conferir remoção do vínculo e preservação da tentativa. Encerrá-la com `/cancelar` se desejado.
5. Com backend falso/local, ensaiar expiração/restart/falha de rede antes de testar interrupções em um serviço real.

Não iniciar outra instância local com o token do bot online. A evidência histórica anterior continua em `estado-atual.md`; não foi substituída por este teste offline.
