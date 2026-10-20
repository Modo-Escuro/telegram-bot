**Registro histórico do ensaio de 18/10/2026.** Valores, schema 2, instruções de clique e flags abaixo pertencem àquele ambiente. Não aplicar a tabela antiga como configuração do assistente atual. Código local corrente usa API v5, login sem segundo clique e menu de memória; guias em [assistente](assistente-conversacional.md), [login](login-ifood.md) e [execução](executar-bot.md). Nenhuma nova inspeção de produção foi feita nesta atualização.

# BOT-02 — habilitação e ensaio operacional

Plano de 18/10/2026. Base: bot `9314c72`, API `dc448f9` (Gemini e propostas já montados).
Escopo autorizado: preparar a conversa, conservar o grupo após login e verificar a retomada.
DEC-01: carrinho simulado, MCP somente leitura, nenhum envio de pedido.

## Sequência e limites

1. Conferir versões, volume `/data`, credenciais correspondentes e ausência de webhook, usando apenas
   `getMe`/`getWebhookInfo`; nunca iniciar outro `getUpdates` ou polling local.
2. Fazer backup privado consistente dos SQLite do bot e dos vínculos iFood antes do redeploy.
   Usar a API de backup SQLite (inclui o WAL), nunca copiar só o arquivo aberto. Cada SQLite é um
   snapshot independente. Não restaurar sobre dados em uso nem publicar backups.
3. Validar offline a montagem atual e a recuperação após reinício. Ativar primeiro a API e conferir
   armazenamento/modelo; só depois ativar a conversa no único polling do bot.
4. Executar o roteiro humano abaixo. Configuração válida e processo ativo não comprovam inferência,
   autorização OAuth nem entrega no Telegram.

Configuração da API para este ensaio:

| Variável | Valor |
| --- | --- |
| `CONVERSATION_RUNTIME_ENABLED` | `true` |
| `CONVERSATION_DB_FILE` | `/data/conversations/runtime.sqlite` |
| `BOT_TELEGRAM_ID` | ID real retornado por `getMe`, sem publicar identidade |
| `CONVERSATION_MODEL_ENABLED` | `true` |
| `CONVERSATION_MODEL_PROVIDER` | `google` |
| `CONVERSATION_MODEL` | `gemini-3.8-flash` |
| `CONVERSATION_MODEL_MAX_REQUESTS` | `100` |
| `CONVERSATION_MODEL_MAX_REQUESTS_PER_CONVERSATION` | `40` |
| `CONVERSATION_MODEL_BUDGET_MICRO_USD` | `500000` (US$ 0,50) |
| `CONVERSATION_MODEL_TIMEOUT_MS` | `15000` |
| `CONVERSATION_MODEL_MAX_OUTPUT_TOKENS` | `2048` |
| `IFOOD_CART_ENABLED`, `DEV_GLOBAL_SESSION` | `false` |

No bot: `TELEGRAM_CONVERSATION_ENABLED=true`, mantendo o diretório `/data`, a senha, o token e o
acesso já configurados. Não trocar chaves nem diminuir a capacidade pública nesta habilitação.

Os três limites do modelo são por processo e contam também falhas; reiniciar a API zera os contadores.
A reserva local não é fatura nem limite mensal. Ao esgotar, o turno falha sem alterar o grupo.
Não reiniciar nem usar `/retomar` repetidamente para contornar o limite. Limite de cobrança no console
Google, quotas persistentes e alertas continuam em OPS-02. Não há fallback de modelo.

## Roteiro humano (somente dados fictícios)

Na conversa privada do bot online, sem abrir outro processo:

1. Entrar com `/entrar` e a senha já compartilhada pela equipe, se a sessão não estiver liberada.
2. Se houver um grupo que deve ser preservado, usar outra conta Telegram admitida para o ensaio.
   Não substituir dados existentes só para executar o teste.
3. Enviar: **Somos Ana e Bia. Ana é alérgica a amendoim. Bia não tem restrições. Teto do grupo de
   R$ 180. Preferimos o mais barato.** Aguardar a resposta antes da próxima mensagem.
4. Enviar: **Na verdade, o teto do grupo é no máximo R$ 150.** Conferir duas pessoas, alergia de Ana
   obrigatória e orçamento de R$ 150. Bia sem restrições não libera itens para Ana.
5. `/conectar` → autorizar a conta **de teste iFood** no navegador → conferir identidade mascarada →
   clicar humanamente no botão → `/verificar` quando necessário. A senha da demo não substitui
   credenciais/autorização da conta iFood. Se a conta já estiver conectada, `/verificar` testa a retomada
   dessa conexão; não comprova um novo OAuth. Não desconectar uma conta só para forçar o ensaio.
6. Na **Retomada informativa**, conferir Ana e Bia, amendoim obrigatório e **R$ 150,00**, sem reaplicar
   a mensagem original, voltar a R$ 180, apresentar proposta antiga ou mostrar aprovação de compra.
   Verificações distintas podem gerar novas consultas informativas; replay do mesmo update não duplica.
7. Uma segunda conta Telegram admitida deve receber seu próprio contexto (ou a orientação de ausência
   de grupo), nunca o grupo da primeira. Não compartilhar capturas de dados privados.

O bot deve mostrar o grupo mesmo que não haja proposta elegível. Informação alimentar ausente mantém
o item bloqueado para a pessoa afetada. Não pedir compra real para testar a retomada.

## Evidência e critérios

[Registro sanitizado](evidencias/bot02-activation-2026-10-18.json): 177 testes do bot (sete HTTP) e
32 testes relevantes da API passaram; Ruff/formatação passaram. Backups conferidos: três SQLite
do bot e dois arquivos de vínculo da API. Após ativação da API, banco íntegro (schema 2), zero
conversas, rota autenticada retornando `NOT_FOUND` esperado; agente Gemini ativo no log.
Nenhuma inferência paga foi provocada pelos testes automatizados desta habilitação.

**Ativação conferida às 09:49 UTC (06:49 BRT), 18/10/2026:** bot com conversa habilitada, uma
instância de polling verificada no container e sem traceback/conflito no log observado. API com
runtime/modelo ativos, SQLite íntegro e F7/sessão global desligadas. Ambos os deploys `SUCCESS`.
Durante o trabalho, a equipe integrou API #41: produção passou a `28edd06`, com alterações somente
em testes/documentação e `src` idêntico ao `dc448f9` validado. O probe da configuração/banco/HTTP
foi repetido após esse deploy e passou. Banco ainda sem grupo; a coleta humana abaixo é necessária.

- [ ] Humano confirmou coleta e correção com Gemini pelo bot online.
- [ ] Autorização e clique humanos concluídos com a conta teste correta (ou registrar só verify existente).
- [ ] Grupo recuperado com duas pessoas, alergia preservada e teto corrigido.
- [ ] Nenhuma ação repetida, proposta antiga ou aprovação apresentada na retomada.
- [ ] Isolamento confirmado com uma segunda conta Telegram.

Registrar somente versões, horário, aprovado/reprovado e motivo sanitizado; nunca tokens, nomes de
conta, IDs Telegram, URLs OAuth, conteúdo de banco ou respostas integrais do modelo. O resultado humano
continua pendente até relato/observação explícita. Não preencher esses itens por inferência da CI.

### Ensaio automatizado

A CI fixa a API em `dc448f9e117e05192004514a639c3ed5acd1098a`. O novo caso HTTP usa
`createConversationRuntime`/Gemini/AI-02/DATA-01 reais com transporte Gemini **falso**, somente loopback.
Cria duas pessoas, corrige o orçamento, conserva a alergia, verifica isolamento e reinicia o processo
Node sobre o mesmo SQLite. GET/retomada não mudam o snapshot nem chamam o transporte do modelo;
replay da confirmação não duplica a entrega. OAuth, vínculo operacional e Telegram são sintéticos.

Esse transporte não é modelo de produção e nunca é instalado como fallback.

## Reversão

Desabilitar primeiro `TELEGRAM_CONVERSATION_ENABLED=false` no bot e redeployar seu único worker;
depois `CONVERSATION_MODEL_ENABLED=false` na API, se necessário. Manter banco, volume, tokens,
vínculos e demais configurações. A fila local fica pausada; não apagar SQLite nem recriar identidades
de eventos. Flags desligadas não desfazem mensagens já entregues ou chamadas já aceitas.

Backups privados desta habilitação: `/data/ops-backups/bot02-20261018-activation` em **cada serviço**.
Não são cópias fora do volume e não protegem contra perda do próprio volume. Contêm dados sensíveis;
respeitar a retenção/exclusão D7. A restauração é manual, com serviço parado e destino vazio.
