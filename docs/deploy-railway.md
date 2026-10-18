# Operar o bot na Railway

[Índice](README.md) · [Estado verificado](estado-atual.md) · [Login](login-ifood.md)

## Serviço existente

O serviço `telegram-bot` está conectado a `Modo-Escuro/telegram-bot`, branch `main`, no mesmo projeto do `api-backend`. A imagem Docker foi construída na Railway; o usuário confirmou respostas de `/start` e `/ifood`, e o login foi concluído. Consulte o snapshot em [estado atual](estado-atual.md) para as versões de referência.

O bot usa long polling: não recebe conexões HTTP e não precisa de domínio público, porta exposta ou healthcheck HTTP. Manter uma réplica e a cópia local parada.

## Variáveis e arquivos de configuração

| Variável do serviço do bot | Configuração |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token do BotFather, somente no painel/ambiente |
| `TELEGRAM_ALLOWED_USER_ID` | Mesmo organizador numérico permitido pela API |
| `BACKEND_BASE_URL` | `https://api-backend-production-9c4c.up.railway.app` |
| `BACKEND_API_TOKEN` | Referência `${{api-backend.BOT_API_TOKEN}}` |
| `TELEGRAM_STATE_DIR` | `/data`, dentro do volume próprio do bot |

O token Telegram foi validado sem webhook. Segredo bot→API, organizador e origem pública foram comparados sem exibir valores. Não copiar Client Secret ou tokens OAuth iFood para o bot.

| Arquivo versionado | Responsabilidade |
| --- | --- |
| `Dockerfile` | Python 3.12, instalação do pacote e execução `python -m telegram_bot` |
| `.dockerignore` | Contexto de build sem ambiente virtual, credenciais e bancos locais |
| `railway.toml` | Builder, comando de início, uma réplica, `/data` obrigatório, execução sem suspensão e política de restart |
| `.env.example` | Referência dos nomes; o programa não carrega `.env` automaticamente |

As credenciais ficam nas variáveis do serviço. O SQLite fica no volume e não integra a imagem ou o Git.

## Atualizar a main

Com autodeploy habilitado, push na branch conectada publica nova versão do código. Variáveis do painel continuam separadas do GitHub. A CI do bot executa testes e não contém comandos para reescrever variáveis Railway.

`railway.toml` tem precedência para os campos correspondentes de build/deploy. Mudanças nesses campos devem ser revisadas. Uma automação futura com credenciais administrativas ou infraestrutura como código também poderia alterar configuração.

`BACKEND_API_TOKEN` é uma referência: se `BOT_API_TOKEN` mudar na API, o valor resolvido do bot também depende dessa origem. Uma alteração de código pode ignorar ou interpretar diferente uma variável mesmo sem mudar o valor do painel.

Os `localhost` em testes e exemplos são intencionais. O bot lê `BACKEND_BASE_URL` do ambiente, sem fallback de rede para localhost. No backend `686300d`, as variáveis públicas precedem os defaults de desenvolvimento. Não usar `api-backend.railway.internal` neste cliente: o link aberto no navegador precisa da mesma origem HTTPS pública configurada na API.

Depois de publicar, conferir commit implantado, `SUCCESS`, instância `RUNNING`, volume e logs sem conflito 409. A resposta no Telegram depende do teste humano; status de deploy não substitui o ensaio. Um redeploy do bot não deve ser confundido com redeploy da API.

## Transferir execução entre computador e nuvem

A migração inicial já foi feita, com checksum e integridade conferidos e cópia local preservada. Não repetir a importação da cópia antiga sobre o volume atual.

Para recriar/migrar o serviço:

1. Preparar o destino sem polling, com volume próprio em `/data`. Manter o token Telegram ausente ou um contêiner temporário que não execute o bot.
2. Encerrar o processo de origem. Não deixar outra máquina ou serviço consumindo o mesmo token.
3. Preservar e copiar por canal privado o arquivo `bot-<id-do-bot>.sqlite3` do estado de origem, mantendo o nome. Fechar o SQLite nos dois lados; não copiar o arquivo de lock nem usar Git para a transferência.
4. Conferir checksum, integridade SQLite e presença do cursor e das ações no destino. Não remover estado nem sobrescrever um destino existente para contornar divergência.
5. Somente depois ativar o polling no destino, validar os comandos e manter a origem parada.

Para voltar ao computador, primeiro parar a nuvem e copiar de volta o SQLite atualizado. A cópia antiga não contém as ações processadas online. O lock impede concorrência no mesmo diretório, não entre computadores.

## Persistência da API

O bot já tem volume; a API ainda não. Seu diretório `.ifood-links` pode perder os vínculos em um redeploy. O próximo incremento deve preservar os arquivos existentes e migrá-los para um volume exclusivo da API antes de mudar `IFOOD_LINKS_DIR`.

Tentativas OAuth pendentes ficam em memória mesmo com volume: não redeployar a API durante o login. Não mover ou expor tokens em commits, logs ou no chat. O frontend de diagnóstico não é necessário para o fluxo de login do bot.

Referências operacionais: [variáveis](https://docs.railway.com/variables), [configuração como código](https://docs.railway.com/config-as-code/reference), [volumes](https://docs.railway.com/volumes).
