# Executar o bot Telegram

Implementado: long polling, /start, /status, /ajuda, acesso privado por ID numérico, cursor persistente e bloqueio de instância concorrente no mesmo diretório de estado. Há cliente HTTP para login iFood via backend, com confirmação por botão. Coleta de participantes e compra continuam pendentes.

## 1. Criar o bot

No Telegram, abra [@BotFather](https://t.me/BotFather), execute /newbot e siga as instruções. Guarde o token apenas localmente. Configure /setjoingroups como Disable para reduzir convites a grupos; o programa rejeita grupos independentemente dessa configuração.

## 2. Preparar Python

No Git Bash, na pasta do projeto, use Python 3.12:

```bash
cd ~/OneDrive/Desktop/telegram-bot
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e .
```

Se seu comando python não for 3.12, use o caminho completo do executável 3.12. No Linux/macOS, substitua .venv/Scripts/python.exe por .venv/bin/python. O programa usa apenas a biblioteca padrão em execução.

## 3. Inserir o token sem exibi-lo

```bash
read -r -s -p "Token do BotFather: " TELEGRAM_BOT_TOKEN
echo
export TELEGRAM_BOT_TOKEN
```

O token não aparece no comando nem no histórico. Não cole o token no chat. O programa lê variáveis do processo; não carrega .env automaticamente. Variáveis exportadas valem apenas nesse terminal.

## 4. Descobrir o ID do organizador

Se já conhece seu ID numérico pessoal, pule para o passo 5. Não use o ID do bot que aparece no início do token.

```bash
./.venv/Scripts/python.exe -m telegram_bot --identify
```

O terminal mostra um comando temporário /identificar seguido de um código aleatório. Envie exatamente esse comando na conversa privada com seu bot em até três minutos. O terminal exibirá apenas o seu ID numérico; não grava essa identidade e não libera o bot automaticamente. Não compartilhe o código de pareamento.

Esse modo consome updates de preparação e não deve rodar junto com o bot. Ele não responde no Telegram. É a única saída local deliberada de ID pessoal, para configurar o acesso; não redirecione essa saída para logs públicos.

## 5. Configurar e iniciar

```bash
read -r -p "Seu ID numérico do Telegram: " TELEGRAM_ALLOWED_USER_ID
export TELEGRAM_ALLOWED_USER_ID
./.venv/Scripts/python.exe -m telegram_bot --check
./.venv/Scripts/python.exe -m telegram_bot
```

Abra a conversa privada com o bot e envie /start. Teste /status e /ajuda. Ctrl+C encerra. Outro usuário ou grupo não recebe resposta.

--check verifica o token e a ausência de webhook, sem consumir mensagens. Não verifica login iFood.

## Erros e limites

- Token recusado: confira o token local do BotFather.
- Webhook ativo: o programa para sem alterar a configuração. Desative o webhook no sistema que o configurou antes de usar polling; não descarte updates pendentes.
- Conflito 409: encerre outra instância do bot/OpenCode que esteja consumindo getUpdates. Use um único processo por token, inclusive entre computadores.
- Falha temporária: novas tentativas têm espera progressiva; limites do Telegram respeitam retry_after.
- O diretório data guarda cursor, IDs dos updates com ações iniciadas e arquivos de lock, sem conteúdo de conversa, link de login, identidade de conta ou token. Não apague o estado durante a operação.
- Uma interrupção após Telegram aceitar sendMessage e antes da gravação do cursor pode repetir uma resposta textual. Não se promete entrega única de mensagens; não há operação de compra. A futura integração precisa de idempotência própria no backend.
- Updates ignorados por autorização ou tipo também avançam o cursor. Mensagens editadas não são processadas; callbacks de confirmação validam remetente e conversa privada.
- Depois de uma semana sem eventos processados, o cursor é reiniciado para aceitar IDs aleatórios do Telegram.
- Integração de login implementada conforme [guia de conexão](login-ifood.md); falta ensaio real com credenciais locais.

## Verificação

```bash
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

Os testes usam respostas simuladas, sem rede e sem credenciais. A CI executa em Windows e Linux. Teste manual esperado: organizador recebe /start; outra conta e grupo são ignorados; reiniciar não responde novamente aos updates já processados.

Referência: [Telegram Bot API — getUpdates](https://core.telegram.org/bots/api#getupdates).

## 6. Habilitar login iFood

Consulte [login-ifood.md](login-ifood.md) para configurar os dois processos. No Telegram, envie /conectar, abra o botão no navegador do computador do backend e conclua a autorização. Envie /confirmar, confira a conta e toque em Confirmar conexão. /ifood consulta o estado; /verificar valida a sessão via backend. Não envie código no chat.
