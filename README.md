# Telegram Bot — Compra com Contexto

Interface conversacional para a demo do hackathon SEMCOMP, em conversa privada entre organizador e bot. O organizador informa as necessidades do grupo; o sistema preserva orçamento e restrições quando o pedido muda e solicita aprovação humana antes do envio.

**Status: base documental inicial. O bot, o long polling e a integração HTTP ainda não estão implementados. Não há operações de compra disponíveis neste repositório.**

Fluxo previsto: Telegram → adaptador Python → [api-backend](https://github.com/Modo-Escuro/api-backend) → agente e validações determinísticas → MCP do iFood.

## Responsabilidades

- Bot: receber mensagens e cliques, verificar o usuário permitido, encaminhar eventos autenticados à API e apresentar opções, sacola e status.
- Backend: manter contexto e participantes, executar o agente, autenticar no iFood, consultar/modificar a sacola, validar aprovação e reconciliar resultados desconhecidos.
- Aprovação: evento humano validado pela API, associado ao responsável, à versão e ao total revisados. O modelo não pode produzir sua própria autorização.

## Documentação

- [Regras preservadas e critérios de migração](docs/regras-preservadas.md).
- [Etapas da demo e contrato pendente](docs/plano-demo.md).
- [Especificação v0.2 preservada](docs/baseline/stakeholder-requirements-specification.md), ainda em validação.
- [Proveniência e hashes das cópias](docs/baseline/proveniencia.json).

O [repositório original](https://github.com/Modo-Escuro/compra-com-contexto) preserva o protótipo Python, seus testes e seu histórico. As cópias em docs/baseline são referências históricas, não funcionalidades implementadas pelo bot. Os links relativos internos da especificação preservada pertencem ao repositório de origem.

## Preparação

1. Criar o bot manualmente no @BotFather com /newbot.
2. Guardar o token somente no ambiente local; nunca em mensagens, commits ou logs.
3. Definir um organizador permitido pelo ID numérico do Telegram.
4. Validar as rotas disponíveis no api-backend antes de implementar o adaptador.

Os nomes em .env.example são propostas para a implementação futura; ainda não existe programa que os carregue. O OAuth do iFood permanece no backend.