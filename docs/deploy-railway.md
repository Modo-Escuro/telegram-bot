# Publicar o bot na Railway

Status: configuração do worker preparada para publicação na Railway, com uma réplica e volume obrigatório. A configuração do backend foi conferida separadamente; não comprova login iFood completo. O callback HTTPS permanece dependente da aprovação no iFood.

## Serviço e variáveis

O bot usa long polling: não recebe conexões HTTP, não precisa de domínio público, porta exposta ou healthcheck HTTP. A aprovação do callback iFood pode ficar pendente enquanto o bot atende `/start`, `/status` e `/ajuda`. `/conectar` continua dependente da configuração do backend e da autorização no navegador.

No projeto do `api-backend`, crie pelo painel um serviço separado a partir do repositório `Modo-Escuro/telegram-bot`, branch `main`. Os arquivos deste incremento precisam estar publicados nessa branch antes do deploy. Prepare o serviço sem iniciar o polling; configure as variáveis, o volume e a transferência do estado antes de ativá-lo. Se a interface iniciar o serviço automaticamente, mantenha `TELEGRAM_BOT_TOKEN` ausente até concluir essa preparação.

| Variável no serviço do bot | Valor |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | Token atual do BotFather, inserido somente no painel |
| `TELEGRAM_ALLOWED_USER_ID` | Mesmo organizador numérico permitido em `ALLOWED_ORGANIZER_IDS` na API |
| `BACKEND_BASE_URL` | `https://api-backend-production-9c4c.up.railway.app` |
| `BACKEND_API_TOKEN` | Mesmo segredo de `BOT_API_TOKEN` no serviço `api-backend` |
| `TELEGRAM_STATE_DIR` | `/data` |

Não copie o Client Secret ou tokens OAuth iFood para o bot. Não coloque valores privados em `railway.toml`, Dockerfile, GitHub Actions ou arquivos versionados. `.env.example` é apenas referência e `.env` não é carregado pelo programa.

Anexe um volume persistente próprio ao serviço do bot em `/data`. O `railway.toml` exige essa montagem, uma réplica, processo sem suspensão e ausência de sobreposição configurada entre deploys. Não reutilize o volume da API. O serviço `api-backend` precisa do próprio volume e de `IFOOD_LINKS_DIR` dentro dele para preservar vínculos após redeploy.

## Transferência da execução local

1. Configure o serviço e seu volume mantendo o token Telegram ausente para que ele não consuma updates.
2. Encerre o bot local com Ctrl+C. Não deixe outro computador ou serviço consumindo o mesmo token.
3. Preserve o diretório de estado local. Copie por um canal privado o arquivo `bot-<id-do-bot>.sqlite3` do `TELEGRAM_STATE_DIR` local para `/data` do volume, mantendo o nome. Não use Git para essa transferência e não abra o conteúdo em logs. O arquivo de lock não precisa ser copiado. O SQLite deve estar fechado nos dois lados durante a cópia.
4. Confira que o arquivo no volume preserva cursor e registro de ações. Se a transferência não estiver disponível ou não puder ser verificada, mantenha o serviço sem token e conclua essa etapa antes de migrar; não remova o estado para contornar o problema.
5. Insira `TELEGRAM_BOT_TOKEN` no serviço e aplique o deploy. Mantenha a cópia local parada. O lock do bot protege processos no mesmo volume, mas não protege contra polling simultâneo no seu computador.
6. Confira os logs de início, ausência de conflito 409 e as respostas de `/start` e `/ifood`. Não cole logs que contenham dados privados no chat.

Para voltar ao computador, pare primeiro o serviço da nuvem e transfira de volta o SQLite atualizado antes de iniciar o polling local. Preservar apenas a cópia antiga não preserva as ações processadas na nuvem.

## Atualizações da main e localhost

Com autodeploy habilitado, um push na branch conectada gera nova versão do código. As variáveis configuradas no painel continuam separadas do repositório. Este repositório não contém automação que reescreva variáveis Railway; sua CI executa testes. No serviço configurado, `BACKEND_API_TOKEN` referencia `${{api-backend.BOT_API_TOKEN}}`; uma alteração da variável de origem muda o valor resolvido, sem editar o GitHub.

`railway.toml` versiona builder, comando de início, réplicas e política de deploy; esses campos têm precedência sobre a configuração correspondente no painel. Não define segredos nem `BACKEND_BASE_URL`. Automações futuras com credenciais administrativas Railway ou infraestrutura como código podem alterar configuração e precisam de revisão.

Os `localhost` em testes e exemplos são intencionais. O bot usa `BACKEND_BASE_URL` do ambiente, sem fallback de rede para localhost. No backend revisado (`686300d`), `PUBLIC_BASE_URL`, `IFOOD_REDIRECT_URI` e `WEB_ORIGIN` leem primeiro o ambiente; localhost é fallback de desenvolvimento. Não use `api-backend.railway.internal` no bot atual: o link de início do login deve ter a mesma origem HTTPS pública configurada na API.

Não faça redeploy do backend durante uma autorização: tentativas pendentes ficam em memória. Os arquivos persistidos guardam vínculos confirmados, não tentativas pendentes. A mudança de código também pode mudar o comportamento de leitura das variáveis, mesmo sem alterar seus valores no painel.

## Validação e limites

O ensaio de login continua sendo `/conectar` → autorização no navegador → `/confirmar` → clique humano → `/verificar`, com sessão operacional e operações permitidas. Login não aprova compras. Não há conversa de compras, sacola ou checkout implementados no bot.

Antes de publicar, executar os testes simulados e revisar o diff. A imagem Docker e o deploy real precisam ser verificados em ambiente com Docker/Railway; testes Python não substituem essa validação. Não executar polling com token real como teste automatizado.

Referências: [variáveis](https://docs.railway.com/variables), [configuração como código](https://docs.railway.com/config-as-code/reference), [volumes](https://docs.railway.com/volumes).

## Migração inicial conferida

Em 17/10/2026, o serviço `telegram-bot` foi configurado no projeto da API com volume próprio em `/data`. Token Telegram válido e ausência de webhook foram conferidos sem polling; segredo bot→API e organizador coincidiram com o backend. O SQLite local fechado foi transferido por SSH para o volume de um contêiner temporário sem polling; checksum, integridade SQLite e presença das tabelas de cursor e ações foram verificados. A cópia local foi preservada. Isso não comprova login iFood, resposta a mensagens na nuvem ou operações de compra.
