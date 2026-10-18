# Login iFood pelo Telegram

Implementado no bot: cliente HTTP autenticado, /conectar, /confirmar, /ifood e /verificar, com confirmação humana por botão. Contrato inicialmente conferido contra api-backend commit 20e46fdad96b96534fb8730e66d94460f98a6939. Compatibilidade de login revisada contra 686300d1a10c12bb6c3bd899e40fbd3a68c648f5 em 17/10/2026; a revisão não comprova login real nem operações de compra. Testes usam respostas simuladas; login real ainda depende das configurações e do ensaio local.

## Configurar os dois processos

No api-backend, configurar conforme sua documentação:

- BOT_API_TOKEN: segredo de serviço com pelo menos 32 caracteres.
- ALLOWED_ORGANIZER_IDS: o mesmo ID numérico permitido no bot.
- PUBLIC_BASE_URL: origem alcançável pelo navegador; deve coincidir com BACKEND_BASE_URL. Para API local, http://localhost:8000; para Railway, a origem HTTPS pública.
- Credenciais e callback iFood: somente no backend; seguir seu cadastro OAuth.

No Git Bash do bot, após configurar TELEGRAM_BOT_TOKEN e TELEGRAM_ALLOWED_USER_ID:

```bash
export BACKEND_BASE_URL="http://localhost:8000"
read -r -s -p "Segredo de serviço da API (BOT_API_TOKEN): " BACKEND_API_TOKEN
echo
export BACKEND_API_TOKEN
./.venv/Scripts/python.exe -m telegram_bot
```

Insira o mesmo segredo configurado como BOT_API_TOKEN na API. Ele é diferente do token do BotFather e do Client Secret iFood. Nenhum segredo deve ser enviado no Telegram. O programa não carrega .env automaticamente. Sem as duas variáveis BACKEND_*, os comandos informam que a integração está desabilitada; configuração parcial impede iniciar o polling.

## API publicada na Railway

O serviço conferido em 17/10/2026 executava o commit `686300d`, com uma instância e sem volume. `/api/health` comprova apenas disponibilidade; uma consulta autenticada de `/api/bot/ifood/status` retornou `DISCONNECTED`, `operational: false` e nenhuma operação permitida. Não houve login ou confirmação humana nesse teste.

Configuração pública do backend conferida:

```text
PUBLIC_BASE_URL=https://api-backend-production-9c4c.up.railway.app
IFOOD_REDIRECT_URI=https://api-backend-production-9c4c.up.railway.app/callback
DEV_GLOBAL_SESSION=false
```

A variável de callback não comprova que a mesma URI esteja cadastrada no cliente OAuth do iFood. O responsável deve conferir esse cadastro e o agente público no painel antes do ensaio. O frontend de diagnóstico não é necessário para conectar pelo Telegram; o fluxo usa `/auth/ifood/start` e `/callback`.

No mesmo terminal Git Bash em que estão as variáveis Telegram, antes de iniciar o bot:

```bash
export BACKEND_BASE_URL="https://api-backend-production-9c4c.up.railway.app"
read -r -s -p "Segredo de serviço da API (BOT_API_TOKEN): " BACKEND_API_TOKEN
echo
export BACKEND_API_TOKEN
./.venv/Scripts/python.exe -m telegram_bot --check
./.venv/Scripts/python.exe -m telegram_bot
```

Use exatamente o `BOT_API_TOKEN` do serviço como `BACKEND_API_TOKEN` e o mesmo ID numérico em `TELEGRAM_ALLOWED_USER_ID` e `ALLOWED_ORGANIZER_IDS`. Não cole nenhum desses segredos em comandos literais ou no chat. Variáveis de outro terminal não são herdadas; `.env` não é carregado automaticamente. Se já houver polling em execução, encerre-o com Ctrl+C antes de iniciar outra instância, preservando `data/`.

Com callback HTTPS público, o navegador pode estar no computador ou no celular, mas o início e o retorno precisam ocorrer no mesmo navegador, com o cookie da tentativa. Tentativas pendentes ficam na memória do backend: não faça redeploy durante o login. Para preservar vínculos confirmados após redeploy, configure um volume no painel e aponte `IFOOD_LINKS_DIR` para um diretório dentro dele (por exemplo, volume `/data`, diretório `/data/ifood-links`). Se já existirem vínculos, preserve os arquivos antes de mudar o caminho.

Critério de conclusão: `/conectar` → autorização humana no navegador → `/confirmar` → clique humano em **Confirmar conexão** → `/verificar`. O backend precisa retornar sessão operacional e operações permitidas; login não aprova compra. Não registrar URLs OAuth, códigos, identidade da conta nem respostas com dados pessoais como evidência.

## Fluxo no Telegram

1. /conectar chama POST /api/bot/ifood/connect e mostra botão Abrir login do iFood. Novo comando cria outra tentativa e invalida a anterior.
2. Abrir o botão e autorizar no iFood no mesmo navegador que iniciou a tentativa. Com callback localhost, use o computador do backend; com callback HTTPS público configurado, também é possível usar o celular.
3. /confirmar consulta GET /api/bot/ifood/status e apresenta a identidade mascarada quando disponível. Se indisponível, isso é informado.
4. Somente tocar em Confirmar conexão se reconhecer a conta. O callback humano envia POST /api/bot/ifood/confirm com confirmationId do botão, após conferir que corresponde à tentativa atual.
5. /ifood consulta o estado sem chamar o iFood. /verificar chama POST /api/bot/ifood/verify para verificar/renovar a sessão.

/confirmar sem clique não confirma. Não aceitar códigos, URLs OAuth, tokens ou senhas no chat. Esta confirmação vincula a conta; não aprova compra. Cancelamento e desconexão no bot ainda não foram implementados; não são oferecidos botões para essas ações neste incremento.

## Autorização e transporte

- Só conversa privada do organizador permitido chega ao cliente HTTP. Cabeçalhos: Authorization: Bearer BACKEND_API_TOKEN e X-Telegram-User-Id do organizador validado pelo adaptador, nunca texto do usuário ou modelo.
- HTTPS obrigatório fora de loopback. A URL é uma origem sem caminho, query ou credenciais. O cliente não segue redirecionamentos e aceita o link de autorização somente na mesma origem do backend, com caminho /auth/ifood/start e tentativa correspondente. PUBLIC_BASE_URL e BACKEND_BASE_URL devem usar a mesma origem.
- Timeout de 50 segundos por chamada, sem retries automáticos HTTP. Exceções são saneadas, sem corpo remoto, código, credencial ou URL em log.
- Estado CONNECTED sozinho não libera o fluxo: operacional e allowedOperations precisam indicar acesso. O bot não chama operações de conta neste incremento.
- Falha de rede é indisponibilidade; não afirmar logout. Botão antigo não confirma outra tentativa. Teclado é removido após uso quando possível.
- Antes de POST de conexão, verificação ou confirmação, registrar update_id no SQLite. Repetição do update consulta o estado em vez de repetir a mutação, inclusive após reinício. Se houver interrupção entre registro e chamada, não se promete execução; consultar /ifood e emitir novo comando conscientemente.
- Erro de envio da resposta Telegram pode fazer o usuário perder o link de login. Consultar /ifood; se precisar de outro link, enviar um novo /conectar. Não gravar o link, confirmationId, código ou identidade da conta no SQLite.
- Outro clique no mesmo botão gera novo callback, mas o backend continua sendo a autoridade de uso único. ALREADY_CONFIRMED apenas consulta estado.

## Limites e próximos passos

Não há coleta do grupo, busca de ofertas, sacola, aprovação de pedido ou checkout no bot. Login não comprova autorização para compras. linkId ainda não é usado por uma sacola, pois ela não existe neste incremento; qualquer implementação futura deve vincular revisão e aprovação a esse ID e invalidá-las quando mudar.

Referência: [contrato bot→API](https://github.com/Modo-Escuro/api-backend/blob/686300d1a10c12bb6c3bd899e40fbd3a68c648f5/docs/bot-api.md).
