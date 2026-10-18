# Telegram Bot — Compra com Contexto

Interface conversacional para a demo do hackathon SEMCOMP, em conversa privada entre organizador e bot. O organizador informa as necessidades do grupo; o sistema preserva orçamento e restrições quando o pedido muda e solicita aprovação humana antes do envio.

**Status: bot inicial implementado com long polling, /start, /status, /ajuda e acesso restrito ao organizador em conversa privada. Cliente HTTP e comandos /conectar, /confirmar, /ifood e /verificar implementados, com confirmação humana por botão. Conversa de compras e pedidos ainda pendentes. Testes automatizados usam respostas simuladas do Telegram; conexão real depende da configuração local.**

Fluxo previsto: Telegram → adaptador Python → [api-backend](https://github.com/Modo-Escuro/api-backend) → agente e validações determinísticas → MCP do iFood.

## Responsabilidades

- Bot: receber mensagens e cliques, verificar o usuário permitido, encaminhar eventos autenticados à API e apresentar opções, sacola e status.
- Backend: manter contexto e participantes, executar o agente, autenticar no iFood, consultar/modificar a sacola, validar aprovação e reconciliar resultados desconhecidos.
- Aprovação: evento humano validado pela API, associado ao responsável, à versão e ao total revisados. O modelo não pode produzir sua própria autorização.

## Executar

Siga o [guia de execução no Git Bash](docs/executar-bot.md) para criar o bot no BotFather, configurar o token sem exibi-lo, descobrir seu ID com --identify e iniciar o processo. Python 3.12; nenhuma dependência externa em execução.

## Documentação

- [Publicar o bot na Railway](docs/deploy-railway.md): serviço, variáveis e transferência do estado local.
- [Regras preservadas e critérios de migração](docs/regras-preservadas.md).
- [Etapas da demo e contrato pendente](docs/plano-demo.md).
- [Login iFood e vínculo com o organizador](docs/login-ifood.md): pré-requisito das operações vinculadas à conta; cliente implementado, ensaio de login real pendente.
- [Especificação v0.2 preservada](docs/baseline/stakeholder-requirements-specification.md), ainda em validação.
- [Proveniência e hashes das cópias](docs/baseline/proveniencia.json).

O [repositório original](https://github.com/Modo-Escuro/compra-com-contexto) preserva o protótipo Python, seus testes e seu histórico. As cópias em docs/baseline são referências históricas, não funcionalidades implementadas pelo bot. Os links relativos internos da especificação preservada pertencem ao repositório de origem.

## Preparação

1. Criar o bot manualmente no @BotFather com /newbot.
2. Guardar o token somente no ambiente local; nunca em mensagens, commits ou logs.
3. Definir um organizador permitido pelo ID numérico do Telegram.
4. Validar as rotas disponíveis no api-backend antes de implementar o adaptador.

As variáveis TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_ID e TELEGRAM_STATE_DIR são lidas do ambiente do processo. .env não é carregado automaticamente. BACKEND_BASE_URL e BACKEND_API_TOKEN habilitam a integração HTTP de login. O OAuth do iFood permanece no backend.