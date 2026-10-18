# Executar e diagnosticar o bot localmente

[Índice](README.md) · [Railway](deploy-railway.md) · [Login](login-ifood.md)

## Antes de iniciar

A conversa de texto livre é opt-in com `TELEGRAM_CONVERSATION_ENABLED=false` por padrão.
Condições de ativação, retenção da fila e ensaio isolado estão no [guia BOT-01](bot-01-fila-duravel.md).
Não habilitar apenas porque o bot iniciou: a API precisa ter o processador AI-02 instalado.

O bot já está online na Railway. Não iniciar polling local com o mesmo token enquanto o serviço estiver ativo. Para transferir a execução, seguir a migração do [estado atualizado](deploy-railway.md#transferir-execução-entre-computador-e-nuvem); preservar `data/` e não voltar a usar uma cópia antiga do SQLite.

`--check` consulta apenas token e webhook, sem consumir updates. `--identify` consome updates de preparação e não deve rodar junto com o serviço online.

## Preparar Python

Python 3.12 no Git Bash do Windows:

```bash
cd ~/OneDrive/Desktop/telegram-bot
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r requirements.lock
./.venv/Scripts/python.exe -m pip install --no-deps -e .
```

Não recriar uma venv que já funciona. Se `python` não for 3.12, usar o executável correspondente. Linux/macOS: `.venv/bin/python`. O transporte usa a biblioteca padrão; o cliente de conversa usa `jsonschema`, com dependências fixadas em `requirements.lock`.

## Configurar o ambiente sem registrar segredos

As variáveis valem para o terminal atual. O bot não carrega `.env` automaticamente. Token do BotFather, segredo bot→API e Client Secret iFood são credenciais diferentes; a última fica exclusivamente no backend.

```bash
read -r -s -p "Token do BotFather: " TELEGRAM_BOT_TOKEN
echo
export TELEGRAM_BOT_TOKEN
read -r -p "Seu ID numérico do Telegram: " TELEGRAM_ALLOWED_USER_ID
export TELEGRAM_ALLOWED_USER_ID
export BACKEND_BASE_URL="https://api-backend-production-9c4c.up.railway.app"
read -r -s -p "Segredo de serviço da API (BOT_API_TOKEN): " BACKEND_API_TOKEN
echo
export BACKEND_API_TOKEN
```

O organizador precisa ser o mesmo permitido em `ALLOWED_ORGANIZER_IDS` na API. O valor de `BACKEND_API_TOKEN` é o `BOT_API_TOKEN` da API. Credenciais não devem ser coladas em comandos literais, histórico ou chat.

`TELEGRAM_STATE_DIR` usa `data` por padrão. Para executar uma migração reversa, aponte para o diretório com o SQLite atualizado e já conferido. O exemplo não importa o estado da nuvem automaticamente.

Sem ambas as variáveis `BACKEND_*`, os comandos de login informam integração desabilitada; configuração parcial impede iniciar polling. Para backend local, a origem pode ser `http://localhost:8000`, desde que `PUBLIC_BASE_URL` e callback estejam coerentes com esse ambiente.

## Diagnóstico e execução

```bash
./.venv/Scripts/python.exe -m telegram_bot --check
```

Esse comando verifica o token Telegram e a ausência de webhook. Não verifica o login iFood nem o contrato/configuração completa do backend.

Depois de encerrar a instância online e concluir a transferência de estado, iniciar:

```bash
./.venv/Scripts/python.exe -m telegram_bot
```

`/start`, `/status` e `/ajuda` respondem ao organizador em conversa privada. Outro usuário ou grupo é ignorado. Ctrl+C encerra. `/status` mostra o estágio da demo; `/ifood` consulta o vínculo e `/verificar` pede verificação da sessão ao backend.

No [fluxo de login](login-ifood.md), volte à mensagem após autorizar no navegador: ela é atualizada com o botão humano. `/confirmar` é a alternativa se o acompanhamento terminar. `/cancelar` encerra só a tentativa; `/desconectar` remove só o vínculo local. Nenhum código deve ser digitado no Telegram.

## Criar um bot ou identificar um novo organizador

Se for necessário outro bot, usar [@BotFather](https://t.me/BotFather), `/newbot`, e guardar o token somente no ambiente/painel. `/setjoingroups` como Disable reduz convites, mas o programa rejeita grupos independentemente dessa configuração.

Se o ID pessoal do organizador for desconhecido, com o polling parado:

```bash
./.venv/Scripts/python.exe -m telegram_bot --identify
```

Enviar na conversa privada exatamente o desafio temporário `/identificar ...` exibido no terminal, em até três minutos. O terminal mostra apenas o ID pessoal para configuração; não gravar essa saída em logs públicos. Não usar o ID do bot presente no token. O pareamento não libera acesso automaticamente.

## Falhas e limites

- Token recusado: conferir o token local do BotFather.
- Webhook ativo: o programa para sem alterar a configuração. Desativar no sistema responsável sem descartar updates pendentes antes de migrar para polling.
- Conflito 409: encerrar a outra instância, inclusive em outra máquina. Não apagar estado para contornar.
- Falha temporária: espera progressiva e `retry_after` do Telegram são respeitados.
- Falha de backend: mensagens saneadas; consultar `/ifood` antes de repetir uma ação cujo resultado seja desconhecido.
- Falha entre `sendMessage` e gravação do cursor pode repetir texto; não há promessa de entrega única de mensagens.
- Eventos ignorados também avançam cursor; mensagens editadas não são processadas. Callbacks validam remetente e conversa privada.
- Após uma semana sem eventos processados, o cursor aceita IDs aleatórios do Telegram.

## Testes

```bash
./.venv/Scripts/python.exe -m unittest discover -s tests -v
```

A suíte usa respostas simuladas, sem rede e sem credenciais. A CI executa em Windows e Linux. O ensaio real concluído está em [estado atual](estado-atual.md); não apresentar testes simulados como evidência de compra no iFood.

Referência do transporte: [Telegram Bot API — getUpdates](https://core.telegram.org/bots/api#getupdates).
