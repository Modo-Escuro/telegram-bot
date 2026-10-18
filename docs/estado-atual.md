# Estado de código e evidências online

[Estado remoto/local](estado-remoto-local.md) registra o código atual conferido: bot #13/#14 integrado; API com montagem AI-01 e RUN-01 #41 integrada. BOT-01 e BOT-02 estão fechadas no GitHub. A continuação da retomada já foi mergeada; não está mais em desenvolvimento nesta revisão.

A ativação e a jornada online precisam de evidência própria. A API CART-01 está no PR #46; esta branch acrescenta o [canal humano](cart-01-telegram.md) ainda desligado. Outputs, revisão final completa e ensaio real continuam pendentes. Nenhuma evidência antiga foi regravada.

## Evidência online histórica — 17/10/2026

O restante desta seção preserva o retrato daquele ensaio. Frases sobre pendências, volume, comandos ou número de testes descrevem aquela versão, não as mains atuais. Para planejamento vigente, usar os links acima.

Conferência em **17/10/2026, horário de São Paulo**. Este documento registra uma observação, não monitoramento contínuo. O [snapshot sanitizado](evidencias/login-ifood-2026-10-17.json) contém somente estados, operações permitidas e referências de versão.


## Capacidades observadas naquele ensaio

| Capacidade | Implementação e evidência |
| --- | --- |
| Canal Telegram privado | Long polling, organizador numérico autorizado, `/start`, `/status`, `/ajuda`; usuário confirmou respostas online |
| Estado do adaptador | SQLite com cursor e ações iniciadas; testes simulados de replay, reinício e concorrência |
| Hospedagem do bot | Worker Railway com uma instância, imagem Docker construída e volume próprio `/data` |
| Migração inicial | Banco local fechado, checksum e integridade conferidos no destino; cópia local preservada |
| Autenticação bot→API | Segredo de serviço e organizador conferidos em memória, sem valores registrados |
| Callback HTTPS | Aprovação do cadastro informada pelo usuário; retorno `/callback` observado com HTTP 200 |
| Login e confirmação | Usuário concluiu navegador e confirmação no Telegram; consulta posterior do backend confirmou vínculo |
| Sessão iFood | `CONNECTED`, `operational: true`, `verification.status: OK`, `scopeEvidence: TOKEN_SCOPES` |
| Operações liberadas pelo backend | `ADDRESSES_READ` e `OFFERS_EVALUATE`; não significa que ambas foram executadas nesta conferência |

A verificação operacional do backend usa leitura autenticada `listAddresses`. Não foram coletados endereços ou respostas privadas para a documentação. Nesta manutenção, o agente consultou somente estado autenticado da API e metadados dos deploys.

## Versões de referência da observação

| Componente | Referência | Observação |
| --- | --- | --- |
| `Modo-Escuro/telegram-bot` | `51b4a9e` | Deploy `SUCCESS`, uma instância `RUNNING`, `/data` montado |
| `Modo-Escuro/api-backend` | `686300d` | Deploy `SUCCESS`, uma instância `RUNNING`, sem volume montado |
| Protótipo original | `ebfd6e0` | Preservado; demonstração simulada e baseline, sem migração destrutiva |

Essas referências identificam a evidência anterior à reorganização documental e às melhorias de orientação deste incremento. Commits posteriores não atualizam retroativamente o snapshot.

## Pendências anotadas naquele ensaio

- Participantes, limites individuais/coletivo e restrições por pessoa na conversa do bot.
- Agente de compra integrado ao canal e contrato HTTP de conversa/sacola/aprovação.
- Ensaio de `searchOffers` e `getItem` apresentado pelo bot; liberação de `OFFERS_EVALUATE` não comprova essa jornada.
- Sacola, entrega, pagamento, cupom, revisão, aprovação de pedido, envio e reconciliação remota.
- Cancelamento e desconexão pelo bot; o backend possui rotas, mas o adaptador não as oferece.
- Mensagem automática após retorno do navegador; hoje o usuário envia `/confirmar` ou `/ifood` para consultar o estado.
- Ensaio online específico de expiração, refresh, indisponibilidade, reconexão e reinício com vínculo preservado.

O backend respondeu `purchaseAuthorized: false`. O login concluído não representa compra aprovada nem fechamento no iFood. O provedor do protótipo Python original permanece simulado.

## Risco de persistência anotado naquele ensaio

O bot já preserva o SQLite em `/data`. A API ainda usa `.ifood-links` sem volume: os vínculos confirmados podem se perder em um redeploy. Antes de mudar o caminho ou montar um volume, preservar os arquivos existentes por canal privado e validar a migração. Tentativas OAuth pendentes ficam em memória mesmo com volume.

Não reiniciar ou redeployar a API durante uma autorização. Atualizar somente o bot não deve ser confundido com redeploy da API.

## Histórico preservado

1. `33fd951`: cliente de login e confirmação por botão implementados contra o contrato `20e46fd`.
2. `19d10ef`: arquivos de deploy e guias Railway publicados; revisão de compatibilidade com `686300d`.
3. `51b4a9e`: aprovação do callback informada pelo usuário registrada; bot online e respostas `/start` e `/ifood` confirmadas.
4. A consulta inicial retornava `DISCONNECTED`. Após login no navegador, `/callback` retornou 200 e o estado mudou para `AWAITING_CONFIRMATION`.
5. O usuário enviou `/confirmar`, concluiu o botão humano e informou sucesso. A consulta autenticada posterior confirmou `CONNECTED`, sessão operacional e verificação `OK`.

## Validação automatizada e seu alcance

A suíte do bot tem 39 testes simulados: autorização privada, identificação, transporte, deduplicação, cursor, lock, replay de ações e confirmação humana. Lint e formatação também foram executados no incremento. A CI roda testes em Windows e Linux; execução local em Windows não substitui o resultado de cada job da CI.

Teste automatizado não comprova resposta do provedor, segurança alimentar, preço final ou compra. O ensaio real de login descrito acima é uma evidência separada. Próximas mudanças devem registrar o que foi realmente executado.
