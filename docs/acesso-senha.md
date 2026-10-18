# Acesso compartilhado à demo por senha

Mudança solicitada pelo usuário em 18/10/2026: qualquer conta Telegram pode entrar na conversa privada com a
senha da equipe, conectar a própria conta iFood e usar a conversa quando a API estiver habilitada. Isso amplia
o recorte anterior de um organizador único; cada usuário é organizador somente da própria conversa. A sacola
continua simulada e o MCP somente leitura (DEC-01). Entrada na demo e login iFood não aprovam compras.

## Configuração

- Bot: definir `TELEGRAM_ACCESS_PASSWORD` no ambiente secreto (6–80 caracteres ASCII sem espaço). Nunca colocar
  senha real em docs, Git, logs, `.env.example` ou evidências. Ausente/vazia mantém o modo anterior de um ID.
- Bot: manter `TELEGRAM_ALLOWED_USER_ID` com o ID anterior para localizar seu SQLite legado. Em modo senha,
  esse ID também precisa entrar; não tem bypass. Não retirar/trocar essa referência durante a migração.
- API: a mudança correspondente adiciona `BOT_PASSWORD_ACCESS_ENABLED=true`. O token bot→API continua
  obrigatório. O bot só envia `X-Telegram-Access: PASSWORD` após admitir uma sessão local. O marcador sozinho,
  sem o token de serviço, não dá acesso. O modelo não recebe marcador, senha ou credenciais.
- Para conversa: `TELEGRAM_CONVERSATION_ENABLED=true` no bot e RUN-01/processador na API, com banco em volume,
  `BOT_TELEGRAM_ID` correto e provedor configurado. A senha não instala um modelo nem contorna cotas.
- Projeto Railway informado pelo usuário: `d2af9e6b-0bda-4725-bcc8-9092dc2b5a2e`, ambiente `production`.
  Conferir os seletores explicitamente, sem reutilizar vínculo antigo da pasta local. Cada serviço tem `/data`.

## Uso

1. Abrir a conversa privada com o bot e enviar `/start`.
2. Enviar `/entrar` seguido da senha fornecida privadamente pela equipe.
3. Acesso dura 24 horas. Usar `/conectar`, entrar com a conta de teste iFood autorizada do evento e conferir
   a identidade no botão humano. A senha da demo não substitui as credenciais nem o OAuth da conta de teste.
4. Texto livre usa a conversa e os limites vigentes da API. `/ajuda`, `/ifood`, `/verificar`, `/andamento` e demais
   comandos preservam os comportamentos anteriores. Recursos pendentes do backend continuam indisponíveis.
5. `/sair` revoga o acesso à demo, sem desconectar a conta iFood nem apagar a intenção aceita. Para remover o
   vínculo iFood, usar `/desconectar` antes de sair ou entrar novamente. Trocar a senha invalida as sessões antigas.

O bot tenta apagar a mensagem `/entrar ...` no Telegram; falha nessa remoção não altera a autorização nem
revela a senha na resposta. Não há garantia de exclusão de notificações, histórico ou cópias do Telegram.

## Isolamento, persistência e limites

Há apenas um polling e o lock original por bot. O cursor global continua no SQLite existente. O evento de
conversa é persistido no banco do usuário antes do avanço do cursor global; se cair entre esses commits, replay
recupera o mesmo evento. O banco legado do organizador anterior permanece no mesmo caminho e não é copiado.
Novos usuários têm diretórios separados por hash, com seus próprios SQLite, fila, acompanhamento e clientes.

O banco `bot-<botId>-access.sqlite3` guarda somente ID Telegram, HMAC de versão da senha (chaveado pelo token do
bot), expiração e contadores de tentativa. Não guarda a senha nem a mensagem. Metadados vencidos são limpos no
polling. Credenciais e detalhes iFood continuam exclusivamente na API. Sessões atuais são reconstruídas no
reinício sem iniciar outro polling. Os workers verificam a sessão antes de enviar texto à API e antes de
entregar respostas; saída/expiração pausa a fila. Uma chamada já aceita pela API pode concluir mesmo após sair.

Até cinco tentativas por conta e 100 no total por janela de 15 minutos. Orientação para usuário sem acesso
limitada a uma por minuto. Até 100 sessões ativas por padrão (`TELEGRAM_ACCESS_MAX_USERS`, 1–200). Há um worker
de conversa por sessão, com fila local limitada; é um recorte de demo, não escalabilidade irrestrita. O
acompanhamento de login alterna usuários no polling; muitos logins podem aumentar a demora para mostrar o botão.

Não são limites financeiros. Modelo, cotas e orçamento continuam sendo responsabilidade da API/provedor.
Desligar a flag, expirar ou sair pausa workers/limpeza das filas daquele usuário, como no modo anterior; arquivos
e WAL/backups devem seguir a política operacional D7. Nenhum banco/volume deve ser apagado para liberar acesso.

## Validação

Testes novos: senha errada e limite persistente, expiração, troca de senha, restart, logout, callback cruzado,
grupo/mensagem editada, senha fora da outbox, fila/cliente/acompanhamento por usuário, herança do SQLite original,
cabeçalhos de identidade e bloqueio de envio/entrega após revogação. Usam somente dados e serviços falsos.
CI deve validar unitários, integração HTTP fixada e imagem Docker. Testes não comprovam deploy ou uso do modelo real.
