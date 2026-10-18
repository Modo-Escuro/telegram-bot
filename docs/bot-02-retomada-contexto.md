# BOT-02 — Retomar a organização após o login

**Atualização 18/10/2026:** a retomada está integrada pela PR #11 e a issue está fechada. A API
`dc448f9` já monta Gemini e propostas; a CI deste incremento usa essa versão. Abaixo permanece o
histórico da implementação anterior. Configuração efetiva, validação atual e pendências humanas estão
no [ensaio operacional](ensaio-bot02-operacional.md); issue fechada não comprova a recuperação online.

[Issue #2](https://github.com/Modo-Escuro/telegram-bot/issues/2) · [Login](login-ifood.md) · [Fila BOT-01](bot-01-fila-duravel.md)

## Base e alcance

A primeira etapa da BOT-02, na PR #8, já está na `main` do bot pelo merge da PR #10 (`c29cc04`). Inclui
acompanhamento da mensagem de login, confirmação humana, cancelamento da tentativa e desconexão do vínculo.
O relatório de 69 testes daquela etapa permanece em [validação BOT-02](validacao-bot02.md); não confundir esses
resultados históricos com a validação deste incremento.

Este incremento integra conexão e fila para **retomar a organização do grupo por consulta**, sem gerar evento
de conversa, chamar modelo, alterar o domínio ou repetir a mensagem anterior. Tem efeito apenas com
`TELEGRAM_CONVERSATION_ENABLED=true`, backend configurado e worker de conversa ativo. A flag continua desabilitada
por padrão; nenhuma variável Railway foi alterada.

A API usada no ensaio/CI é `2b77c958f358130c91a72e310d5c31f6c39c2d00`, que incorpora AI-02. O módulo do agente
mergeado não comprova sua instalação no processo: `src/server/index.ts` ainda cria a RUN-01 sem processador. A
configuração de provedor real/montagem e o ensaio online continuam separados. A retomada usa os GET já existentes
de status iFood e snapshot de conversa; não depende de inventar endpoint ou evento de restauração.

## Comportamento

1. O clique humano confirma a conta pelas proteções já existentes. Callback OAuth sozinho não confirma.
2. Se a resposta validada indica `CONNECTED`, sessão operacional, permissões e `linkId`, o bot persiste uma
   solicitação local de consulta antes de enviar a resposta ao clique. Sem esses requisitos, orienta `/verificar`.
3. `/verificar` também agenda a consulta quando o resultado é operacional. Se esse comando for recebido novamente
   após falha de entrega, apenas consulta status e recupera a mesma solicitação, sem repetir a verificação remota.
4. O acompanhamento de login pode recuperar uma confirmação já concluída no servidor após falha/reinício. Faz
   somente GET; estado `AWAITING_CONFIRMATION` nunca agenda a retomada nem autoriza confirmação automática.
5. O worker confere o vínculo operacional, consulta o snapshot atual e confere novamente o vínculo. Troca de
   `linkId`, desconexão ou sessão sem acesso impedem a apresentação. Indisponibilidade temporária não é logout.
6. O texto apresenta somente participantes, condições e orçamento coletivo do bloco GROUP. Não apresenta textos
   antigos do modelo, propostas, itens, preços cotados, endereços, resultado de compra ou referências/botões de
   aprovação. O orçamento é uma informação do grupo, não uma cotação. Perguntas antigas não são recuperadas.
7. Cada parte de mensagem exige nova consulta do snapshot e do vínculo. Sem grupo salvo, o bot orienta começar
   por texto livre. Para mensagens anteriores, `/andamento` e `/retomar` continuam disponíveis; a retomada
   informativa não reinicia automaticamente um evento pausado ou de resultado desconhecido.

`/ifood` e `/confirmar` continuam como fallback de conexão. `/cancelar` e `/desconectar` mantêm seus efeitos
distintos e não agendam retomada. Fila cheia recusa a consulta com orientação, preservando os textos aceitos.

## Persistência, falhas e privacidade

Uma migração aditiva acrescenta `link_hash` à outbox. A solicitação `CONTEXT` guarda chave técnica de origem,
hash do vínculo, fase, prazos e metadados de entrega. Não guarda `linkId` em texto, identidade, confirmationId,
URL, código OAuth, snapshot, mensagem ou resultado. A origem fica no escopo autenticado de API/bot/organizador.
Mesmo identificador de origem não troca de vínculo no replay. Migração preserva cursor e eventos pendentes.

O worker usa seus próprios clientes. Cada GET tem timeout de 5 s; cancelamento do processo interrompe a sequência
antes de iniciar outra requisição. Falhas respeitam os três ciclos/tentativas e comandos de recuperação da BOT-01.
Solicitações de consulta expiram em 24 h e os metadados terminais são limpos após sete dias. Flag desligada pausa
worker e limpeza, conforme a política operacional de retenção já documentada.

O bot persiste o agendamento antes de confirmar o processamento do update e deduplica sua chave em replay.
Falha entre confirmação remota e agendamento não repete a confirmação: replay consulta status; o acompanhamento
ou `/verificar` recupera a retomada. Falha ao enviar uma mensagem Telegram pode ter ocorrido depois do efeito:
pausa como `DELIVERY_UNKNOWN`; `/retomar` pode duplicar uma mensagem, sem criar turno ou repetir mutação.

O snapshot é sempre relido; expurgo/encerramento na DATA-01 não é desfeito pela retomada. Não há cópia local do
grupo. Isso não exclui mensagens já entregues nem sanitiza WAL/backups; preservar o volume e sua política D7.

## Limite da revalidação e dependências

As duas consultas de status **não são uma transação com a API ou com o Telegram**. Outra sessão pode trocar a
conta depois da última consulta. A saída é informativa e não contém ações de compra; não se promete invalidar
mensagens já exibidas ou validar itens/preços/endereços por esse mecanismo.

O critério da issue “troca de linkId invalida ações antigas de compra” permanece dependente de BOT-03 e da
validação de versão/vínculo no backend, com BUY-01 para aprovação. Ausência de botão de compra neste bot não
comprova esse critério. Login e retomada nunca aprovam uma compra. DEC-01 mantém demo simulada e MCP só leitura.

## Validação e ensaio humano

Testes novos cobrem clique/replay, confirmação de resultado incerto, retomada do acompanhamento, vínculo trocado
antes/durante consultas e entre partes, sessão indisponível, fila cheia, reinício, migração, expiração, privacidade,
Telegram 429/403 e entrega incerta. Os testes HTTP usam as rotas reais de conversa/SQLite da API fixada e
processador/vínculo sintéticos; comprovam consulta sem novo turno e retomada depois de expurgo sem reintroduzir
o grupo. Não validam OAuth/provedor reais ou o módulo de IA. Resultados e commits ficam no PR e na issue.

Para reproduzir, instalar o lockfile/pacote do bot, preparar o checkout exclusivo da API fixada e executar a suíte
conforme [BOT-01](bot-01-fila-duravel.md#reprodução-e-evidência). O job separado da CI executa obrigatoriamente os
seis ensaios HTTP; sem `BOT01_API_ROOT`, a suíte unitária registra esses skips explicitamente.

Ensaio após revisão/merge e deploy, operado pelo organizador sem iniciar um segundo polling:

1. Preservar SQLite/volume e conferir a versão implantada. Verificar flags, backend e processador/provedor.
2. `/conectar`, autorizar no navegador e voltar à mensagem; conferir a identidade e clicar humanamente.
3. Com sessão operacional e conversa habilitada, conferir a orientação de consulta e o grupo recuperado.
   Se a sessão ainda não está operacional, usar `/verificar`; se não houver grupo, conferir a orientação inicial.
4. Confirmar que participantes, restrições e orçamento permanecem, sem proposta/aprovação ou repetição do texto.
5. Em ambiente de teste, repetir com conta substituída, indisponibilidade e reinício; usar `/retomar` apenas
   conscientemente quando houver entrega incerta. Não provocar falhas destrutivas no serviço real.
6. Conservar o roteiro original de cancelar reconexão e desconectar com tentativa pendente. Registrar só estados
   sanitizados, commit e resultado. Não enviar códigos, URLs privadas ou dados da conta ao chat.

Código/CI não comprovam esse ensaio. A BOT-02 permanece aberta até revisão e validação operacional, com a
invalidação das futuras ações de compra acompanhada nas dependências citadas.
